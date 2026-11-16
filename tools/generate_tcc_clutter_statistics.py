"""Plot the executable SHARC spatial-clutter quantiles, without simulations.

Run from a Python environment with the SHARC dependencies:
    python tools/generate_tcc_clutter_statistics.py

The plotted quantiles precede the below_rooftop selection mask. They are NOT
quantiles of the mixture of selected links and zero-clutter links. No equations
are reimplemented here, and negative model outputs are intentionally retained.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import logging
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
import scipy
import yaml

from sharc.propagation.propagation_clutter_loss import PropagationClutterLoss

SOURCE = ROOT / "sharc/propagation/propagation_clutter_loss.py"
CAMPAIGNS = [ROOT / "sharc/campaigns" / name for name in (
    "07_TCC2_DC_MSS_to_FS", "08_TCC2_DC_MSS_performance")]
PERCENTILES = (0.1, 0.5, 0.9)
STYLES = (("#287499", "-"), ("#354650", "--"), ("#b34046", "-."))
SEED = 2108


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def profile(cfg):
    fs = cfg["single_earth_station"]
    assert fs["channel_model"] == "P619"
    assert not cfg["imt"]["interfered_with"]
    assert cfg["imt"]["frequency"] == fs["frequency"] == 2155
    return {
        "height_m": fs["geometry"]["height"],
        "environment": fs["param_p619"]["mean_clutter_height"],
        "below_rooftop_percent": fs["param_p619"]["below_rooftop"],
        "frequency_mhz": fs["frequency"],
    }


def read_profiles():
    profiles, checked, sources = {}, 0, [SOURCE]
    for index, campaign in enumerate(CAMPAIGNS):
        generator = campaign / "Scripts/generate.py"
        spec = importlib.util.spec_from_file_location(f"clutter_campaign_{index}", generator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # build() only constructs an in-memory dict; never invoke main()/generate().
        for height in (20, 40):
            item = profile(module.build(340, height, 0.2, "BASELINE"))
            if height in profiles:
                assert item == profiles[height]
            profiles[height] = item
        sources.extend([generator, campaign / "Scripts/base_input.yaml"])
        for path in sorted((campaign / "input").glob("*.yaml")):
            cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
            item = profile(cfg)
            assert item == profiles[item["height_m"]], str(path)
            sources.append(path)
            checked += 1
    assert profiles[20]["environment"] == "low"
    assert profiles[40]["environment"] == "mid"
    assert profiles[20]["below_rooftop_percent"] == 60
    assert profiles[40]["below_rooftop_percent"] == 10
    sources.extend([ROOT / "sharc/propagation/propagation_p619.py",
                    ROOT / "sharc/propagation/propagation_factory.py"])
    return list(profiles.values()), checked, sources


def loss(model, elevation, p, spec):
    shape = elevation.shape
    return model.get_spatial_clutter_loss(
        np.full(shape, spec["frequency_mhz"], dtype=float), elevation,
        np.full(shape, p, dtype=float),
        np.full(shape, spec["height_m"], dtype=float), spec["environment"])


def validate(model, profiles):
    checks = []
    for spec in profiles:
        # Validate quantile ordering, not monotonicity in elevation.
        angles = np.linspace(0, 90, 901)
        qs = np.linspace(.0001, .9999, 1001)
        e, p = np.broadcast_arrays(angles[:, None], qs[None, :])
        values = loss(model, e, p, spec)
        assert np.isfinite(values).all()
        assert (np.diff(values, axis=1) >= -1e-10).all()
        args = dict(frequency=np.full(1000, 2155.), distance=np.full(1000, 1e6),
                    elevation=np.full(1000, 30.), clutter_scenario="spatial",
                    earth_station_height=np.full(1000, spec["height_m"], dtype=float),
                    mean_clutter_height=spec["environment"], loc_percentage=.5)
        expected = loss(model, args["elevation"], .5, spec)
        np.testing.assert_array_equal(model.get_loss(**args, below_rooftop=100), expected)
        assert np.count_nonzero(model.get_loss(**args, below_rooftop=0)) == 0
        applied = model.get_loss(**args, below_rooftop=spec["below_rooftop_percent"])
        count = int(round(1000 * spec["below_rooftop_percent"] / 100))
        assert np.count_nonzero(applied) == count
        np.testing.assert_array_equal(applied[applied != 0], expected[applied != 0])
        # Changing distance cannot change this spatial kernel (same RNG state).
        state = model.random_number_gen.get_state()
        one = model.get_loss(**args, below_rooftop=spec["below_rooftop_percent"])
        model.random_number_gen.set_state(state)
        args["distance"] *= 2
        two = model.get_loss(**args, below_rooftop=spec["below_rooftop_percent"])
        np.testing.assert_array_equal(one, two)
        checks.append(dict(height_m=spec["height_m"], selected_links=count,
                           tested_links=1000, quantile_ordering=True,
                           wrapper_matches_kernel=True, distance_invariant=True))
    return checks


def style_axes(ax, small=False):
    ax.set_axisbelow(True)
    ax.grid(which="major", color="#d9e0e4", linewidth=.8)
    ax.grid(which="minor", color="#edf0f2", linewidth=.5)
    ax.axhline(0, color="#85929a", linewidth=.9, zorder=1)
    ax.xaxis.set_major_locator(MultipleLocator(30 if small else 15))
    ax.xaxis.set_minor_locator(MultipleLocator(10 if small else 5))
    fmt = FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))
    ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(labelsize=12 if small else 15, colors="#354650")
    for spine in ax.spines.values():
        spine.set_color("#354650")
        spine.set_linewidth(.9)


def plot(profiles, elevation, curves, out):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16,
                         "axes.labelsize": 17, "legend.fontsize": 15,
                         "text.color": "#354650", "axes.labelcolor": "#354650",
                         "mathtext.fontset": "dejavusans", "pdf.fonttype": 42,
                         "ps.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.7))
    fig.subplots_adjust(left=.075, right=.985, bottom=.155, top=.72, wspace=.25)
    for i, (ax, spec) in enumerate(zip(axes, profiles)):
        for p, (color, ls) in zip(PERCENTILES, STYLES):
            ax.plot(elevation, curves[(spec["height_m"], p)], color=color,
                    linestyle=ls, linewidth=2.1, label=f"P{int(p*100)}")
        ax.set_xlim(0, 90)
        ax.set_xlabel("Eleva\u00e7\u00e3o do sat\u00e9lite (\u00b0)", labelpad=9)
        ax.set_ylabel("Perda por clutter (dB)", labelpad=7)
        environment = "low-rise" if spec["environment"] == "low" else "mid-rise"
        ax.set_title(f"({chr(97+i)}) FS: {spec['height_m']} m | {environment}",
                     fontsize=17, pad=38, fontweight="medium")
        ax.text(.5, 1.045, f"Abaixo das coberturas: {spec['below_rooftop_percent']}%",
                transform=ax.transAxes, ha="center", fontsize=14)
        style_axes(ax)
    axes[0].set_ylim(-1.4, 26)
    axes[0].yaxis.set_major_locator(MultipleLocator(5))
    axes[0].yaxis.set_minor_locator(MultipleLocator(1))
    axes[1].set_ylim(-.65, .05)
    axes[1].yaxis.set_major_locator(MultipleLocator(.1))
    axes[1].yaxis.set_minor_locator(MultipleLocator(.05))
    # The full left axis retains the near-horizon NLoS branch. This enlargement
    # makes the other percentiles legible without a logarithmic or clipped axis.
    inset = axes[0].inset_axes([.35, .38, .60, .50])
    for p, (color, ls) in zip(PERCENTILES, STYLES):
        inset.plot(elevation, curves[(20, p)], color=color, linestyle=ls, linewidth=1.7)
    inset.set(xlim=(10, 90), ylim=(-.65, .05))
    inset.set_title("Amplia\u00e7\u00e3o pr\u00f3xima de 0 dB", fontsize=12, pad=7)
    inset.yaxis.set_major_locator(MultipleLocator(.2))
    style_axes(inset, small=True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .995),
               ncol=3, frameon=False, title="Percentis antes da sele\u00e7\u00e3o de enlaces | f = 2 155 MHz",
               title_fontsize=15, handlelength=3.0, columnspacing=2.8)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(match=Text):
        if not text.get_visible() or not text.get_text():
            continue
        if text in [t for ax in [*axes, inset] for t in ax.get_xticklabels()+ax.get_yticklabels()]:
            continue
        b = text.get_window_extent(renderer)
        assert fig.bbox.contains(b.x0, b.y0) and fig.bbox.contains(b.x1, b.y1), text.get_text()
    stem = out / "fig_clutter_p2108"
    fig.savefig(stem.with_suffix(".png"), dpi=450, facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white",
                metadata={"Title": "Clutter espacial: implementacao SHARC",
                          "Subject": "Quantis antes da selecao below_rooftop"})
    fig.savefig(out / "fig_clutter_p2108_preview.png", dpi=140, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figuras")
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    profiles, checked, sources = read_profiles()
    before = {str(p.relative_to(ROOT)): digest(p) for p in sources}
    model = PropagationClutterLoss(np.random.RandomState(SEED))
    checks = validate(model, profiles)
    # Resolve the narrow low-elevation transitions without smoothing the model.
    elevation = np.linspace(0, 90, 18001)
    curves, rows, samples, ranges = {}, [], [], []
    for spec in profiles:
        for p in PERCENTILES:
            values = loss(model, elevation, p, spec)
            assert np.isfinite(values).all()
            curves[(spec["height_m"], p)] = values
            rows.append(np.column_stack((np.full_like(elevation, spec["height_m"]),
                                         np.full_like(elevation, p*100), elevation, values)))
            selected = np.array([0., 1., 2., 5., 10., 30., 60., 90.])
            samples.append(dict(height_m=spec["height_m"], percentile=p*100,
                                elevation_deg=selected.tolist(),
                                loss_db=loss(model, selected, p, spec).tolist()))
            ranges.append(dict(height_m=spec["height_m"], percentile=p*100,
                               minimum_db=float(values.min()), maximum_db=float(values.max()),
                               positive_increments=int(np.sum(np.diff(values)>1e-10))))
    plot(profiles, elevation, curves, out)
    np.savetxt(out / "fig_clutter_p2108_curvas.csv", np.vstack(rows), delimiter=",",
               header="fs_height_m,percentile_percent,elevation_deg,conditional_clutter_db",
               comments="", fmt="%.10g")
    assert before == {str(p.relative_to(ROOT)): digest(p) for p in sources}
    report = dict(profiles=profiles, checked_existing_inputs=checked, validations=checks,
                  samples=samples, ranges=ranges, git_commit=git("rev-parse", "HEAD"),
                  source_sha256=before, script_sha256=digest(Path(__file__)),
                  numpy=np.__version__, scipy=scipy.__version__, matplotlib=matplotlib.__version__,
                  python=sys.version, validation_seed=SEED, model_unchanged=True,
                  curve_definition="get_spatial_clutter_loss before below_rooftop mask",
                  percentiles_are_non_exceedance=True, negative_values_retained=True,
                  revision_2026_equivalence="Not certified: exact source document not available",
                  mask_rule="round(N * below_rooftop / 100) links selected without replacement",
                  figure_units="MHz input, metres, degrees, probability fraction; output dB")
    (out / "fig_clutter_p2108_validacao.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked_inputs": checked, "checks": checks, "ranges": ranges,
                      "output": str(out / "fig_clutter_p2108.png")}, indent=2))


if __name__ == "__main__":
    main()
