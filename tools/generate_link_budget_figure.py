"""Horizontal, vector-first TCC link-budget diagram; no SHARC imports or runs."""
from pathlib import Path
import json

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "figuras/fig_orcamento_enlace_profissional"
WIDTH, HEIGHT = 480, 176
BLUE = HexColor("#1f4e79")
INK = HexColor("#111827")
CHECKS = []


def register_fonts():
    fonts = Path("C:/Windows/Fonts")
    for name, file in (("FigureSans", "arial.ttf"), ("FigureSansBold", "arialbd.ttf"),
                       ("FigureMath", "times.ttf"), ("FigureMathItalic", "timesi.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    pdfmetrics.registerFontFamily("FigureSans", normal="FigureSans", bold="FigureSansBold")
    pdfmetrics.registerFontFamily("FigureMath", normal="FigureMath", italic="FigureMathItalic")


def label(c, text, x, baseline, size=9, *, bold=False, color=INK, center=False):
    font = "FigureSansBold" if bold else "FigureSans"
    c.setFont(font, size)
    c.setFillColor(color)
    width = pdfmetrics.stringWidth(text, font, size)
    left = x - width/2 if center else x
    CHECKS.append(dict(kind="label", text=text, x=left, baseline=baseline, width=width, size=size))
    assert left >= 0 and left+width <= WIDTH, text
    (c.drawCentredString if center else c.drawString)(x, baseline, text)


def symbol(c, markup, x, y, width):
    style = ParagraphStyle("symbol", fontName="FigureMath", fontSize=10.5,
                           leading=13, alignment=1, textColor=BLUE)
    paragraph = Paragraph(markup, style)
    _, height = paragraph.wrap(width, 30)
    assert height <= 13, f"Symbol must fit on one line: {markup}"
    CHECKS.append(dict(kind="symbol", text=markup, x=x, y=y, width=width, height=height))
    paragraph.drawOn(c, x, y)


def arrow(c, x1, y1, x2, y2, color=INK):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(.85)
    if y1 == y2:
        c.line(x1, y1, x2-3.4, y2)
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2-4, y2+2.25)
        p.lineTo(x2-4, y2-2.25)
    else:
        c.line(x1, y1, x2, y2-3.4)
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2-2.25, y2-4)
        p.lineTo(x2+2.25, y2-4)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def group(c, text, left, right):
    label(c, text, (left+right)/2, 146, size=8.7, bold=True, color=BLUE, center=True)
    c.setStrokeColor(BLUE)
    c.setLineWidth(.65)
    c.line(left, 140, right, 140)


def main():
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT.with_suffix(".pdf")), pagesize=(WIDTH, HEIGHT), pageCompression=1)
    c.setTitle("Orcamento de enlace descendente DC-MSS-IMT")
    c.setAuthor("Elaboracao propria")
    c.setFillColor(white)
    c.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    label(c, "Or\u00e7amento de enlace descendente", WIDTH/2, 163,
          size=11.5, bold=True, center=True)
    group(c, "SAT\u00c9LITE / FEIXE b", 10, 202)
    group(c, "ENLACE", 211, 269)
    group(c, "RECEPTOR TERRESTRE (UE)", 278, 470)

    titles = [("Pot\u00eancia", "transmitida", "por feixe"), ("Ganho de", "transmiss\u00e3o"),
              ("EIRP", "direcional"), ("Perdas", "no enlace"),
              ("Ganho de", "recep\u00e7\u00e3o"), ("Pot\u00eancia", "recebida"),
              ("Compara\u00e7\u00e3o", "com ru\u00eddo")]
    symbols = ["<i>P</i><sub>tx,b</sub>", "<i>G</i><sub>tx,b</sub>(&#952;,&#966;)",
               "EIRP<sub>b</sub>(&#952;,&#966;)", "<i>L</i><sub>tot</sub>",
               "<i>G</i><sub>rx</sub>(&#968;)", "<i>P</i><sub>rx</sub>", "SNR"]
    for index, title in enumerate(titles):
        x, y, w, h = 10+67*index, 68, 58, 60
        c.setFillColor(white)
        c.setStrokeColor(INK)
        c.setLineWidth(.85)
        c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
        first_baseline = y+h/2 + (len(title)-1)*6 + 5
        for line_index, line in enumerate(title):
            baseline = first_baseline - 12*line_index
            label(c, line, x+w/2, baseline, size=8.7, bold=True, center=True)
            assert pdfmetrics.stringWidth(line, "FigureSansBold", 8.7) <= w-5, line
        symbol(c, symbols[index], x+2, y+7, w-4)
        if index < 6:
            arrow(c, x+w+1, y+h/2, x+67-1, y+h/2)

    c.setFillColor(white)
    c.setStrokeColor(BLUE)
    c.setLineWidth(.8)
    c.roundRect(360, 12, 110, 30, 3, fill=1, stroke=1)
    label(c, "Ru\u00eddo no receptor", 415, 30, size=8.7,
          bold=True, color=BLUE, center=True)
    symbol(c, "<i>N</i>", 363, 14, 104)
    arrow(c, 441, 43, 441, 67, BLUE)
    c.showPage()
    c.save()

    document = pdfium.PdfDocument(str(OUTPUT.with_suffix(".pdf")))
    page = document[0]
    raster = page.render(scale=600/72).to_pil()
    raster.save(OUTPUT.with_suffix(".png"), dpi=(600, 600))
    preview = page.render(scale=2.5).to_pil()
    preview.save(OUTPUT.with_name(OUTPUT.name + "_preview").with_suffix(".png"))
    page.close()
    document.close()
    reader = PdfReader(str(OUTPUT.with_suffix(".pdf")))
    text = reader.pages[0].extract_text()
    assert len(reader.pages) == 1
    for token in ("EIRP", "SNR", "Ru\u00eddo", "Pot\u00eancia"):
        assert token in text, token
    assert "=" not in text, "Conceptual diagram must not contain equations"
    assert not any(item.get("text", "").isdigit() for item in CHECKS), "No numbered blocks"
    assert not reader.pages[0].images, "PDF should be vector, not a raster screenshot"
    report = dict(page_points=[WIDTH, HEIGHT], png_pixels=list(raster.size), dpi=600,
                  vector_pdf=True, palette=["#1f4e79", "#111827", "#ffffff"],
                  body_font_pt_at_16cm=8.7*(160/25.4*72)/WIDTH,
                  note="Unnumbered conceptual blocks with parameter symbols, without equations.", elements=CHECKS)
    OUTPUT.with_name(OUTPUT.name+"_validation").with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "elements"}, indent=2))


if __name__ == "__main__":
    main()
