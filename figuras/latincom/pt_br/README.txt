FIGURAS LATINCOM EM PORTUGUÊS

Cada imagem final tem um TXT de mesmo nome com legenda, fonte e método de produção.
Os diagramas têm PNG a 600 dpi, PDF e SVG. Os PDFs/SVGs preservam os elementos vetoriais, mas incorporam os renders raster de satélites e antenas.
Os dois mapas Cesium são PNGs de 3200 x 1840 pixels; não são imagens vetoriais.
As versões em inglês foram preservadas. Nenhum resultado científico foi recalculado.

TERMINOLOGIA
Jargões mantidos em inglês: User Equipment (UE), feeder link, service link, payload, bent-pipe, gateway, direct satellite-to-device link, main lobes, off-axis radiation, power back-off, snapshot e downlink. Textos explicativos e nomes dos países permanecem em português.

REPRODUÇÃO DOS DIAGRAMAS
.venv/Scripts/python.exe tools/generate_latincom_portuguese.py

REPRODUÇÃO DA TRADUÇÃO DOS MAPAS EXISTENTES
.venv/Scripts/python.exe tools/generate_latincom_portuguese.py --maps-only
Somente os retângulos de cabeçalho e legenda são substituídos.

NOVA CAPTURA NO SIMULADOR (OPCIONAL)
.venv/Scripts/python.exe -m sharc.satellite.ngso.backend.api --port 8000
http://127.0.0.1:8000/?profile=presentation&scenario=sa&capture=publication&lang=pt
http://127.0.0.1:8000/?profile=presentation&scenario=brarg&capture=publication&lang=pt
Clique em Generate PNG após carregar a cena.

latincom_sharc_monte_carlo_pt e dc_mss_fs_mitigation_methodology_pt são a mesma figura, mantida com os dois nomes usados anteriormente.
latincom_page_2_pt reúne os painéis 2A e 2B, também disponíveis separadamente.
