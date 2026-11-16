"""Vector explanatory figures; never reads or changes simulation results."""
from pathlib import Path
import json
import math

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from PIL import Image
from pypdf import PdfReader
import pypdfium2 as pdfium

OUT = Path(__file__).resolve().parents[1] / "figuras"
W = 600
BLUE = HexColor("#1f4e79")
INK = HexColor("#111827")
GRAY = HexColor("#56616b")
PALE = HexColor("#edf3f7")
RULE = HexColor("#b4c0c9")
ELEMENTS = []


def fonts():
    for name, filename in (("Sans", "arial.ttf"), ("SansBold", "arialbd.ttf")):
        pdfmetrics.registerFont(TTFont(name, f"C:/Windows/Fonts/{filename}"))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="SansBold")


def text(c, value, x, y, size=11, bold=False, color=INK, center=False):
    font = "SansBold" if bold else "Sans"
    width = pdfmetrics.stringWidth(value, font, size)
    left = x-width/2 if center else x
    assert 0 <= left and left+width <= W, value
    assert 0 <= y <= c._pagesize[1]-size, value
    c.setFillColor(color)
    c.setFont(font, size)
    (c.drawCentredString if center else c.drawString)(x, y, value)
    ELEMENTS.append(dict(text=value, x=left, y=y, width=width, size=size))


def rich(c, value, x, y, width, size=11, center=False):
    p = Paragraph(value, ParagraphStyle("label", fontName="Sans", fontSize=size,
                  leading=size*1.3, alignment=1 if center else 0, textColor=INK))
    _, height = p.wrap(width, 200)
    assert height <= size*1.4, value
    p.drawOn(c, x, y)
    ELEMENTS.append(dict(text=value, x=x, y=y, width=width, height=height))


def line(c, x1, y1, x2, y2, color=INK, width=1, dashed=False):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.setDash([4, 3] if dashed else [])
    c.line(x1, y1, x2, y2)
    c.setDash([])


def arrow(c, x1, y1, x2, y2, color=INK):
    angle = math.atan2(y2-y1, x2-x1)
    dx, dy = math.cos(angle), math.sin(angle)
    line(c, x1, y1, x2-4*dx, y2-4*dy, color)
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2-5*dx+2.6*dy, y2-5*dy-2.6*dx)
    p.lineTo(x2-5*dx-2.6*dy, y2-5*dy+2.6*dx)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def box(c, x, y, width, height, fill=white, stroke=INK):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(.9)
    c.roundRect(x, y, width, height, 3, fill=1, stroke=1)


def satellite(c, x, y, width, target):
    path = OUT.parent / "sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/v3/satellite_from_paper.png"
    with Image.open(path) as source:
        height = width * source.height / source.width
    angle = math.atan2(target[0]-x, y-target[1])
    c.saveState()
    c.translate(x, y)
    c.rotate(math.degrees(angle))
    c.drawImage(str(path), -width/2, -height/2, width, height, mask="auto")
    c.restoreState()
    direction = (math.sin(angle), -math.cos(angle))
    feed = (x+.29*height*direction[0], y+.29*height*direction[1])
    ELEMENTS.append(dict(kind="satellite_orientation", center=[x, y],
                         target=target, antenna_direction=direction, angle_deg=math.degrees(angle)))
    return feed


def receiver(c, x, y, draw=True):
    """Same handset design as Latincom's terminal(), at a smaller urban scale."""
    if draw:
        box(c, x-7, y, 14, 24, fill=HexColor("#DDE6EB"), stroke=HexColor("#46525A"))
        c.setFillColor(white)
        c.setStrokeColor(HexColor("#6BA8CA"))
        c.setLineWidth(.55)
        c.rect(x-4.8, y+5.3, 9.6, 15, fill=1, stroke=1)
        c.setFillColor(HexColor("#46525A"))
        c.circle(x, y+2.7, .8, fill=1, stroke=0)
    return (x, y+24)


