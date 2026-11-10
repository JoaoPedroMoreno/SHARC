"""Export Portuguese LATINCOM figures from the unchanged original builders."""
from pathlib import Path
import argparse
import json
import math
import re
import shutil
from PIL import Image, ImageDraw, ImageFont

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text

import generate_latincom_figures as figures
import generate_fs_mitigation_methodology as methodology
import latincom_encom_cover as cover
import latincom_perspective as perspective
import latincom_fs_antenna as antenna

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figuras/latincom/pt_br'
TRANSLATIONS = {
    'DC-MSS / FS coexistence': 'Coexistência DC-MSS / FS',
    'Exclusion zone': 'Zona de exclusão',
    'Conditional power back-off': 'Power back-off condicional',
    'Brazil': 'Brasil',
    'Paraguay': 'Paraguai',
    'Regional service area': 'Área de serviço regional',
    'Brazil / Argentina service area': 'Área de serviço Brasil / Argentina',
    'Nominal-power cell': 'Célula com potência nominal',
    'Power-reduced cell (10 dB)': 'Célula com redução de 10 dB',
    'Excluded cell': 'Célula excluída',
    'Victim FS (Paraguay)': 'FS vítima (Paraguai)',
    'Conventional MSS': 'MSS convencional',
    'Ground gateway': 'Gateway terrestre',
    'Dedicated MSS terminal': 'Terminal MSS dedicado',
    r'Gateway $\rightarrow$ satellite $\rightarrow$ MSS handset':
        r'Gateway $\rightarrow$ satélite $\rightarrow$ terminal MSS',
    'IMT user equipment': 'IMT User Equipment (UE)',
    '(a) No power back-off': '(a) Sem power back-off',
    'Border': 'Fronteira',
    'Victim FS receiver': 'Receptor FS vítima',
    'FS transmitter': 'Transmissor FS',
    'Scenario': 'Cenário',
    'Snapshots and mitigation': 'Snapshots e mitigação',
    'FS assessment': 'Avaliação do FS',
    'System 3': 'Sistema 3',
    'Victim FS': 'FS vítima',
    'Mitigation sweep': 'Variação da mitigação',
    '0 to 100 km': '0 a 100 km',
    'Regional coverage': 'Cobertura regional',
    'Brazil / Argentina': 'Brasil / Argentina',
    'CCDF of INR': 'CCDF da INR',
    'Illustrative': 'Ilustrativa',
    'Compare\nconfigurations': 'Comparação de\nconfigurações',
    'Active': 'Ativa',
    'Inactive': 'Inativa',
    '10 dB back-off': 'Back-off de 10 dB',
    'Excluded': 'Excluída',
    'Interference to FS': 'Interferência no FS',
    'Schematic': 'Esquemático',
    r'1 configuration  $\rightarrow$  10 000 snapshots  $\rightarrow$  FS statistics':
        r'1 configuração  $\rightarrow$  10 000 snapshots  $\rightarrow$  estatísticas do FS',
}
ENGLISH_TERMS = {'Feeder link', 'Service link', 'Transparent / bent-pipe payload',
                 'Direct satellite-to-device link', 'Off-axis radiation', 'Main lobes'}
UNCHANGED = ENGLISH_TERMS | {'Argentina', 'DC-MSS-IMT', 'FS', 'SHARC + Monte Carlo',
                            '340 / 525 km', 'LF 20 / 50%', '20 / 40 m', 'INR (dB)', 'CCDF'}


def localize(fig):
    unknown = set()
    translated = []
    for artist in fig.findobj(match=Text):
        original = artist.get_text()
        if not original:
            continue
        if original in TRANSLATIONS:
            artist.set_text(TRANSLATIONS[original])
            translated.append({'en': original, 'pt': artist.get_text()})
        elif (original not in UNCHANGED and not original.startswith('$')
              and not re.fullmatch(r'[\d .−-]+|Snapshot [\d ]+', original)):
            unknown.add(original)
    if unknown:
        raise ValueError(f'Unmapped labels: {sorted(unknown)}')
    return translated


