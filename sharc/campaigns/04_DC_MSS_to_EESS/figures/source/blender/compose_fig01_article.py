"""Add publication-quality 2D typography to the Blender Fig. 1 render."""
from __future__ import annotations

import csv
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
FIGURES = HERE.parents[1]
BASE = HERE / "fig01_scenario_reassociation_blender_base.png"
EVENT = FIGURES / "data" / "fig01_representative_event.csv"
OUT = FIGURES / "final" / "fig01_scenario_reassociation.png"
FONT_REGULAR = Path(r"C:\Windows\Fonts\times.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\timesbd.ttf")

BLUE = "#0072B2"
VERMILLION = "#D55E00"
GREEN = "#009E73"
ORANGE = "#E69F00"
CYAN = "#0099A8"
INK = "#173042"
GRAY = "#5B6770"


def font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def card(draw, box, *, fill=(255, 255, 255, 235), outline=(31, 56, 72, 75), radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def leader(draw, start, end, color, width=5):
    elbow = (start[0] + (end[0] - start[0]) * 0.55, start[1])
    draw.line([start, elbow, end], fill=color, width=width, joint="curve")
    r = width + 2
    draw.ellipse((end[0] - r, end[1] - r, end[0] + r, end[1] + r), fill=color)


def main():
    with EVENT.open(newline="", encoding="utf-8") as stream:
        event = next(csv.DictReader(stream))
    image = Image.open(BASE).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Header: title stays outside the 3D geometry, like a journal graphical plate.
    draw.text((105, 70), "Interference-Aware Inter-Satellite Handover",
              font=font(64, True), fill=INK)
    draw.text((108, 145), "Realized campaign geometry - same service cell preserved",
              font=font(38), fill=GRAY)
    scenario = f"Snapshot {int(float(event['snapshot_id']))}  |  {event['scenario']}  |  GB = 10 MHz"
    card(draw, (2560, 68, 3475, 175), fill=(246, 249, 251, 240))
    draw.text((2600, 96), scenario, font=font(34, True), fill=INK)

    # Physical entities. Leaders terminate on rendered objects, not invented positions.
    card(draw, (165, 445, 975, 595))
    draw.ellipse((205, 485, 245, 525), fill=CYAN)
    draw.text((270, 468), f"Target satellite {int(float(event['target_satellite_idx']))}",
              font=font(43, True), fill=INK)
    draw.text((270, 520), "eligible alternative for the same cell", font=font(31), fill=GRAY)
    leader(draw, (975, 530), (1250, 765), CYAN)

    card(draw, (2505, 565, 3445, 715))
    draw.ellipse((2545, 605, 2585, 645), fill=VERMILLION)
    draw.text((2610, 587), f"Serving satellite {int(float(event['current_satellite_idx']))}",
              font=font(43, True), fill=INK)
    draw.text((2610, 640), "dominant interfering link before V2", font=font(31), fill=GRAY)
    leader(draw, (2505, 650), (2000, 875), VERMILLION)

    card(draw, (2520, 1185, 3455, 1335))
    draw.ellipse((2560, 1225, 2600, 1265), fill=GREEN)
    draw.text((2625, 1207), "EESS earth station - Paraguay",
              font=font(42, True), fill=INK)
    draw.text((2625, 1260), "realized pointing used in this snapshot", font=font(31), fill=GRAY)
    leader(draw, (2520, 1270), (1917, 1127), GREEN)

    card(draw, (2460, 1435, 3375, 1585))
    draw.ellipse((2500, 1475, 2540, 1515), fill=BLUE)
    draw.text((2565, 1457), f"Service cell {int(float(event['service_cell_id']))}",
              font=font(42, True), fill=INK)
    draw.text((2565, 1510), "cell identity and position are unchanged", font=font(31), fill=GRAY)
    leader(draw, (2460, 1515), (1887, 1107), BLUE)

    # Compact geometry annotations.
    card(draw, (2350, 820, 3430, 1100), fill=(255, 255, 255, 228))
    draw.text((2400, 855), "Angular coupling in the original link", font=font(38, True), fill=INK)
    draw.text((2410, 920), f"ψTX = {float(event['current_tx_offaxis_deg']):.2f}°",
              font=font(44, True), fill=VERMILLION)
    draw.text((2780, 920), f"ψRX = {float(event['current_rx_offaxis_deg']):.2f}°",
              font=font(44, True), fill=GREEN)
    draw.text((2410, 990), "TX beam-to-EESS", font=font(30), fill=GRAY)
    draw.text((2780, 990), "EESS boresight-to-satellite", font=font(30), fill=GRAY)
    leader(draw, (2350, 1015), (1985, 973), GREEN, width=4)

    card(draw, (2360, 235, 3450, 480), fill=(255, 255, 255, 232))
    draw.text((2410, 270), "Physical candidate evaluation", font=font(39, True), fill=INK)
    draw.text((2410, 332),
              f"Link interference: {float(event['current_i_dbw_per_mhz']):.1f} → "
              f"{float(event['target_i_dbw_per_mhz']):.1f} dBW/MHz",
              font=font(35), fill=VERMILLION)
    draw.text((2410, 393),
              f"Predicted reduction: {float(event['predicted_reduction_db']):.1f} dB",
              font=font(37, True), fill=INK)

    draw.text((1180, 260), "INTER-SATELLITE REASSOCIATION",
              font=font(39, True), fill=ORANGE)
    draw.text((2090, 690), "Realized EESS boresight", font=font(32, True), fill=GREEN)

    # Bottom legend uses color + line style so the figure remains readable in grayscale.
    card(draw, (120, 1840, 3480, 2020), fill=(255, 255, 255, 238), radius=18)
    entries = [
        (BLUE, "Serving satellite → service cell", False),
        (CYAN, "Candidate → same service cell", True),
        (VERMILLION, "Interference path toward EESS", False),
        (GREEN, "EESS boresight", False),
        (ORANGE, "Reassociation decision", False),
    ]
    x_positions = [170, 810, 1475, 2250, 2820]
    for x, (color, label, dashed) in zip(x_positions, entries):
        if dashed:
            for dx in range(0, 115, 28):
                draw.line((x + dx, 1895, x + dx + 15, 1895), fill=color, width=7)
        else:
            draw.line((x, 1895, x + 110, 1895), fill=color, width=7)
        draw.text((x, 1920), label, font=font(28), fill=INK)
    draw.text((2170, 1980),
              "Satellite ranges enlarged uniformly for visibility; realized angular geometry is preserved.",
              font=font(27), fill=GRAY)

    result = Image.alpha_composite(image, overlay).convert("RGB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.save(OUT, format="PNG", optimize=True, compress_level=9)
    print(OUT)


if __name__ == "__main__":
    main()