def urban_obstruction(c, x=215, y=30, width=185, draw=True):
    assets = OUT / "tcc_assets"
    model = json.loads((assets / "urban_obstruction.json").read_text())
    u, v = model["base_uv"]
    left, bottom = x-u*width, y-v*width
    if draw:
        c.drawImage(str(assets / "urban_obstruction.png"), left, bottom, width, width, mask="auto")
    top = (left+model["top_uv"][0]*width, bottom+model["top_uv"][1]*width)
    assert top[1]-y > 3*24, "Buildings must be substantially taller than the handset"
    return top


def new_canvas(name, height, title):
    ELEMENTS.clear()
    c = canvas.Canvas(str(OUT / f"{name}.pdf"), pagesize=(W, height))
    c.setTitle(title)
    c.setAuthor("Elaboracao propria")
    c.setFillColor(white)
    c.rect(0, 0, W, height, fill=1, stroke=0)
    return c


def obstructed_link(c, source, target, color):
    """Use the rendered silhouette to show a hidden path only inside buildings."""
    assets = OUT / "tcc_assets"
    model = json.loads((assets / "urban_obstruction.json").read_text())
    width = 185
    left = 215-model["base_uv"][0]*width
    bottom = 30-model["base_uv"][1]*width
    with Image.open(assets / "urban_obstruction.png") as sprite:
        alpha = sprite.getchannel("A")
        def inside(point):
            px = int((point[0]-left)/width*alpha.width)
            py = int((bottom+width-point[1])/width*alpha.height)
            return (0 <= px < alpha.width and 0 <= py < alpha.height
                    and alpha.getpixel((px, py)) > 220)
        steps = math.ceil(math.dist(source, target)*4)
        points = [(source[0]+(target[0]-source[0])*i/steps,
                   source[1]+(target[1]-source[1])*i/steps)
                  for i in range(steps+1)]
        start, hidden = points[0], inside(points[0])
        segments = []
        for point in points[1:]:
            current = inside(point)
            if current != hidden:
                segments.append((start, point, hidden))
                start, hidden = point, current
        segments.append((start, target, hidden))
    assert any(hidden for _, _, hidden in segments)
    for start, end, hidden in segments:
        c.saveState()
        c.setStrokeColor(color)
        c.setStrokeAlpha(.48 if hidden else 1)
        c.setLineWidth(.7 if hidden else 1)
        c.setDash([2, 2] if hidden else [])
        c.line(*start, *end)
        c.restoreState()


