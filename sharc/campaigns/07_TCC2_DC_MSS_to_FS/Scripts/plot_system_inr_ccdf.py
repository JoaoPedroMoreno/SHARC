"""INR CCDFs for baseline, HO5/HO30 and PBO100km; same empirical rule as GUI_new."""
import argparse
import csv
from datetime import datetime
import gzip
import json
import math
from pathlib import Path
import re
import yaml

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CAMPAIGN = Path(__file__).resolve().parents[1]
PATTERN = re.compile(
    r"^output_tcc2_SA_noPY_(?P<altitude>340|525)km_FS(?P<height>20|40)m_"
    r"LF(?P<lf>20|50)_Azi90_(?P<mode>BASELINE|HO5|HO30|PBO100km)"
    r"(?:_(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+))?$")
MODES = ["BASELINE", "HO5", "HO30", "PBO100km"]
COLORS = {"BASELINE": "#555555", "HO5": "#0072B2", "HO30": "#D55E00", "PBO100km": "#009E73"}
LABELS = {"BASELINE": "Baseline", "HO5": "HO (max. 5)", "HO30": "HO (max. 30)", "PBO100km": "PBO (100 km)"}
Y_FLOOR = 1e-4


def read_snapshot_records(folder):
    """Read only completed snapshots while a simulation may still be writing."""
    manifest = folder / "tcc2_manifest.json"
    limit = None
    if manifest.exists():
        try:
            limit = json.loads(manifest.read_text())["completed_snapshots"]
        except json.JSONDecodeError:
            pass  # A manifest rewrite can overlap this read.
    records = {}
    with gzip.open(folder / "tcc2_snapshots.csv.gz", "rt", encoding="utf-8-sig", newline="") as stream:
        try:
            for row in csv.DictReader(stream):
                sid = int(row["snapshot_id"])
                if limit is not None and sid > limit:
                    break
                if sid in records:
                    raise ValueError(f"Duplicate snapshot {sid}: {folder}")
                records[sid] = row
                if sid == limit:
                    break
        except EOFError:
            print(f"Ignoring unfinished gzip tail: {folder.name}")
    return records


def paired_samples(folders):
    records = {mode: read_snapshot_records(folder) for mode, folder in folders.items()}
    common = sorted(set.intersection(*(set(rows) for rows in records.values())))
    for sid in common:
        rows = [records[mode][sid] for mode in records]
        if len({r["secondary_seed"] for r in rows}) != 1:
            raise ValueError(f"Unpaired seeds at snapshot {sid}")
        if "BASELINE" in records:
            for mode in (name for name in records if name.startswith("HO")):
                baseline, handover = records["BASELINE"][sid], records[mode][sid]
                for field in ("realization_sha256", "initial_performance_sha256", "baseline_links_sha256"):
                    if field == "initial_performance_sha256" and any(
                            r.get("ue_performance_calculated") == "False" for r in (baseline, handover)):
                        continue
                    if not baseline[field] or baseline[field] != handover[field]:
                        raise ValueError(f"Baseline/{mode} mismatch in {field}, snapshot {sid}")
        if not all(np.isfinite(float(r["inr_after_db"])) for r in rows):
            raise ValueError(f"Nonfinite INR at paired snapshot {sid}")
    samples = {mode: np.array([float(rows[sid]["inr_after_db"]) for sid in common])
               for mode, rows in records.items()}
    return samples, common


