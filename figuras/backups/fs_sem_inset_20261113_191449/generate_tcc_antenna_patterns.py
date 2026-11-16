"""Plot the campaign's executable antenna models; never run simulations."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import MultipleLocator, FuncFormatter
import numpy as np
from scipy.optimize import brentq
import yaml

from sharc.antenna.antenna_factory import AntennaFactory
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation

CAMPAIGN = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
CONFIG = CAMPAIGN / "Scripts/base_input.yaml"
OUT = ROOT / "figuras"
BLUE, INK, RED = "#287499", "#354650", "#b34046"


def signature(cfg):
    imt, fs = cfg["imt"], cfg["single_earth_station"]
    return json.dumps([imt["frequency"], imt["bandwidth"], imt["bs"]["antenna"],
                       fs["frequency"], fs["antenna"]], sort_keys=True)


def load_models():
    source = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    paths = list((CAMPAIGN / "input").glob("*.yaml"))
    paths.append(ROOT / "sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/base_input.yaml")
    for path in paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert signature(cfg) == signature(source), f"Different antenna configuration: {path}"
    imt, fs = ParametersImt(), ParametersSingleEarthStation()
    imt.load_parameters_from_file(str(CONFIG))
    fs.load_parameters_from_file(str(CONFIG))
    tx = AntennaFactory.create_antenna(imt.bs.antenna, 0, 0)
    rx = AntennaFactory.create_antenna(fs.antenna, 90, 0)
    return imt, fs, tx, rx, len(paths)


def relative_gain(antenna, angles):
    angles = np.atleast_1d(angles).astype(float)
    return antenna.calculate_gain(off_axis_angle_vec=angles,
                                  theta_vec=np.zeros_like(angles))-antenna.peak_gain


def setup_axes(xmax, ymin, xstep):
    fig, ax = plt.subplots(figsize=(11.8, 7.8))
    fig.subplots_adjust(left=.12, right=.97, bottom=.14, top=.96)
    ax.set(xlim=(0, xmax), ylim=(ymin, 2))
    ax.set_xlabel("\u00c2ngulo fora do eixo (\u00b0)", labelpad=13)
    ax.set_ylabel(r"Ganho relativo a $G_{\max}$ (dB)", labelpad=13)
    ax.xaxis.set_major_locator(MultipleLocator(xstep))
    ax.xaxis.set_minor_locator(MultipleLocator(xstep/5))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:g}".replace(".", ",")))
    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_minor_locator(MultipleLocator(2))
    ax.set_axisbelow(True)
    ax.grid(which="major", color="#d9e0e4", linewidth=.9)
    ax.grid(which="minor", color="#edf0f2", linewidth=.55)
    for spine in ax.spines.values():
        spine.set_color(INK)
        spine.set_linewidth(1.1)
    ax.tick_params(which="major", length=6, width=1, colors=INK)
    ax.tick_params(which="minor", length=3, colors=INK)
    return fig, ax


def save(fig, name):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist in fig.findobj(match=Text):
        if not artist.get_visible() or not artist.get_text():
            continue
        # Locators can create invisible off-axis tick labels beyond the limits.
        if artist in [t for ax in fig.axes for t in ax.get_xticklabels()+ax.get_yticklabels()]:
            continue
        bounds = artist.get_window_extent(renderer)
        assert fig.bbox.contains(bounds.x0, bounds.y0) and fig.bbox.contains(bounds.x1, bounds.y1), artist.get_text()
    fig.savefig(OUT / f"{name}.png", dpi=400, facecolor="white")
    fig.savefig(OUT / f"{name}_preview.png", dpi=120, facecolor="white")
    plt.close(fig)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 17,
                         "axes.labelsize": 19, "legend.fontsize": 17,
                         "text.color": INK, "axes.labelcolor": INK,
                         "mathtext.fontset": "dejavusans"})
    imt, fs, tx, rx, checked = load_models()
    assert tx.frequency_mhz == 2000 and imt.frequency == 2155
    assert tx.bandwidth_mhz == 5 and tx.l_r == tx.l_t == 1.6
    assert tx.peak_gain == 34.1 and rx.peak_gain == 33.1
    assert fs.antenna.itu_r_f_1245_fs.frequency == 2155
    assert relative_gain(tx, 0)[0] == relative_gain(rx, 0)[0] == 0
    theta7 = brentq(lambda x: relative_gain(tx, x)[0]+7, 0, 6)
    theta3 = brentq(lambda x: relative_gain(rx, x)[0]+3, 0, rx.phi_m)
    angles = np.linspace(0, 20, 40001)
    gain = relative_gain(tx, angles)
    assert np.all(np.isfinite(gain))
    np.testing.assert_allclose(gain, tx.calculate_gain(off_axis_angle_vec=angles,
                               theta_vec=np.full_like(angles, 90))-tx.peak_gain, atol=1e-8)

    fig, ax = setup_axes(20, -60, 2.5)
    ax.plot(angles, gain, color=BLUE, lw=2.6, label="DC-MSS-IMT | ITU-R S.1528 Taylor")
    ax.axhline(-7, color=RED, ls=(0, (5, 3)), lw=1.4, label="Contorno de \u22127 dB")
    ax.vlines(theta7, -60, -7, color=RED, ls=(0, (5, 3)), lw=1.3)
    ax.plot(theta7, -7, "o", color=RED, ms=7)
    ax.annotate(r"$\theta_{-7\,\mathrm{dB}} = $"+f"{theta7:.3f}".replace(".", ",")+"\u00b0",
                xy=(theta7, -7), xytext=(7.4, -16), color=RED, fontsize=19,
                arrowprops={"arrowstyle": "-", "color": RED, "lw": 1.2})
    ax.legend(loc="upper right", framealpha=.97, edgecolor="#cbd4da")
    ax.text(.035, .055, "Modelo: f = 2000 MHz; B = 5 MHz\n"
            r"$l_r = l_t = 1{,}6$ m; $G_{\max} = 34{,}1$ dBi",
            transform=ax.transAxes, fontsize=16, linespacing=1.5, va="bottom",
            bbox={"facecolor": "white", "edgecolor": "#cbd4da", "pad": 9})
    save(fig, "fig_diagrama_antena_dc_mss_imt")

    fig, ax = setup_axes(90, -50, 15)
    # Show the forward hemisphere, avoiding the implementation's exact-180 deg boundary.
    angles_fs = np.unique(np.r_[np.linspace(0, 90, 18001), rx.phi_m, 48])
    ax.plot(angles_fs, relative_gain(rx, angles_fs), color=BLUE, lw=2.6,
            label="Receptor FS | ITU-R F.1245")
    ax.legend(loc="upper right", framealpha=.97, edgecolor="#cbd4da")
    detail = ax.inset_axes([.46, .49, .49, .32])
    detail_angles = np.unique(np.r_[np.linspace(0, 10, 4001), rx.phi_m])
    detail.plot(detail_angles, relative_gain(rx, detail_angles), color=BLUE, lw=2)
    detail.set(xlim=(0, 10), ylim=(-23, 1))
    detail.set_xticks([0, 2, 4, 6, 8, 10])
    detail.set_yticks([-20, -10, 0])
    detail.tick_params(labelsize=12, colors=INK)
    detail.grid(color="#e3e8eb", lw=.6)
    detail.set_xlabel("\u00c2ngulo fora do eixo (\u00b0)", fontsize=12, labelpad=3)
    detail.set_ylabel("Ganho relativo (dB)", fontsize=12, labelpad=3)
    detail.hlines(-3, 0, theta3, color=RED, ls="--", lw=1.1)
    detail.vlines(theta3, -23, -3, color=RED, ls="--", lw=1.1)
    detail.plot(theta3, -3, "o", color=RED, ms=4)
    detail.annotate("\u22123 dB: "+f"{theta3:.3f}".replace(".", ",")+"\u00b0",
                    xy=(theta3, -3), xytext=(4.5, -4.5), color=RED, fontsize=12,
                    arrowprops={"arrowstyle": "-", "color": RED, "lw": .8})
    for spine in detail.spines.values():
        spine.set_color("#98a8b2")
    ax.text(.035, .055, "f = 2155 MHz; D = 2 m\n"+r"$G_{\max} = 33{,}1$ dBi",
            transform=ax.transAxes, fontsize=16, linespacing=1.5, va="bottom",
            bbox={"facecolor": "white", "edgecolor": "#cbd4da", "pad": 9})
    save(fig, "fig_diagrama_antena_fs")

    report = {"source": str(CONFIG), "source_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "additional_configs_checked": checked, "no_simulations_run": True,
              "curves": "Direct AntennaFactory instances after SHARC parameter loading; gain minus peak_gain",
              "tx": {"model": imt.bs.antenna.pattern, "channel_frequency_mhz": imt.frequency,
                     "pattern_frequency_mhz": tx.frequency_mhz, "bandwidth_mhz": tx.bandwidth_mhz,
                     "peak_gain_dbi": tx.peak_gain, "l_r_m": tx.l_r, "l_t_m": tx.l_t,
                     "slr_db": tx.slr, "n_side_lobes": tx.n_side_lobes, "theta_minus7_deg": theta7,
                     "plot_range_deg": [0, 20], "vertical_display_limits_db": [-60, 2]},
              "fs": {"model": fs.antenna.pattern, "frequency_mhz": fs.frequency,
                     "diameter_m": fs.antenna.itu_r_f_1245_fs.diameter, "peak_gain_dbi": rx.peak_gain,
                     "diameter_over_wavelength": rx.d_lmbda, "phi_m_deg": rx.phi_m,
                     "theta_minus3_deg": theta3, "plot_range_deg": [0, 90],
                     "inset_range_deg": [0, 10], "vertical_display_limits_db": [-50, 2]},
              "format": "PNG", "dimensions_px": [4720, 3120], "dpi": 400}
    (OUT / "diagramas_antenas_parametros.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
