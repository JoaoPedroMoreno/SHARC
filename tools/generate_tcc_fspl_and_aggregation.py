"""Scientific FSPL graph and linear-power aggregation diagram for the TCC.

Run with SHARC dependencies: python tools/generate_tcc_fspl_and_aggregation.py
Additional 0-90 degree FSPL only: add --horizon-only (preserves older figures).
Only writes new figure artifacts. Does not execute or modify any campaign.
"""
from pathlib import Path
import argparse
import hashlib
import json
import logging
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
import yaml

from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.satellite.ngso.constants import EARTH_RADIUS_M
from sharc.satellite.utils.sat_utils import calc_elevation

BLUE, INK, GRAY = "#287499", "#354650", "#77858e"
CONFIG = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml"
SOURCES = [CONFIG, ROOT / "sharc/satellite/ngso/constants.py",
           ROOT / "sharc/satellite/utils/sat_utils.py",
           ROOT / "sharc/propagation/propagation_free_space.py",
           ROOT / "sharc/cochannel_handover.py"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slant_range(elevation_deg, altitude_m, receiver_altitude_m):
    """Positive ray/sphere intersection measured from the receiver, in metres."""
    r = EARTH_RADIUS_M + receiver_altitude_m
    rs = EARTH_RADIUS_M + altitude_m
    sin_e = np.sin(np.radians(elevation_deg))
    # Rationalized form avoids subtracting two large nearby quantities.
    return (rs**2-r**2)/(np.sqrt(rs**2-r**2+(r*sin_e)**2)+r*sin_e)


def save(fig, out, name):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ticks = [t for ax in fig.axes for t in ax.get_xticklabels()+ax.get_yticklabels()]
    for text in fig.findobj(match=Text):
        if not text.get_visible() or not text.get_text() or text in ticks:
            continue
        b = text.get_window_extent(renderer)
        assert fig.bbox.contains(b.x0, b.y0) and fig.bbox.contains(b.x1, b.y1), text.get_text()
    for extension in ("png", "pdf"):
        fig.savefig(out / f"{name}.{extension}", dpi=450, facecolor="white")
    fig.savefig(out / f"{name}_preview.png", dpi=140, facecolor="white")
    plt.close(fig)


def fspl_figure(out, cfg, minimum_elevation=5):
    assert minimum_elevation in (0, 5)
    horizon = minimum_elevation == 0
    name = "fig_fspl_elevacao_leo" + ("_0a90" if horizon else "")
    frequency = cfg["single_earth_station"]["frequency"]
    ground = cfg["imt"]["topology"]["central_altitude"]
    antenna_height = cfg["single_earth_station"]["geometry"]["height"]
    receiver = ground + antenna_height
    mss = cfg["imt"]["topology"]["mss_dc"]
    visibility = mss["sat_is_active_if"]["minimum_elevation_from_es"]
    service = mss["beam_positioning"]["service_grid"]["minimum_service_angle"]
    assert (frequency, ground, antenna_height, visibility, service) == (2155, 200, 20, 5, 32)
    model = PropagationFreeSpace(np.random.RandomState(0))
    elevations = np.unique(np.r_[np.linspace(minimum_elevation, 90,
                                int((90-minimum_elevation)*20)+1), service])
    fig, ax = plt.subplots(figsize=(10.2, 6.4))
    fig.subplots_adjust(left=.105, right=.97, top=.96, bottom=.22)
    samples, data, validations = [], [], []
    for height, color, ls in ((340, BLUE, "-"), (525, INK, "--")):
        d = slant_range(elevations, height*1000, receiver)
        loss = model.get_free_space_loss(frequency, d)
        np.testing.assert_allclose(loss, 32.45+20*np.log10(frequency)+20*np.log10(d/1000), atol=1e-12)
        np.testing.assert_allclose(d[-1], height*1000-receiver, atol=1e-8)
        assert np.all(np.diff(d)<0) and np.all(np.diff(loss)<0)
        # Independent Cartesian reconstruction and SHARC elevation calculation.
        r = EARTH_RADIUS_M + receiver
        x = r+d*np.sin(np.radians(elevations))
        y = d*np.cos(np.radians(elevations))
        np.testing.assert_allclose(np.hypot(x, y), EARTH_RADIUS_M+height*1000, atol=1e-7)
        longitudes = np.degrees(np.arctan2(y, x))
        # calc_elevation does not clip its acos argument at the exact zenith.
        back = calc_elevation(np.zeros_like(y[:-1]), np.zeros_like(y[:-1]),
                              np.zeros_like(y[:-1]), longitudes[:-1],
                              sat_height=height*1000, es_height=receiver)
        np.testing.assert_allclose(back, elevations[:-1], atol=2e-6, rtol=0)
        ax.plot(elevations, loss, color=color, ls=ls, lw=2.4, label=f"{height} km")
        key_e = np.array([0., 5., 32., 90.] if horizon else [5., 32., 90.])
        key_d = slant_range(key_e, height*1000, receiver)
        key_loss = model.get_free_space_loss(frequency, key_d)
        ax.plot(key_e, key_loss, "o", color=color, ms=5, clip_on=False)
        for e, ds, l in zip(key_e, key_d, key_loss):
            samples.append(dict(altitude_km=height, elevation_deg=float(e),
                                slant_range_km=float(ds/1000), fspl_db=float(l)))
        data.append(np.column_stack((np.full_like(elevations, height), elevations, d/1000, loss)))
        loss40 = model.get_free_space_loss(frequency, slant_range(elevations, height*1000, ground+40))
        validation = dict(altitude_km=height,
                                max_elevation_roundtrip_error_deg=float(np.max(np.abs(back-elevations[:-1]))),
                                max_fs_height_20_to_40_difference_db=float(np.max(np.abs(loss40-loss))),
                                fspl_5_minus_90_db=float(key_loss[key_e == 5][0]-key_loss[-1]))
        if horizon:
            np.testing.assert_allclose(d[0], np.sqrt((EARTH_RADIUS_M+height*1000)**2-r**2), atol=1e-8)
            validation["fspl_0_minus_5_db"] = float(key_loss[0]-key_loss[1])
            validation["horizon_distance_verified"] = True
        validations.append(validation)
    ax.set(xlim=(minimum_elevation, 90), ylim=(148, 170))
    if horizon:
        ax.axvspan(0, 5, color="#dbeaf3", alpha=.8, zorder=0)
        ax.text(2.5, 155, "Abaixo do filtro de 5\u00b0", rotation=90,
                ha="center", va="center", fontsize=12.5, color=INK)
    ax.set_xlabel("\u00c2ngulo de eleva\u00e7\u00e3o (\u00b0)", labelpad=10)
    ax.set_ylabel("Perda em espa\u00e7o livre (dB)", labelpad=10)
    ax.set_xticks(([0] if horizon else []) + [5, 15, 32, 45, 60, 75, 90])
    ax.xaxis.set_minor_locator(MultipleLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(4))
    ax.yaxis.set_minor_locator(MultipleLocator(1))
    ax.set_axisbelow(True)
    ax.grid(which="major", color="#d9e0e4", lw=.8)
    ax.grid(which="minor", color="#edf0f2", lw=.5)
    for angle, caption in ((5, "5\u00b0: visibilidade inicial"), (32, "32\u00b0: atendimento")):
        ax.axvline(angle, color=GRAY, ls=":", lw=1.3, zorder=3, clip_on=False)
        ax.text(angle+1.2, 169.4, caption, fontsize=13.5, ha="left", va="top", color=INK)
    ax.legend(title="Altitude orbital | f = 2 155 MHz", loc="upper right",
              bbox_to_anchor=(.985, .91), frameon=True, fancybox=False,
              facecolor="white", edgecolor="#d9e0e4", fontsize=15, title_fontsize=14)
    ax.annotate("Z\u00eanite", xy=(90, samples[-1]["fspl_db"]), xytext=(79, 158),
                fontsize=14, color=INK, arrowprops=dict(arrowstyle="-", color=GRAY, lw=.8))
    for spine in ax.spines.values():
        spine.set_color(INK)
    fig.text(.535, .045,
             "5\u00b0 e 32\u00b0: refer\u00eancias geom\u00e9tricas do DC-MSS-IMT,\n"
             "n\u00e3o limiares universais de recep\u00e7\u00e3o do FS.",
             ha="center", va="center", fontsize=13.5, linespacing=1.5)
    save(fig, out, name)
    np.savetxt(out / f"{name}_curvas.csv", np.vstack(data), delimiter=",",
               header="altitude_km,elevation_deg,slant_range_km,fspl_db", comments="", fmt="%.10g")
    return dict(earth_radius_m=EARTH_RADIUS_M, frequency_mhz=frequency,
                receiver_ground_altitude_m=ground, receiver_antenna_height_m=antenna_height,
                minimum_elevation_deg=minimum_elevation, samples=samples, tests=validations)


def aggregation_figure(out):
    fig, ax = plt.subplots(figsize=(12.8, 6.0))
    fig.subplots_adjust(left=.015, right=.985, bottom=.025, top=.975)
    ax.set(xlim=(0, 20), ylim=(0, 9))
    ax.axis("off")
    containment = []

    def box(x, y, w, h, *, inactive=False):
        patch = Rectangle((x, y), w, h, linewidth=1.1, edgecolor="#bbc2c7" if inactive else INK,
                          facecolor="#f4f5f6" if inactive else "white", zorder=3)
        ax.add_patch(patch)
        return patch

    def text(x, y, value, size=17, color=INK, **kwargs):
        return ax.text(x, y, value, fontsize=size, color=color, ha="center", va="center", zorder=4, **kwargs)

    def contained(patch, *labels):
        containment.extend((patch, label) for label in labels)

    def arrow(a, b, color=BLUE):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=13,
                                    linewidth=1.2, color=color, shrinkA=0, shrinkB=0, zorder=2))

    text(3.45, 8.7, "Contribui\u00e7\u00f5es recebidas no FS", size=18, color=BLUE)
    text(1.575, 8.12, "Feixe cocanal", size=16)
    text(5.1, 8.12, "Convers\u00e3o dBm \u2192 mW", size=16)
    rows = [(1, 7.15), (2, 5.72), (3, 4.29), (4, 2.86), ("n", 1.43)]
    center = np.array([9.0, 4.29])
    radius = .57
    for j, y in rows:
        inactive = j == 4
        color = GRAY if inactive else BLUE
        first = box(.25, y-.55, 2.65, 1.1, inactive=inactive)
        title = "Outros ativos" if j == "n" else ("Feixe 4" if inactive else f"Feixe {j} ativo")
        contained(first, text(1.575, y+.22, title, size=16, color=color),
                  text(1.575, y-.22, "Inativo" if inactive else rf"$I_{{{j}}}$ (dBm)",
                       size=14 if inactive else 17, color=color))
        second = box(3.3, y-.55, 3.6, 1.1, inactive=inactive)
        value = r"$i_4=0\ \mathrm{mW}$" if inactive else rf"$i_{{{j}}}=10^{{I_{{{j}}}/10}}\ \mathrm{{mW}}$"
        contained(second, text(5.1, y, value, size=18, color=color))
        arrow((2.9, y), (3.3, y), color)
        if not inactive:
            start = np.array([6.9, y])
            vector = center-start
            endpoint = center-radius*vector/np.linalg.norm(vector)
            arrow(start, endpoint, BLUE)
    # Only active beams have connectors into the summation node.
    text(9.0, 7.45, "SOMA EM\nESCALA LINEAR", size=18, color=BLUE, linespacing=1.4)
    circle = Circle(center, radius, facecolor="white", edgecolor=BLUE, linewidth=1.5, zorder=3)
    ax.add_patch(circle)
    text(*center, r"$\Sigma$", size=29, color=BLUE)
    text(10.4, 2.3, r"$i_{\mathrm{agg}}=\sum_{j\in\mathcal{A}}i_j$", size=19, color=BLUE)
    text(10.4, 1.5, "Pot\u00eancia em mW", size=16)
    text(10.4, .9, r"$\mathcal{A}$: feixes ativos", size=15)
    arrow((9.57, 4.29), (11.1, 4.29))
    text(10.3, 4.7, r"$i_{\mathrm{agg}}$", size=17, color=BLUE)

    logbox = box(11.1, 3.12, 4.0, 2.34)
    contained(logbox,
              text(13.1, 5.02, "Retorno a dBm", size=17, color=BLUE),
              text(13.1, 4.18, r"$I_{\mathrm{agg}}=10\log_{10}\!\left(\frac{i_{\mathrm{agg}}}{1\,\mathrm{mW}}\right)$", size=17),
              text(13.1, 3.48, "(dBm)", size=16))
    arrow((15.1, 4.29), (15.7, 4.29))
    inrbox = box(15.7, 3.12, 4.05, 2.34)
    contained(inrbox,
              text(17.725, 5.02, "INR no receptor FS", size=17, color=BLUE),
              text(17.725, 4.35, r"$\mathrm{INR}_{\mathrm{dB}}=$", size=19),
              text(17.725, 3.66, r"$I_{\mathrm{agg,dBm}}-N_{\mathrm{FS,dBm}}$", size=19))
    noise = box(15.7, .55, 4.05, 1.35)
    contained(noise, text(17.725, 1.43, "Ru\u00eddo do FS", size=17),
              text(17.725, .91, r"$N_{\mathrm{FS,dBm}}$", size=19, color=BLUE))
    arrow((17.725, 1.9), (17.725, 3.12), INK)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for patch, label in containment:
        b, t = patch.get_window_extent(renderer), label.get_window_extent(renderer)
        assert b.contains(t.x0-3, t.y0-3) and b.contains(t.x1+3, t.y1+3), label.get_text()
    save(fig, out, "fig_agregacao_interferencia_fs")
    # Algebra/unit checks only, not data plotted or simulation samples.
    dbm = np.array([-100., -103., -107.])
    linear = 10**(dbm/10)
    summed = linear.sum()
    aggregate = 10*np.log10(summed)
    noise_dbm = -105.
    np.testing.assert_allclose(aggregate-noise_dbm, 10*np.log10(summed/10**(noise_dbm/10)))
    np.testing.assert_allclose(10*np.log10(2*10**(-100/10)), -100+10*np.log10(2))
    assert summed+0 == summed
    assert aggregate > dbm.max()
    return dict(sum_in_linear_units=True, inactive_contribution_mw=0,
                logarithmic_and_linear_inr_agree=True, numeric_example_plotted=False,
                zero_total_convention="Iagg and INR are -infinity dB for positive receiver noise")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figuras")
    parser.add_argument("--horizon-only", action="store_true",
                        help="Generate only the additional 0-90 degree FSPL figure")
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    before = {str(p.relative_to(ROOT)): sha(p) for p in SOURCES}
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16,
                         "axes.labelsize": 18, "text.color": INK,
                         "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                         "mathtext.fontset": "dejavusans", "pdf.fonttype": 42, "ps.fonttype": 42})
    report = {"fspl": fspl_figure(out, cfg, minimum_elevation=0 if args.horizon_only else 5)}
    if not args.horizon_only:
        report["aggregation"] = aggregation_figure(out)
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in SOURCES}
    report.update(source_sha256=before, script_sha256=sha(Path(__file__)),
                  git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  numpy=np.__version__, matplotlib=matplotlib.__version__, python=sys.version,
                  simulations_executed=False, source_files_unchanged=True)
    report_name = "fig_fspl_elevacao_leo_0a90_validacao.json" if args.horizon_only else "fig_fspl_agregacao_validacao.json"
    (out / report_name).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["fspl"], indent=2))


if __name__ == "__main__":
    main()