JOBS = [
    ('latincom_cover', cover.cover,
     'Representação conceitual das estratégias de zona de exclusão e power back-off condicional na coexistência DC-MSS/FS.',
     'Elaboração própria em Python/Matplotlib, com modelos de satélites e antenas renderizados no Blender e base cartográfica Natural Earth.',
     'Composição em Matplotlib, geometrias cartográficas processadas com Shapely e PyProj, e elementos do Blender inseridos como imagens transparentes. As células, feixes e zonas são ilustrativos, sem escala física comum. Não constituem um drop da campanha.'),
    ('latincom_page_2', figures.architecture,
     'Comparação conceitual entre as arquiteturas MSS convencional e DC-MSS-IMT.',
     'Elaboração própria em Python/Matplotlib, com modelo de satélite renderizado no Blender.',
     'O Matplotlib compõe feeder link, service link, células, terminais, antena gateway e textos. O painel DC-MSS-IMT representa User Equipment (UE) do ecossistema IMT. O satélite é uma imagem transparente renderizada no Blender. O gateway desta figura é um desenho em Matplotlib, não o modelo Blender do receptor FS. A comparação é didática, não uma topologia completa de implantação.'),
    ('latincom_page_2A_conventional_mss', lambda: figures.architecture('mss'),
     'Arquitetura conceitual do MSS convencional com gateway terrestre, satélite e terminal MSS dedicado.',
     'Elaboração própria em Python/Matplotlib, com modelo de satélite renderizado no Blender.',
     'O satélite vem de um render transparente do Blender. Gateway, terminal, célula, enlaces bidirecionais e textos são elementos desenhados em Matplotlib. O payload transparente/bent-pipe retransmite o sinal entre feeder link e service link.'),
    ('latincom_page_2B_dc_mss_imt', lambda: figures.architecture('dc'),
     'Representação conceitual da conectividade direta entre satélite DC-MSS-IMT e User Equipment (UE) do ecossistema IMT.',
     'Elaboração própria em Python/Matplotlib, com modelo de satélite renderizado no Blender.',
     'O Matplotlib compõe células, feixes, UEs e textos, incorporando uma imagem transparente do satélite renderizado no Blender. A figura destaca o direct satellite-to-device link, sem pretender representar todos os componentes da rede.'),
    ('latincom_page_3', perspective.context,
     'Geometria conceitual do acoplamento interferente do downlink DC-MSS ao receptor de um enlace FS na fronteira Brasil-Paraguai, sem power back-off.',
     'Elaboração própria em Python/Matplotlib, com modelos de satélite e antenas FS renderizados no Blender.',
     'Plano de solo, células, main lobes, off-axis radiation, enlace FS e anotações são compostos em Matplotlib. Satélite e parabólicas são renders transparentes do Blender. Trata-se de um esquema de acoplamento, não de um mapa quantitativo de potência ou de interferência.'),
    ('latincom_sharc_monte_carlo', methodology.figure,
     'Metodologia de avaliação da interferência no FS por Monte Carlo no SHARC, com zona de exclusão e power back-off condicional.',
     'Elaboração própria em Python/Matplotlib, com modelos de satélites e antenas FS renderizados no Blender.',
     'O Matplotlib compõe os quadros de snapshots, as células, os enlaces, os textos e a curva de CCDF ilustrativa. Satélites e receptores FS são renders transparentes do Blender. Os dois snapshots e a CCDF do esquema são didáticos, não resultados extraídos dos outputs. O número de 10 000 snapshots foi preservado da figura original.'),
    ('latincom_fs_antenna', antenna.figure,
     'Modelo ilustrativo de antena parabólica direcional para receptor de Serviço Fixo.',
     'Elaboração própria, com modelo tridimensional renderizado no Blender e composição em Python/Matplotlib.',
     'A parabólica, o feed horn, o suporte e o mastro pertencem ao modelo Blender aprovado. O Matplotlib posiciona o render transparente e o indicador gráfico de apontamento. Não é uma fotografia de equipamento comercial nem um diagrama de radiação calculado.'),
]
MAP_CAPTIONS = {
    'mapa_zona_exclusao': (
        'Visualização geométrica da constelação DC-MSS e das células de serviço com zona de exclusão em torno do receptor FS.',
        'Elaboração própria no visualizador CesiumJS, com imagens do Bing Maps via Cesium ion e créditos dos provedores indicados na figura.',
        'Captura renderizada pelo CesiumJS/WebGL. A exportação original em JavaScript/Canvas 2D acrescenta título e legenda. Na versão em português, Python/Pillow substitui apenas essas anotações, preservando os pixels da cena e os créditos do rodapé. Não utiliza Matplotlib ou Blender. O cenário ilustrativo usa raio de exclusão de 180 km, conforme o perfil de apresentação existente, e não representa uma distância de conformidade obtida no artigo.'),
    'mapa_power_backoff': (
        'Visualização geométrica da cobertura DC-MSS no Brasil e na Argentina, com destaque das células de fronteira sujeitas ao power back-off.',
        'Elaboração própria no visualizador CesiumJS, com imagens do Bing Maps via Cesium ion e créditos dos provedores indicados na figura.',
        'Captura renderizada pelo CesiumJS/WebGL, com título e legenda originais exportados por JavaScript/Canvas 2D. Na versão em português, Python/Pillow substitui somente essas anotações; a cena e os créditos cartográficos permanecem intactos. Não utiliza Matplotlib ou Blender. A faixa ilustrativa usa pelo menos uma vizinhança de hexágonos, inclusive com YAML de base M0km; não interpretar sua largura visual como resultado numérico de conformidade.'),
}


