"""Create a white review sheet without changing the transparent renders."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parents[1] / "figuras/latincom/antenna_proposal_v2"
VIEWS = (
    ("north_rear_three_quarter", "Rear three-quarter view"),
    ("front_inspection", "Front inspection"),
)


def main():
    sheet = Image.new("RGB", (1700, 1240), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 31)
    for index, (name, title) in enumerate(VIEWS):
        source = Image.open(OUT / f"fs_antenna_{name}.png").convert("RGBA")
        white = Image.new("RGBA", source.size, "white")
        white.alpha_composite(source)
        white.convert("RGB").save(
            OUT / f"fs_antenna_{name}_white.png", dpi=(600, 600)
        )
        bounds = source.getchannel("A").getbbox()
        tile = white.crop(bounds).convert("RGB")
        tile.thumbnail((740, 1080), Image.Resampling.LANCZOS)
        x = index * 850 + (850 - tile.width) // 2
        y = 110 + (1080 - tile.height) // 2
        sheet.paste(tile, (x, y))
        draw.text((index * 850 + 425, 53), title, font=font,
                  fill="#3B4B54", anchor="mm")
    destination = OUT / "fs_antenna_review.png"
    sheet.save(destination, dpi=(600, 600))
    print(destination)


if __name__ == "__main__":
    main()
