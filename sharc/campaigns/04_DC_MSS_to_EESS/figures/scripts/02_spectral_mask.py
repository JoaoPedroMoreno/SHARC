"""Figure 2: exact SpectralMaskMSS transition for GB=10 and GB=5 MHz."""
from __future__ import annotations

from _common import (
    BLUE, DARK, DATA, FINAL, GREEN, PURPLE, SKY, VERMILLION,
    prepare_dirs, save_figure, setup_ieee,
)
import numpy as np
import pandas as pd
from sharc.mask.spectral_mask_mss import SpectralMaskMSS


def sample_mask(center_mhz: float, frequencies: np.ndarray) -> np.ndarray:
    mask = SpectralMaskMSS(center_mhz, 5.0, -13.0)
    mask.set_mask(42.8)
    values = np.full_like(frequencies, mask.mask_dbm[0], dtype=float)
    for index in range(len(mask.freq_lim) - 1, -1, -1):
        values[frequencies < mask.freq_lim[index]] = mask.mask_dbm[index]
        if index == len(mask.delta_f_lim):
            values[frequencies < mask.freq_lim[index]] = mask.p_tx
    return values


def main() -> None:
    prepare_dirs(); setup_ieee()
    frequency = np.arange(2183.0, 2207.001, 0.01)
    gb10 = sample_mask(2187.5, frequency)
    gb5 = sample_mask(2192.5, frequency)
    data = pd.DataFrame({
        "frequency_mhz": frequency,
        "mask_gb10_dbm_per_mhz": gb10,
        "mask_gb5_dbm_per_mhz": gb5,
    })
    data.to_csv(DATA / "fig02_data.csv", index=False)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.1, 3.05))
    ax.plot(frequency, gb10, color=GREEN, label="GB = 10 MHz")
    ax.plot(frequency, gb5, color=VERMILLION, linestyle="--", label="GB = 5 MHz")
    ax.axhline(-13, color=DARK, linestyle=(0, (4, 3)), linewidth=0.9,
               label="Piso espúrio: −13 dBm/MHz")
    ax.axvspan(2200, 2204, color=SKY, alpha=0.20, linewidth=0)
    ax.axvspan(2200, 2206, color=PURPLE, alpha=0.12, linewidth=0)
    ax.text(2200.2, 31.0, "EESS B", color=BLUE, fontsize=7.2)
    ax.text(2204.1, 27.0, "EESS D", color=PURPLE, fontsize=7.2)
    ax.axvline(2200, color=DARK, linewidth=0.7, alpha=0.7)
    ax.annotate("Para GB ≥ 10 MHz, a EESS\npermanece no piso espúrio",
                xy=(2201.0, -13), xytext=(2191.1, -7.0),
                arrowprops={"arrowstyle": "->", "color": GREEN, "lw": 0.8},
                fontsize=7.2, color=GREEN)
    ax.annotate("Em GB = 5 MHz, a EESS entra\nna região de transição/OOB",
                xy=(2200.3, float(sample_mask(2192.5, np.array([2200.3]))[0])),
                xytext=(2195.9, 23.5),
                arrowprops={"arrowstyle": "->", "color": VERMILLION, "lw": 0.8},
                fontsize=7.2, color=VERMILLION)
    ax.text(2199.8, 35.2, "10 MHz após a borda\ndo canal em GB = 10",
            ha="right", va="top", fontsize=6.8, color=DARK)
    ax.set_xlim(2183, 2207)
    ax.set_ylim(-17, 38)
    ax.set_xlabel("Frequência [MHz]")
    ax.set_ylabel("Máscara espectral [dBm/MHz]")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.65)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.legend(loc="lower left", frameon=False, ncol=3)
    save_figure(fig, "fig02_spectral_mask")
    print(DATA / "fig02_data.csv")


if __name__ == "__main__":
    main()