def translate_map(name):
    """Replace only known annotation rectangles in the final Cesium capture."""
    original = ROOT / 'figuras/latincom/cesium_captures_20261104' / f'{name}.png'
    with Image.open(original) as image:
        image.load()
        output = image.convert('RGB')
    if output.size != (3200, 1840):
        raise ValueError('Unexpected Cesium capture dimensions')
    draw = ImageDraw.Draw(output)
    fonts = Path('C:/Windows/Fonts')
    regular = lambda size: ImageFont.truetype(str(fonts / 'segoeui.ttf'), size)
    bold = lambda size: ImageFont.truetype(str(fonts / 'segoeuib.ttf'), size)
    pbo = name == 'mapa_power_backoff'
    draw.rectangle((0, 0, 3199, 111), fill='white')
    draw.text((52, 55), 'Power back-off condicional' if pbo else 'Zona de exclusão',
              font=bold(44), fill='#263d47', anchor='ls')
    draw.text((54, 91), 'Área de serviço Brasil / Argentina' if pbo else
              'Área de serviço regional na América do Sul',
              font=regular(27), fill='#526570', anchor='ls')
    draw.text((3148, 62), 'Sistema 3 | 340 km | Quadro 1',
              font=regular(27), fill='#526570', anchor='rs')
    x, y, width, height = 2340, 1284, 820, 436
    # An opaque panel prevents the original English glyphs from showing through.
    draw.rectangle((x-1, y-1, x+width+1, y+height+1),
                   fill='#091a24', outline='#75818a', width=2)
    entries = [('active', 'Satélite em serviço'), ('other', 'Outro satélite'),
               ('fs', 'Receptor FS'), ('nominal', 'Célula nominal'),
               ('mitigation', 'Célula com back-off' if pbo else 'Célula excluída')]
    for index, (kind, label) in enumerate(entries):
        cx, cy = x + 60, y + 28 + 76 * (index + .5)
        if kind in ('active', 'other', 'fs'):
            radius = {'active': 15, 'other': 9, 'fs': 18}[kind]
            color = {'active': '#00ff00', 'other': '#29b8bd', 'fs': '#ffffff'}[kind]
            draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                         fill=color, outline='#071219', width=4)
        else:
            points = [(cx+25*math.cos(i*math.pi/3), cy+25*math.sin(i*math.pi/3))
                      for i in range(6)]
            draw.polygon(points, fill='#302d1e' if kind == 'nominal' else
                         '#626d73' if pbo else '#091a24')
            draw.line(points+[points[0]], fill='#ffa500' if kind == 'nominal'
                      else '#ffffff', width=4, joint='curve')
        if draw.textbbox((0, 0), label, font=regular(56))[2] > width-140:
            raise ValueError(f'Legend label too wide: {label}')
        draw.text((x+110, cy), label, font=regular(56), fill='white', anchor='lm')
    output.save(OUT / f'{name}_pt.png')
    output.thumbnail((1600, 920))
    output.save(OUT / 'previews' / f'{name}_pt.png')
    print(f'{name}: translated annotations, original scene preserved', flush=True)


def write_caption(name, title, source, details):
    extra = ''
    if name.startswith('mapa_'):
        extra = ('\n\nLIMITE DA VISUALIZAÇÃO\n'
                 'Os pontos verdes identificam satélites com células associadas no visualizador. '
                 'Os cianos identificam os demais satélites exibidos. As associações geométricas '
                 'não reproduzem o sorteio de atividade LF dos drops Monte Carlo. '
                 'Os envelopes amarelos não representam intensidade de interferência.\n')
    content = (f'LEGENDA SUGERIDA\nFigura X - {title}\n\n'
               f'FONTE SUGERIDA\nFonte: {source}\n\n'
               f'COMO A FIGURA FOI PRODUZIDA\n{details}\n\n'
               'USO NO TCC\nSubstitua X pelo número da figura. A descrição de produção pode '
               'ficar na metodologia ou na lista de recursos utilizados; não precisa ocupar '
               'toda a legenda. A composição autoral não dispensa a atribuição de bases '
               'cartográficas e recursos de terceiros quando presentes.\n' + extra)
    (OUT / f'{name}_pt.txt').write_text(content, encoding='utf-8')