def read_samples(folder):
    # Snapshot records are incremental and contain one final INR per snapshot.
    path = folder / "tcc2_snapshots.csv.gz"
    if path.exists():
        values = [float(row["inr_after_db"]) for row in read_snapshot_records(folder).values()]
    else:
        with (folder / "system_inr.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            field = next((f for f in ["system_inr", "samples", "value"] if f in fields), None)
            if field is None:
                if len(fields) != 1:
                    raise ValueError(f"Unknown INR CSV schema: {folder}")
                field = fields[0]
            values = [float(row[field]) for row in reader]
    values = np.asarray(values, dtype=float)
    return values[np.isfinite(values)]


def compute_ccdf(samples):
    values = np.asarray(samples, dtype=float)
    x = np.sort(values[np.isfinite(values)])
    if not x.size:
        return x, x.copy()
    return x, 1.0 - np.arange(1, x.size + 1) / x.size


def handover_metrics(before, after):
    """Use the same empirical 80th percentile as the campaign-02 FS figures."""
    before, after = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
    if before.ndim != 1 or before.shape != after.shape or not before.size:
        raise ValueError("Expected nonempty paired one-dimensional samples")
    if not (np.isfinite(before).all() and np.isfinite(after).all()):
        raise ValueError("Nonfinite paired INR")
    index = math.ceil(.8 * before.size) - 1
    q_before, q_after = (float(np.sort(values)[index]) for values in (before, after))
    p_before, p_after = (float(np.mean(values > -6) * 100) for values in (before, after))
    return dict(snapshots=before.size, inr20_baseline_db=q_before, inr20_handover_db=q_after,
                gain_at_20pct_db=q_before - q_after,
                margin20_baseline_db=-6 - q_before, margin20_handover_db=-6 - q_after,
                exceedance_baseline_pct=p_before, exceedance_handover_pct=p_after,
                exceedance_reduction_pp=p_before - p_after)


def plot_handover_preview(output_root, plots_dir, load_factors=(20, 50), handover_mode=None):
    """Freeze matched completed samples once for both figures and their audit data."""
    scenarios = discover(output_root)
    if handover_mode is None:
        handover_mode = "HO30" if any(key[3] == "HO30" for key in scenarios) else "HO5"
    if handover_mode not in ("HO5", "HO30"):
        raise ValueError(f"Unknown handover mode: {handover_mode}")
    handover_limit = int(handover_mode[2:])
    cases, sample_rows, sources = [], [], []
    captured = datetime.now().astimezone().isoformat(timespec="seconds")
    for altitude, height, lf in sorted({key[:3] for key in scenarios}):
        if lf not in load_factors:
            continue
        pair = {mode: scenarios.get((altitude, height, lf, mode)) for mode in ("BASELINE", handover_mode)}
        if any(value is None for value in pair.values()):
            continue
        # Baseline may be reused across run dates; actual initial-state hashes must match.
        folders = {mode: entry[1] for mode, entry in pair.items()}
        samples, ids = paired_samples(folders)
        if not ids:
            continue
        metrics = dict(altitude_km=altitude, fs_height_m=height, lf_pct=lf, handover_mode=handover_mode,
                       **handover_metrics(samples["BASELINE"], samples[handover_mode]))
        cases.append((metrics, samples))
        sources.append(dict(**metrics, captured_at=captured,
                            baseline_source=str(folders["BASELINE"]), handover_source=str(folders[handover_mode]),
                            snapshot_ids=ids))
        sample_rows.extend(dict(altitude_km=altitude, fs_height_m=height, lf_pct=lf, handover_mode=handover_mode,
                                snapshot_id=sid, baseline_inr_db=float(before), handover_inr_db=float(after))
                           for sid, before, after in zip(ids, samples["BASELINE"], samples[handover_mode]))
    if not cases:
        print(f"No paired baseline/{handover_mode} results available. No artificial data generated.")
        return []
    plots_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in ((f"handover_criterion_metrics_{handover_mode}.csv", [case[0] for case in cases]),
                       (f"handover_paired_samples_{handover_mode}.csv", sample_rows)):
        with (plots_dir / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (plots_dir / f"handover_preview_sources_{handover_mode}.json").write_text(json.dumps(dict(
        captured_at=captured, cases=sources,
        quantile="sorted_samples[ceil(0.8*N)-1], same as campaign-02 FS figures",
        ccdf="1-rank/N", exceedance="count(INR > -6 dB)/N",
        pairing="common snapshot IDs, seeds, realization/link hashes; performance hash when both modes calculate it",
        uncertainty="point estimates only; no confidence intervals"), indent=2), encoding="utf-8")
    generated = []
    colors = {"BASELINE": "#0072B2", handover_mode: "#D89000"}
    labels = {"BASELINE": "Sem handover", handover_mode: f"Com {handover_mode}"}
    with plt.rc_context({"font.family": "serif", "font.size": 11,
                         "axes.titlesize": 12, "legend.fontsize": 11}):
        for altitude in sorted({case[0]["altitude_km"] for case in cases}):
            group = sorted([case for case in cases if case[0]["altitude_km"] == altitude],
                           key=lambda case: (case[0]["lf_pct"], case[0]["fs_height_m"]))
            fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.8))
            fig.subplots_adjust(left=.14, right=.98, bottom=.19, top=.78, wspace=.28)
            fig.suptitle(f"Efeito do handover no criterio de protecao | {altitude} km", y=.98, fontsize=16)
            handles = []
            for column, (ax, prefix, limit) in enumerate(zip(axes, ("inr20", "exceedance"), (-6, 20))):
                ax.axvline(limit, color="#333333", linestyle=":", linewidth=1.5)
                for row, (metrics, _) in enumerate(group):
                    y = len(group) - 1 - row
                    suffix = "db" if column == 0 else "pct"
                    before = metrics[f"{prefix}_baseline_{suffix}"]
                    after = metrics[f"{prefix}_handover_{suffix}"]
                    ax.plot([before, after], [y+.09, y-.09], color="#999999", linewidth=1.2, zorder=1)
                    for mode, value, offset, marker in (("BASELINE", before, .09, "o"), (handover_mode, after, -.09, "s")):
                        point, = ax.plot(value, y+offset, marker=marker, color=colors[mode],
                                         markersize=7, linestyle="none", label=labels[mode], zorder=3)
                        if column == 0 and row == 0:
                            handles.append(point)
                        ax.annotate(f"{value:.2f}" if column == 0 else f"{value:.1f}%",
                                    (value, y+offset), xytext=(0, 9 if offset > 0 else -17),
                                    textcoords="offset points", ha="center", color=colors[mode], fontsize=10)
                    gain = metrics["gain_at_20pct_db" if column == 0 else "exceedance_reduction_pp"]
                    ax.text(.98, y, f"-{gain:.2f} dB" if column == 0 else f"-{gain:.1f} p.p.",
                            transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=10)
                ax.set_ylim(-.65, len(group)-.35)
                ax.set_yticks(range(len(group)))
                ax.set_yticklabels([f"FS {m['fs_height_m']} m | LF {m['lf_pct']}%\nN = {m['snapshots']}"
                                    for m, _ in reversed(group)] if column == 0 else [])
                ax.grid(axis="x", color="#dddddd", linewidth=.7)
                ax.set_axisbelow(True)
                ax.spines[["top", "right"]].set_visible(False)
            values = [m[key] for m, _ in group for key in ("inr20_baseline_db", "inr20_handover_db")]
            low, high = min(-6, min(values)), max(-6, max(values))
            width = max(high-low, 3)
            axes[0].set_xlim(low-.18*width, high+.40*width)
            axes[0].set(title="(a) INR no ponto de 20% da CCDF", xlabel="INR20 (dB) | criterio: -6 dB")
            axes[1].set(xlim=(-5, 119), title="(b) Excedencia do limiar de -6 dB",
                        xlabel="Snapshots com INR > -6 dB (%) | limite: 20%")
            axes[1].set_xticks([0, 20, 40, 60, 80, 100])
            fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.55, .925), ncol=2, frameon=False)
            fig.text(.5, .055, "Previa: mesmos snapshots nas duas curvas; estimativas pontuais, sem IC.\n"
                     f"Menor e melhor. {handover_mode}: top_k={handover_limit}, no maximo {handover_limit} reassociacoes aceitas por snapshot.",
                     ha="center", fontsize=10)
            stem = plots_dir / f"handover_criterion_Sys3_{altitude}km_{handover_mode}"
            for suffix in (".png", ".pdf"):
                path = stem.with_suffix(suffix)
                fig.savefig(path, dpi=300, bbox_inches="tight")
                generated.append(path)
            plt.close(fig)

            fig, axes = plt.subplots(math.ceil(len(group)/2), 2, figsize=(12, 4.1*math.ceil(len(group)/2)),
                                     squeeze=False, sharex=True, sharey=True)
            fig.subplots_adjust(left=.08, right=.98, bottom=.13, top=.84, hspace=.42, wspace=.17)
            fig.suptitle(f"CCDF antes e depois do {handover_mode} | DC-MSS / FS | {altitude} km", y=.98, fontsize=15)
            handles = []
            all_values = np.concatenate([values for _, samples in group for values in samples.values()])
            x_limits = (min(-8, math.floor(all_values.min()/5)*5), max(0, math.ceil(all_values.max()/5)*5))
            for ax, (metrics, samples) in zip(axes.flat, group):
                for mode, style, marker in (("BASELINE", "-", "o"), (handover_mode, "--", "s")):
                    x, y = compute_ccdf(samples[mode])
                    line, = ax.plot(x, y, color=colors[mode], linestyle=style, linewidth=1.6, label=labels[mode])
                    if len(handles) < 2:
                        handles.append(line)
                    field = "inr20_baseline_db" if mode == "BASELINE" else "inr20_handover_db"
                    ax.plot(metrics[field], .2, marker=marker, color=colors[mode], markersize=6)
                ax.axhline(.2, color="#777777", linestyle=":", linewidth=1.0)
                ax.plot([-6, -6], [.2, 1], color="black", linestyle=":", linewidth=1.4)
                ax.plot(-6, .2, marker="+", color="black", markersize=9)
                ax.set(yscale="log", ylim=(.01, 1), xlim=x_limits, xlabel="INR (dB)", ylabel="CCDF",
                       title=f"FS {metrics['fs_height_m']} m | LF {metrics['lf_pct']}% | N={metrics['snapshots']}")
                ax.text(.97, .95, f"INR20: {metrics['inr20_baseline_db']:.2f} -> {metrics['inr20_handover_db']:.2f} dB\n"
                        f"Reducao no ponto: {metrics['gain_at_20pct_db']:.2f} dB", transform=ax.transAxes,
                        ha="right", va="top", fontsize=10,
                        bbox=dict(facecolor="white", edgecolor="none", alpha=.9))
                ax.grid(True, which="both", alpha=.23)
            for ax in list(axes.flat)[len(group):]:
                ax.set_visible(False)
            fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .94), ncol=2, frameon=False)
            fig.text(.5, .035, "Previa pareada, sem IC. Referencia: INR = -6 dB em 20% do tempo.\n"
                     "CCDF empirica = 1 - rank/N; INR20: quantil empirico usado nos graficos anteriores do FS.",
                     ha="center", fontsize=10)
            stem = plots_dir / f"handover_ccdf_Sys3_{altitude}km_{handover_mode}"
            for suffix in (".png", ".pdf"):
                path = stem.with_suffix(suffix)
                fig.savefig(path, dpi=300, bbox_inches="tight")
                generated.append(path)
            plt.close(fig)
    for metrics, _ in cases:
        print(json.dumps(metrics))
    return generated


