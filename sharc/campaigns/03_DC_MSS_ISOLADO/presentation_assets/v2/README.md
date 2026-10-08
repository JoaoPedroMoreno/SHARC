# Ilustracoes PBO - versao 2

Geradas em 2026-10-08 com a ferramenta nativa image_gen. As tres figuras sao esquemas qualitativos para apresentacao oral, nao saidas de simulacao ou mapas quantitativos da campanha.

## Fontes e enquadramento

- Paper_ENCOM-1.pdf, secoes II e III: sistema DC-MSS-IMT isolado, selecao pseudoaleatoria de fracoes de feixes ativos, custo no sinal desejado e beneficio de interferencia nos demais usuarios.
- ITU-R_WP4C_Contribution_4C-612_Brazil_2026.docx, Study G, Modelling of operations: contexto de fronteira Brasil/Argentina/Paraguai, margens operacionais e controle de potencia por feixe.
- As figuras 2 e 3 representam a motivacao geografica da contribuicao, nao a mascara aleatoria efetivamente usada no artigo.

## Arquivos e finalidade

| Arquivo | PNG nativo | Uso |
| --- | --- | --- |
| cover_pbo_brazil.png | 1672 x 941 | Capa: satelite, Brasil, celulares e PBO localizado. |
| itu_pbo_overview_brazil.png | 1254 x 1254 | Metade esquerda: contexto brasileiro e regiao ilustrativa com PBO. |
| itu_pbo_zoom_border.png | 1254 x 1254 | Metade direita: mecanismo local antes/depois. |

A resolucao pedida ao gerador foi 2048 x 1152 ou 2048 x 2048; a ferramenta retornou os tamanhos nativos acima. Estes arquivos nao foram artificialmente ampliados. As figuras quadradas foram dimensionadas para ocupar metades de um slide 16:9.

Verificacao visual: as figuras 2 e 3 foram renderizadas lado a lado em uma pagina branca de 1920 x 1080, com 876 x 876 pixels por imagem. Os rotulos permaneceram legiveis e sem sobreposicao nessa composicao. Essa checagem em tela nao substitui um teste no projetor da apresentacao.

## Leitura tecnica

- Azul: feixes nominais. Laranja: feixes que continuam ativos com PBO. Vermelho: interferencia. Verde: receptor terrestre considerado para protecao.
- A dimensao desenhada da celula permanece igual no mecanismo antes/depois; a cor e a intensidade indicam menor potencia. Isto nao afirma que a cobertura operacional acima de um limiar fica inalterada.
- A seta de interferencia parte do satelite e termina no receptor IMT; nao representa uma retransmissao pelos celulares ou pelo solo.
- A espessura das setas e qualitativa, sem escala de dB. O verde nao certifica conformidade nem garante que o receptor fique abaixo de algum limiar.
- Brasil, footprints, satelite, limites e distancias sao esquematicos. A capa nao afirma que um unico satelite a 340 km atenda simultaneamente todo o Brasil.
- O script generate_presentation_images.py da pasta anterior gera a versao antiga; nao gera estes novos PNGs.

## Prompts utilizados

### Figura 1

