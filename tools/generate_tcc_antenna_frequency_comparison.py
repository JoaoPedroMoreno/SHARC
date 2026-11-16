"""Frequency sensitivity of the configured Taylor pattern, without YAML edits."""
from copy import deepcopy
import hashlib
import json

import generate_tcc_antenna_patterns as patterns
from sharc.antenna.antenna_factory import AntennaFactory


def main():
    plt, np = patterns.plt, patterns.np
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 17,
                         "axes.labelsize": 19, "legend.fontsize": 16,
                         "text.color": patterns.INK, "axes.labelcolor": patterns.INK,
                         "mathtext.fontset": "dejavusans"})
    original_hash = hashlib.sha256(patterns.CONFIG.read_bytes()).hexdigest()
    imt, _, current, _, _ = patterns.load_models()
    parameters = deepcopy(imt.bs.antenna)
    parameters.itu_r_s_1528.frequency = imt.frequency
    changed = AntennaFactory.create_antenna(parameters, 0, 0)
    assert current.frequency_mhz == 2000 and changed.frequency_mhz == 2155
    assert current.peak_gain == changed.peak_gain == 34.1
    angles = np.linspace(0, 20, 40001)
    roots = [patterns.brentq(lambda x: patterns.relative_gain(antenna, x)[0]+7, 0, 6)
             for antenna in (current, changed)]

    for comparison in (True, False):
        fig, ax = patterns.setup_axes(20, -60, 2.5)
        if comparison:
            ax.plot(angles, patterns.relative_gain(current, angles), color="#7d858a",
                    ls=(0, (5, 3)), lw=2, label="2000 MHz | configurado na campanha")
        ax.plot(angles, patterns.relative_gain(changed, angles), color=patterns.BLUE,
                lw=2.5, label="2155 MHz | modelo recalculado")
        ax.axhline(-7, color=patterns.RED, ls=(0, (5, 3)), lw=1.3)
        ax.vlines(roots[1], -60, -7, color=patterns.BLUE, ls=(0, (4, 3)), lw=1)
        ax.plot(roots[1], -7, "o", color=patterns.BLUE, ms=6)
        if comparison:
            ax.plot(roots[0], -7, "o", color="#7d858a", ms=6)
        note = "Contorno de \u22127 dB\n"
        if comparison:
            note += f"2000 MHz: {roots[0]:.3f}\u00b0\n".replace(".", ",")
        note += f"2155 MHz: {roots[1]:.3f}\u00b0".replace(".", ",")
        ax.text(7.1, -11.5, note, va="top", fontsize=16, linespacing=1.5,
                color=patterns.BLUE, bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9})
        ax.text(.035, .055, "ITU-R S.1528 Taylor; B = 5 MHz\n"
                r"$l_r = l_t = 1{,}6$ m; $G_{\max} = 34{,}1$ dBi",
                transform=ax.transAxes, fontsize=16, linespacing=1.5,
                bbox={"facecolor": "white", "edgecolor": "#cbd4da", "pad": 9})
        ax.legend(loc="upper right", framealpha=.97, edgecolor="#cbd4da")
        name = "fig_antena_dc_mss_comparacao_frequencia" if comparison else "fig_diagrama_antena_dc_mss_imt_2155MHz"
        patterns.save(fig, name)

    assert hashlib.sha256(patterns.CONFIG.read_bytes()).hexdigest() == original_hash
    report = {"changed_parameter_only": "itu_r_s_1528.frequency: 2000 -> 2155 MHz",
              "yaml_modified": False, "simulations_run": False,
              "peak_gain_held_fixed_dbi": changed.peak_gain,
              "theta_minus7_2000_deg": roots[0], "theta_minus7_2155_deg": roots[1],
              "half_angle_reduction_percent": 100*(1-roots[1]/roots[0])}
    (patterns.OUT / "antena_dc_mss_comparacao_frequencia.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