def discover(output_root):
    roots = [output_root] if isinstance(output_root, Path) else output_root
    folders = {p.parent.resolve() for root in roots
               for pattern in ["tcc2_snapshots.csv.gz", "system_inr.csv"]
               for p in root.rglob(pattern)}
    latest = {}
    for folder in sorted(folders):
        match = PATTERN.fullmatch(folder.name)
        if not match:
            continue
        info = match.groupdict()
        key = (int(info["altitude"]), int(info["height"]), int(info["lf"]), info["mode"])
        rank = (info["date"] or "0000-00-00", int(info["run"] or 0))
        try:
            samples = read_samples(folder)
        except (OSError, EOFError, ValueError) as error:
            print(f"Skipping unreadable/in-progress result {folder}: {error}")
            continue
        if not samples.size:
            continue
        if key in latest and rank == latest[key][0]:
            raise ValueError(f"Ambiguous repeated run for {key}; choose a narrower --output-root")
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, folder, samples)
    return latest


def plot(output_root, plots_dir, load_factors=(20, 50), paired=False):
    scenarios = {key: value for key, value in discover(output_root).items() if key[2] in load_factors}
    if not scenarios:
        print(f"No INR results yet in {output_root}. No artificial data generated.")
        return []
    plt.rcParams.update({"font.family": "serif", "font.size": 10,
                         "axes.titlesize": 11, "legend.fontsize": 8.5})
    plots_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for altitude, height in sorted({key[:2] for key in scenarios}):
        common_ids = {}
        if paired:
            for lf in load_factors:
                folders = {mode: scenarios[altitude, height, lf, mode][1] for mode in MODES
                           if (altitude, height, lf, mode) in scenarios}
                if not folders:
                    continue
                samples_by_mode, common_ids[lf] = paired_samples(folders)
                for mode, samples in samples_by_mode.items():
                    rank, folder, _ = scenarios[altitude, height, lf, mode]
                    scenarios[altitude, height, lf, mode] = (rank, folder, samples)
        fig, ax = plt.subplots(figsize=(7.16, 3.6))
        used = []
        for mode in MODES:
            for lf in load_factors:
                key = (altitude, height, lf, mode)
                if key not in scenarios:
                    print(f"Missing curve: {key}")
                    continue
                _, folder, samples = scenarios[key]
                if not len(samples):
                    continue
                x, y = compute_ccdf(samples)
                ax.plot(x, np.clip(y, Y_FLOOR, 1), color=COLORS[mode],
                        linestyle="-" if lf == 20 else "--", linewidth=1.6,
                        marker="o" if x.size == 1 else None, markersize=3,
                        label=f"{LABELS[mode]}, LF={lf}% (N={len(samples)})")
                used.append(dict(mode=mode, lf=lf, snapshots=len(samples), source=str(folder),
                                 exceedance_at_minus6=float(np.mean(samples > -6)),
                                 paired=paired, snapshot_ids=json.dumps(common_ids.get(lf, []))))
                print(f"{folder.name}: {len(samples)} snapshots")
        ax.plot([-6, -6], [.2, 1], "k:", linewidth=1.5, label="-6 dB / 20% of time")
        if not used:
            plt.close(fig)
            continue
        title = f"DC-MSS System 3, {altitude} km, FS={height} m"
        if paired:
            title += "\nPreliminary results: matched snapshots"
        ax.set(yscale="log", ylim=(Y_FLOOR, 1), xlabel="INR (dB)", ylabel="CCDF", title=title)
        ax.grid(True, which="both", alpha=.25)
        ax.legend(loc="best", ncol=2)
        fig.tight_layout()
        selection = "" if tuple(load_factors) == (20, 50) else "_LF" + "_".join(map(str, load_factors))
        stem = plots_dir / (f"system_inr_ccdf_Sys3_{altitude}km_FS{height}m" + selection)
        for suffix in [".png", ".pdf"]:
            path = stem.with_suffix(suffix)
            fig.savefig(path, dpi=300, bbox_inches="tight")
            generated.append(path)
        plt.close(fig)
        with stem.with_suffix(".sources.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(used[0]))
            writer.writeheader()
            writer.writerows(used)
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, action="append",
                        help="Repeat for multiple roots; default: local output and base output_dir")
    parser.add_argument("--plots-dir", type=Path, default=CAMPAIGN / "plots/system_inr_ccdf")
    parser.add_argument("--lf", type=int, nargs="+", choices=[20, 50], default=[20, 50])
    parser.add_argument("--paired", action="store_true", help="Use common completed snapshot IDs and seeds")
    parser.add_argument("--handover-preview", action="store_true", help="Paired before/after criterion summary and CCDFs")
    parser.add_argument("--handover-mode", choices=["HO5", "HO30"], help="Preview mode; defaults to HO30 when available, otherwise HO5")
    args = parser.parse_args()
    if args.output_root is None:
        base = yaml.safe_load((Path(__file__).with_name("base_input.yaml")).read_text(encoding="utf-8"))
        args.output_root = [CAMPAIGN / "output", Path(base["general"]["output_dir"])]
    paths = (plot_handover_preview(args.output_root, args.plots_dir, args.lf, args.handover_mode) if args.handover_preview
             else plot(args.output_root, args.plots_dir, args.lf, args.paired))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
