"""Portuguese, title-free copy of the original LATINCOM border diagram."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text

from latincom_perspective import context


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
TRANSLATIONS = {
    "Paraguay": "Paraguai",
    "Brazil": "Brasil",
    "Border": "Fronteira",
    "FS transmitter": "Transmissor FS",
    "Victim FS receiver": "Receptor FS v\u00edtima",
    "Off-axis radiation": "Radia\u00e7\u00e3o fora do eixo",
    "Main lobes": "Lobos principais",
}


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    fig = context()
    ax = fig.axes[0]
    original_geometry = tuple(tuple(items) for items in
                              (ax.patches, ax.images, ax.lines))
    translated = []
    for artist in list(fig.findobj(match=Text)):
        value = artist.get_text()
        if value == "(a) No power back-off":
            artist.remove()
        elif value in TRANSLATIONS:
            artist.set_text(TRANSLATIONS[value])
            translated.append(value)
        elif value:
            raise ValueError(f"Unexpected label: {value}")
    assert set(translated) == set(TRANSLATIONS)
    assert original_geometry == tuple(tuple(items) for items in
                                      (ax.patches, ax.images, ax.lines))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist in fig.findobj(match=Text):
        if not artist.get_visible() or not artist.get_text():
            continue
        bounds = artist.get_window_extent(renderer)
        assert (bounds.x0 >= 0 and bounds.y0 >= 0 and
                bounds.x1 <= fig.bbox.width and bounds.y1 <= fig.bbox.height), artist.get_text()
    stem = OUT / "fig_interferencia_fronteira_pt"
    fig.savefig(stem.with_suffix(".png"), dpi=320, facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), facecolor="white")
    fig.savefig(OUT / "fig_interferencia_fronteira_pt_preview.png", dpi=100, facecolor="white")
    report = {**fig._latincom_validation, "title": False,
              "translations": TRANSLATIONS, "original_geometry_preserved": True,
              "text_within_canvas": True, "png_pixels": [5120, 2688]}
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plt.close(fig)
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