def finish(c, name, required, *, embedded_assets=False):
    c.showPage()
    c.save()
    path = OUT / name
    reader = PdfReader(path.with_suffix(".pdf"))
    assert len(reader.pages) == 1
    assert bool(reader.pages[0].images) == embedded_assets
    extracted = reader.pages[0].extract_text()
    for token in required:
        assert token in extracted, token
    doc = pdfium.PdfDocument(str(path.with_suffix(".pdf")))
    page = doc[0]
    png = page.render(scale=600/72).to_pil()
    png.save(path.with_suffix(".png"), dpi=(600, 600))
    page.render(scale=2).to_pil().save(OUT / f"{name}_preview.png")
    page.close()
    doc.close()
    report = dict(png_pixels=list(png.size), dpi=600, vector_pdf=not embedded_assets,
                  vector_text_and_lines=True, embedded_latincom_assets=embedded_assets,
                  elements=ELEMENTS.copy())
    (OUT / f"{name}_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path.with_suffix(".png"))


def losses():
    name = "esboco_figura2_perdas_enlace"
    c = new_canvas(name, 310, "Componentes das perdas no enlace espaco-Terra")

    # Atmosphere is near Earth, not a uniform absorber over the entire path.
    c.setFillColor(PALE)
    c.rect(18, 30, 306, 133, fill=1, stroke=0)
    line(c, 18, 163, 324, 163, RULE, .7, True)
    text(c, "Atmosfera", 55, 126, 10.5, color=BLUE)
    line(c, 18, 29, 324, 29, GRAY)
    text(c, "Superf\u00edcie terrestre", 28, 14, 10.5, color=GRAY)
    focus = receiver(c, 290, 30, draw=False)
    geo = satellite(c, 52, 240, 80, focus)
    leo = satellite(c, 155, 210, 80, focus)
    obstruction_top = urban_obstruction(c, draw=False)
    urban_obstruction(c)
    for source, color in ((geo, GRAY), (leo, BLUE)):
        at_building = source[1]+(215-source[0])*(focus[1]-source[1])/(focus[0]-source[0])
        assert at_building < obstruction_top[1], "Building must intercept the projected direct path"
        obstructed_link(c, source, focus, color)
    receiver(c, 290, 30)
    text(c, "GEO", 52, 290, 12, True, GRAY, True)
    text(c, "LEO", 155, 245, 12, True, BLUE, True)
    text(c, "UE", 290, 11, 12, bold=True, center=True)

    # Callouts stay outside the drawing; leader lines never cross their text.
    entries = [
        (256, "L<sub>bfs</sub>", "Espa\u00e7o livre", "Dist\u00e2ncia e frequ\u00eancia", (geo[0]+.12*(focus[0]-geo[0]), geo[1]+.12*(focus[1]-geo[1]))),
        (190, "L<sub>atm</sub>", "Atmosfera", "Gases e outras contribui\u00e7\u00f5es", (315, 120)),
        (124, "L<sub>add</sub>", "Ambiente local", "Sombreamento e clutter", (215, obstruction_top[1]-22)),
        (58, "L<sub>pol</sub>", "Polariza\u00e7\u00e3o", "Descasamento entre antenas", focus),
    ]
    for y, sym, heading, subtitle, point in entries:
        box(c, 344, y-29, 238, 46)
        rich(c, sym, 354, y-3, 40, 12)
        text(c, heading, 401, y, 11.5, bold=True)
        text(c, subtitle, 354, y-18, 10.5)
        line(c, 339, y+2, 333, y+2, RULE, .8)
        if sym == "L<sub>bfs</sub>":
            line(c, 333, y+2, 200, y+2, RULE, .8)
            line(c, 200, y+2, point[0], point[1], RULE, .8)
        else:
            line(c, 333, y+2, point[0], point[1], RULE, .8)
    finish(c, name, ["LEO", "GEO", "UE", "clutter", "Polariza\u00e7\u00e3o"], embedded_assets=True)


def bootstrap():
    name = "fig_bootstrap_inr_incerteza"
    c = new_canvas(name, 270, "Intervalo de confianca bootstrap do INR")
    values = [-12, -9, -7, -5, -3]
    draws = [[3, 1, 3, 5, 2], [4, 2, 4, 1, 5]]
    expected = [-7, -5]
    xs = [18, 164, 310, 456]
    for x in xs:
        box(c, x, 14, 126, 242)
    for x in xs[:-1]:
        arrow(c, x+129, 135, x+143, 135)
    text(c, "Snapshots originais", 81, 235, 11.5, True, center=True)
    text(c, "Exemplo fict\u00edcio (dB)", 81, 214, 10, color=GRAY, center=True)
    for i, value in enumerate(values):
        y = 185 - i*28
        text(c, f"Snapshot {i+1}", 28, y, 10.5)
        text(c, str(value), 122, y, 11, center=True, color=BLUE, bold=True)

    text(c, "Reamostragem", 227, 235, 12, True, center=True)
    text(c, "Sorteio aleat\u00f3rio", 227, 214, 10.5, center=True)
    text(c, "com reposi\u00e7\u00e3o", 227, 199, 10.5, center=True)
    text(c, "Estimar INR", 373, 235, 12, True, center=True)
    text(c, "Ordene do maior", 373, 214, 10.5, center=True)
    text(c, "para o menor", 373, 199, 10.5, center=True)
    for number, (ids, estimate) in enumerate(zip(draws, expected)):
        baseline = 167-number*57
        letter = chr(65+number)
        text(c, f"Reamostra {letter}", 227, baseline+16, 10, True, center=True)
        ordered = sorted((values[j-1] for j in ids), reverse=True)
        selected = len(ordered)-math.ceil(.8*len(ordered))
        assert selected == 1 and ordered[selected] == estimate
        for j, snapshot in enumerate(ids):
            x = 174+j*22
            repeated = ids.count(snapshot) > 1
            box(c, x, baseline-10, 19, 20, fill=PALE if repeated else white, stroke=RULE)
            text(c, f"S{snapshot}", x+9.5, baseline-3, 10, bold=repeated, color=BLUE, center=True)
        for j, value in enumerate(ordered):
            x = 324+j*24
            if j == selected:
                c.setFillColor(PALE)
                c.rect(x-10, baseline-10, 20, 20, fill=1, stroke=0)
            text(c, str(value), x, baseline-3, 10.5, bold=j == selected,
                 color=BLUE if j == selected else INK, center=True)
        rich(c, f"{letter}: INR<sub>20</sub> = {estimate} dB", 314, baseline-38, 118, 11, True)
    text(c, "Amostras podem se repetir", 227, 76, 9.8, center=True)
    text(c, "10.000 reamostras", 227, 49, 11, True, BLUE, True)
    text(c, "Percentil 80", 373, 49, 11, True, BLUE, True)

    text(c, "IC de 95%", 519, 235, 12, True, center=True)
    text(c, "Distribui\u00e7\u00e3o das 10.000", 519, 214, 10.1, center=True)
    rich(c, "estimativas de INR<sub>20</sub>", 460, 194, 118, 10.5, True)
    text(c, "(curva ilustrativa)", 519, 177, 9.5, color=GRAY, center=True)
    base, peak, sigma = 116, 45, 17
    lower, upper = 519-1.96*sigma, 519+1.96*sigma
    def curve_y(x):
        return base+peak*math.exp(-.5*((x-519)/sigma)**2)
    shaded = c.beginPath()
    shaded.moveTo(lower, base)
    for i in range(81):
        x = lower+(upper-lower)*i/80
        shaded.lineTo(x, curve_y(x))
    shaded.lineTo(upper, base)
    shaded.close()
    c.setFillColor(PALE)
    c.drawPath(shaded, fill=1, stroke=0)
    curve = c.beginPath()
    for i in range(101):
        x = 469+i
        (curve.moveTo if i == 0 else curve.lineTo)(x, curve_y(x))
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.3)
    c.drawPath(curve)
    line(c, 469, base, 569, base, RULE, .6)
    for x, label in ((lower, "2,5%"), (upper, "97,5%")):
        line(c, x, base, x, curve_y(x)+10, BLUE, .7, True)
        text(c, label, x, 98, 10.5, color=BLUE, center=True)
    text(c, "95%", 519, 130, 10.5, True, BLUE, True)
    text(c, "Esses percentis definem", 519, 67, 10, center=True)
    rich(c, "o IC de 95% do INR<sub>20</sub>", 460, 46, 118, 10.5, True)
    finish(c, name, ["10.000", "2,5%", "97,5%", "reposi\u00e7\u00e3o", "Snapshot 1"])
    (OUT / "bootstrap_exemplo_didatico.json").write_text(json.dumps(dict(
        synthetic=True, values_db=values, example_snapshot_ids=draws,
        example_estimates_db=expected, n_bootstrap=10000,
        ci95_percentiles=[2.5, 97.5], numerical_ci_not_shown=True,
        estimator="Descending order: index N-ceil(0.8*N); N=5: second value",
        curve="Illustrative bell shape only; no normality assumption or normal CI"
    ), indent=2), encoding="utf-8")


if __name__ == "__main__":
    fonts()
    OUT.mkdir(exist_ok=True)
    losses()
    bootstrap()