Use case: scientific-educational. Create ONE finished high-resolution PNG illustration for an academic oral presentation about Direct-to-Cell LEO satellites and selective beam power back-off over Brazil. This is figure 1 of a consistent three-figure set. Requested canvas 2048x1152, landscape 16:9, pure white background (#FFFFFF), clean margins.

Message in one glance: a LEO satellite illuminates multiple regions of Brazil; most beams remain nominal blue; only a small localized subset has reduced power, orange. Coverage remains present everywhere depicted.

Composition: premium clean semi-isometric technical illustration, unmistakable accurate recognizable Brazil country silhouette in the lower middle, gently tilted but not so far that geography becomes unrecognizable. Whole country visible, north upward, eastern coastline on right, Amazonas extension west/upper-left and long southern tip. No state borders. Country is very pale cool blue with a fine restrained outline, flat thin map surface not a thick plinth. Above it, a single elegant technically plausible LEO satellite with a rectangular metallic communications bus, two dark blue rectangular solar-panel wings, and a downward-facing antenna. Satellite large and clearly recognizable, around upper central area. Arrange seven distinct circular/elliptical beam footprints wholly inside the Brazilian silhouette, distributed north, northeast, center, southeast, south and west. Five blue nominal footprints and their softly translucent but well-defined blue cone-shaped downlink beams connect directly to the satellite antenna. Two adjacent orange footprints near the SOUTHWESTERN land-border part of Brazil with their own orange downlink cones. Both orange footprints remain the SAME GEOMETRIC SIZE as comparable nominal footprints. Orange cones are less intense/paler than blue nominal cones, illustrating lower power rather than shrunken or removed coverage. Beam edges do not become tangled; keep enough empty separation to see all seven ground footprints. A few minimalist smartphone silhouettes (two or three, only if readable) stand in selected blue and orange footprints, indicating direct-to-cell service without ground relays. All footprints remain within Brazil; nothing in the ocean or outside the country.

Visual style: polished academic scientific illustration, subtle volume on satellite, crisp vector-like edges and restrained translucency on beams, no cartoon or clipart, no dramatic lighting, no glow, no gray background, no heavy shadow, no decorative orbs. Consistent colors: nominal blue #1683C8, PBO orange #ED8737, satellite dark blue #124B70, fine outlines #223B4B. The map stays pale #F0F8FC on a pure white canvas. Reserve clean whitespace around the image but do NOT leave half of the canvas blank for a title: the image itself will be placed beside an existing title. No embedded text, no legends, no numbers, no logos, no watermark. No interference arrows on this cover; prioritize the satellite-Brazil-selective-power story. The cone diagram is illustrative, not a quantitative single-satellite footprint map.

### Figura 2

Referencia visual: Figura 1.

Use case: scientific-educational. Produce ONE new academic slide illustration, figure 2 of a three-part presentation. Supporting reference image 1 is ONLY the palette and clean technical style reference, not an edit target and not a composition to copy. This image is a geographic overview, no satellite or cones needed. A clear whole-country map of Brazil with selective power back-off along a localized southwestern land-border region. Prefer a high-resolution 2048x2048 square PNG (for the left half of a 16:9 slide), pure white background, ample safe margins.

Scientific context: the Brazilian ITU-R contribution 4C/612 studies satellite downlink interference near the Brazil/Paraguay/Argentina border and per-beam power reduction. This drawing is a schematic of that context, NOT a quantitative reconstruction of exact simulated cells. The separate paper investigates fractions of active beams; do not add percentage claims or measured boundaries.

Composition: Show the complete, geographically recognizable north-up Brazil silhouette prominently centered, clean and upright with minimal perspective. Correct overall shape, recognizable northwestern Amazon extension, northeastern Atlantic bulge and southern taper. Use a subtle pale cool blue fill #F0F8FC, crisp dark-blue thin outline #223B4B. NO state borders, cities, terrain, roads, flags, political symbols or coordinate grid. Show about 30 evenly sized, clearly separated circular service footprints distributed over the country's interior, ALL clipped to or wholly inside Brazil (no cells outside the land outline). Circles have blue #1683C8 outlines and very light blue centers. A small contiguous set of exactly three or four same-sized circles is orange #ED8737 with pale orange interiors, near the southwestern border facing Paraguay, around southern Mato Grosso do Sul and western Parana. These orange cells retain the same footprint size and remain visibly filled, emphasizing reduced transmitted power, not switched-off coverage. All other service cells remain blue, including distant north, northeast and southeast. Do not draw arbitrary random orange cells elsewhere, do not color the whole border orange. No fake heatmap.

A very subtle pale-orange local band behind only the orange cells may connect them as a clearly localized region, strictly inside Brazil. One dark-orange neat leader outside the map leads to this group, with the LARGE exact Portuguese label on two lines: "Região com" / "PBO". Another large dark-blue label "Brasil" sits in clean open space near the upper part of the map. A compact, airy two-item key at the bottom has an identical small blue circle followed by "Nominal" and an identical orange circle followed by "Com PBO". Both labels use large crisp semibold modern sans-serif type, easy to read when reduced to half-slide width; no small captions or boxes. Do not put text on top of cells. Keep all map shapes and annotations within safe margins. No title, no explanatory paragraphs, no logos, no watermark.

Visual language: polished restrained scientific infographic with crisp vector-like edges, lightly translucent circular cells, strong blue/orange semantic contrast and large typography. White backdrop, NOT gray. Match the reference palette. No decorative 3D slab or black drop shadow. This must communicate in seconds WHERE selective PBO is applied and that the remaining network is nominal.

### Figura 3

Referencias visuais: Figuras 1 e 2.

Use case: scientific-educational. Generate ONE finished academic technical illustration for the RIGHT HALF of a 16:9 oral presentation slide, preferably a 2048x2048 square PNG on pure white. This is figure 3, a LOCAL ZOOM explaining how satellite beam power back-off reduces unwanted received interference near a border. Image 1 (satellite over Brazil) is a STYLE/PALETTE REFERENCE ONLY; image 2 (Brazil overview) is the palette and orange selected-region reference. Do not reproduce the Brazil map here. Make a new schematic with LARGE elements and LARGE type for projection.

The core scientific truth: a satellite transmits several downlink beams. Only the selected beam is attenuated. It still serves its cell. The unwanted signal received at a nearby TERRESTRIAL IMT receiver decreases. Interference originates at the SATELLITE antenna, not from the ground footprints or smartphones. Use a co-channel qualitative illustration; do not imply numerical guaranteed protection.

Composition: TWO LARGE MATCHED MINI-SCENES STACKED VERTICALLY in this ONE image, with generous white space between and no box frames. They must show EXACTLY THE SAME positions, camera and footprint sizes, to provide an unambiguous before-and-after comparison.
Top scene heading, large dark navy, exact Portuguese: "Sem PBO".
Bottom scene heading, same size: "PBO seletivo".

Each scene: one compact but clearly recognizable LEO satellite in the upper-left/center with rectangular silver communications body, dark-blue solar-panel wings and downward-looking antenna, drawn in the same clean semi-3D style as image 1. Three downward cones illuminate THREE ellipse-shaped neighboring satellite service cells in the lower-left and middle of the scene. The footprints are SAME SIZE between the two scenes. A slim phone receiver remains visibly present within each of the three footprints. At right of these cells, a sparse dark-blue DASHED ground line marks the local international boundary. To the right of this boundary, a single green terrestrial IMT receiving mast stands clearly outside all satellite footprints, with one simple receive antenna atop it, without outward radio waves. Its green color means protected receiver, not transmitter. Plain white ground, no gray platform, no shading outside cell footprints, no scenery.

TOP: all three cones and cells blue #1683C8. A single bold RED/SALMON #CF5752 dashed interference trajectory starts at the satellite's down-facing transmitting antenna and travels directly through the air toward the green mast receive antenna, finishing with a CLEAR arrowhead AT the mast antenna. This is an unwanted off-axis satellite signal; do NOT draw the arrow starting at a ground cell. Route it to the right, outside the serving cones, to avoid crossings.

BOTTOM: the TWO cells farther from the boundary and their cones stay exactly the same nominal blue as above. ONLY the third cone/cell nearest the boundary changes to orange #ED8737. This orange downlink cone is pale / less intense, but has the SAME full geometric outline and footprint area and a visible phone: beam remains on at lower power. The interference trajectory from satellite to mast follows the EXACT SAME path and red/salmon hue as in the top scene, but its dashed stroke is only ONE THIRD as thick, with visible arrowhead at the same green mast. It is NOT orange. Geometry, satellite, mast, phone positions, noise and ground line do not change.

Text: besides the two scene headings, use ONLY these THREE LARGE legible labels, semibold clean sans-serif, in clear white space:
"Receptor IMT" near the upper green mast;
"Menor potência" with a SHORT clear leader to the bottom ORANGE beam;
"Menor interferência" next to the bottom thin RED trajectory, unambiguously associated with it.
No equations, tiny footnotes, numerals, additional key or paragraph. Keep letters clear of cones and arrow paths, generous margins, no text boxes.

Use crisp premium technical rendering, restrained semi-3D satellite, blue #1683C8, orange #ED8737, interference red #CF5752, receiver green #22866A, typography navy #123E5C. No gray background, gray oval ground, massive shadows, clipart, decorative swooshes, halo or glow. This figure must unmistakably show that reducing satellite transmit power on ONE beam leaves its footprint present and reduces the off-axis unwanted signal at the same victim receiver. Clarity and causal correspondence matter more than ornament. Make all ground features and letters readable at about 700 pixels total image width.