def check_bounds(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    warnings = []
    for text in fig.findobj(match=Text):
        if not text.get_visible() or not text.get_text():
            continue
        bounds = text.get_window_extent(renderer)
        if (bounds.x0 < -1 or bounds.y0 < -1 or
                bounds.x1 > fig.bbox.width + 1 or bounds.y1 > fig.bbox.height + 1):
            warnings.append(text.get_text())
    return warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--maps-only', action='store_true')
    parser.add_argument('--figures', nargs='+', choices=[job[0] for job in JOBS])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'previews').mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'pdf.fonttype': 42,
                         'svg.fonttype': 'none'})
    report = []
    for name, build, title, source, details in JOBS:
        if args.maps_only:
            continue
        if args.figures and name not in args.figures:
            continue
        fig = build()
        labels = localize(fig)
        bounds_warnings = check_bounds(fig)
        if bounds_warnings:
            raise ValueError(f'Text outside {name}: {bounds_warnings}')
        transparent = name == 'latincom_sharc_monte_carlo'
        if not args.preview:
            for ext in ('png', 'pdf', 'svg'):
                alpha = ext == 'png' or transparent
                fig.savefig(OUT / f'{name}_pt.{ext}', dpi=600,
                            transparent=alpha, facecolor='none' if alpha else 'white')
        fig.savefig(OUT / 'previews' / f'{name}_pt.png', dpi=140,
                    transparent=transparent, facecolor='none' if transparent else 'white')
        plt.close(fig)
        write_caption(name, title, source, details)
        report.append({'figure': name, 'translated_labels': labels,
                       'text_outside_canvas': bounds_warnings})
        print(f'{name}: {len(labels)} translated labels', flush=True)
    alias = 'dc_mss_fs_mitigation_methodology'
    original = 'latincom_sharc_monte_carlo'
    if not args.preview and (OUT / f'{original}_pt.png').exists():
        for ext in ('png', 'pdf', 'svg', 'txt'):
            shutil.copy2(OUT / f'{original}_pt.{ext}', OUT / f'{alias}_pt.{ext}')
    for name, caption in MAP_CAPTIONS.items():
        if not args.preview:
            translate_map(name)
        write_caption(name, *caption)
    if report:
        (OUT / 'translation_validation.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'README.txt').write_text(
        'FIGURAS LATINCOM EM PORTUGUÊS\n\n'
        'Cada imagem final tem um TXT de mesmo nome com legenda, fonte e método de produção.\n'
        'Os diagramas têm PNG a 600 dpi, PDF e SVG. Os PDFs/SVGs preservam os elementos '
        'vetoriais, mas incorporam os renders raster de satélites e antenas.\n'
        'Os dois mapas Cesium são PNGs de 3200 x 1840 pixels; não são imagens vetoriais.\n'
        'As versões em inglês foram preservadas. Nenhum resultado científico foi recalculado.\n\n'
        'TERMINOLOGIA\n'
        'Jargões mantidos em inglês: User Equipment (UE), feeder link, service link, '
        'payload, bent-pipe, gateway, direct satellite-to-device link, main lobes, '
        'off-axis radiation, power back-off, snapshot e downlink. '
        'Textos explicativos e nomes dos países permanecem em português.\n\n'
        'REPRODUÇÃO DOS DIAGRAMAS\n'
        '.venv/Scripts/python.exe tools/generate_latincom_portuguese.py\n\n'
        'REPRODUÇÃO DA TRADUÇÃO DOS MAPAS EXISTENTES\n'
        '.venv/Scripts/python.exe tools/generate_latincom_portuguese.py --maps-only\n'
        'Somente os retângulos de cabeçalho e legenda são substituídos.\n\n'
        'NOVA CAPTURA NO SIMULADOR (OPCIONAL)\n'
        '.venv/Scripts/python.exe -m sharc.satellite.ngso.backend.api --port 8000\n'
        'http://127.0.0.1:8000/?profile=presentation&scenario=sa&capture=publication&lang=pt\n'
        'http://127.0.0.1:8000/?profile=presentation&scenario=brarg&capture=publication&lang=pt\n'
        'Clique em Generate PNG após carregar a cena.\n\n'
        'latincom_sharc_monte_carlo_pt e dc_mss_fs_mitigation_methodology_pt são a '
        'mesma figura, mantida com os dois nomes usados anteriormente.\n'
        'latincom_page_2_pt reúne os painéis 2A e 2B, também disponíveis separadamente.\n',
        encoding='utf-8')


if __name__ == '__main__':
    main()
