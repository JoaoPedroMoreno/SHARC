import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.special import jn, jn_zeros


def taylor_gain(theta_deg, frequency_mhz, bandwidth_mhz, slr_db, n_side_lobes, l_r, l_t):
    speed_of_light = 299792458.0
    num_bessel_roots = 3
    lamb = (speed_of_light / 1e6) / (frequency_mhz - bandwidth_mhz / 2)

    theta = np.abs(np.radians(theta_deg))
    phi = np.zeros_like(theta)

    a = (1 / np.pi) * np.arccosh(10 ** (slr_db / 20))
    j1_roots = jn_zeros(1, n_side_lobes) / np.pi
    sigma = j1_roots[-1] / np.sqrt(a ** 2 + (n_side_lobes - 0.5) ** 2)
    mu = jn_zeros(1, num_bessel_roots) / np.pi

    u = (np.pi / lamb) * np.sqrt(
        (l_r * np.sin(theta) * np.cos(phi)) ** 2
        + (l_t * np.sin(theta) * np.sin(phi)) ** 2
    )

    v = np.ones(u.shape + (num_bessel_roots,))
    for i, ui in enumerate(mu):
        v[..., i] = (
            1 - u ** 2 / (np.pi ** 2 * sigma ** 2 * (a ** 2 + (i + 0.5) ** 2))
        ) / (1 - (u / (np.pi * ui)) ** 2)

    with np.errstate(divide="ignore", invalid="ignore"):
        gain = 20 * np.log10(np.abs((2 * jn(1, u) / u) * np.prod(v, axis=-1)))

    gain = np.nan_to_num(gain, nan=-np.inf)
    gain[u == 0] = 0.0
    return gain


def first_crossing(x, y, target):
    indices = np.where(y <= target)[0]
    if len(indices) == 0:
        return None
    idx = indices[0]
    if idx == 0:
        return x[0]
    x0, x1 = x[idx - 1], x[idx]
    y0, y1 = y[idx - 1], y[idx]
    return x0 + (target - y0) * (x1 - x0) / (y1 - y0)


def main():
    out_dir = Path("figuras")
    out_dir.mkdir(exist_ok=True)

    # Parameters used by the campaign antenna configuration.
    frequency = 2000
    bandwidth = 5
    slr = 20
    n_side_lobes = 2
    l_r = 1.6
    l_t = 1.6

    theta = np.arange(0, 20.01, 0.01)
    gain = taylor_gain(theta, frequency, bandwidth, slr, n_side_lobes, l_r, l_t)
    theta_7db = first_crossing(theta, gain, -7.0)

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.labelsize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.linewidth": 0.75,
    })

    fig, ax = plt.subplots(figsize=(3.5, 2.45), dpi=600)
    ax.plot(theta, gain, color="black", linestyle="-", linewidth=1.4, label=r"ITU-R S.1528 Taylor")

    ax.axhline(-7, color="#b00020", linestyle="--", linewidth=1.0, label="-7 dB")
    if theta_7db is not None:
        ax.vlines(theta_7db, -60, -7, color="#b00020", linestyle="--", linewidth=1.0)
        ax.scatter([theta_7db], [-7], color="#b00020", s=16, zorder=4)
        ax.annotate(
            rf"$\theta_{{-7\,\mathrm{{dB}}}}={theta_7db:.3f}^\circ$",
            xy=(theta_7db, -7),
            xytext=(theta_7db + 4, -16),
            arrowprops={"arrowstyle": "->", "color": "#b00020", "linewidth": 0.75},
            color="#b00020",
            fontsize=7,
        )

    ax.set_xlim(0, 20)
    ax.set_ylim(-60, 2)
    ax.set_xlabel(r"Off-axis angle, $\theta$ [deg]")
    ax.set_ylabel(r"Gain relative to $G_{\max}$ [dB]")
    ax.grid(True, which="major", color="0.82", linewidth=0.5)
    ax.grid(True, which="minor", color="0.90", linewidth=0.3)
    ax.minorticks_on()
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="black")
    ax.text(
        0.04,
        0.08,
        r"$f=2000$ MHz, $B=5$ MHz, $l_r=l_t=1.6$ m",
        transform=ax.transAxes,
        fontsize=7,
        bbox={"facecolor": "white", "edgecolor": "0.55", "linewidth": 0.5, "pad": 2.5},
    )

    fig.tight_layout(pad=0.5)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out_dir / f"s1528_taylor_campaign_7db_ieee.{ext}", bbox_inches="tight")

    print(f"theta_7db_deg={theta_7db:.6f}")
    print(f"theta_7db_deg_3dec={theta_7db:.3f}")
    print(out_dir / "s1528_taylor_campaign_7db_ieee.png")


if __name__ == "__main__":
    main()
