# Captura direta do visualizador NGSO original

A figura `fig_cenario_geografico.png` combina duas capturas da pagina original
`sharc/satellite/ngso/frontend/index.html`, usando seu app.js intacto.
As funcoes originais preBuildGrid, assignGridCellsToSatellites,
drawPresentationFootprintCones e renderFrame desenham toda a cena.
Nao ha renderizador alternativo, cones redesenhados ou sobreposicao de satelites.

O backend original OrbitSimulationBackend fornece apenas o primeiro quadro
orbital do perfil presentation, System 3 a 340 km. O quadro, as entidades e
os desenhos sao os mesmos nas duas vistas; somente camera e viewport mudam.
Vista continental: enquadramento inicial lon [-83,-32], lat [-57,14],
estendido para a direita por captura ampla e recorte, 3200 x 2120 pixels.
O campo vertical e a projecao original no lado esquerdo sao preservados.
Detalhe: retangulo lon [-65,-52], lat [-29,-18], 1080 x 1230 pixels.
A composicao final tem 3200 x 2120 pixels, com o continente a esquerda,
detalhe circular do Paraguai a direita e legenda em painel escuro translucido,
sobre o fundo nativo que ocupa toda a imagem, sem barra branca nem titulo geral.
A lupa liga um circulo de selecao no mapa a lente ampliada por duas tangentes
e uma faixa translucida. Esse elemento e apenas uma indicacao de ampliacao,
nao um feixe do sistema. Os pixels das capturas nativas nao sao redesenhados.
Rotulos geograficos sao anotacoes de apresentacao projetadas pela camera.
Nenhum feixe, satelite ou grid foi redesenhado na composicao.
Os paineis de operacao foram ocultados somente no navegador da captura.
A legenda identifica os elementos existentes. Por pedido do usuario, o rodape
foi removido da figura. Os creditos completos permanecem no JSON de validacao
e em `figuras/tcc_geographic_capture/map_attribution.txt`; ao publicar, incluir
a atribuicao cartografica na legenda ou texto associado conforme a licenca.
As duas capturas nativas ficam em `figuras/tcc_geographic_capture/native_*.png`.
A captura regional aprovada foi preservada como `regional_reference.png`.

## Cobertura e receptor

Usa a lista da campanha 07: Argentina, Bolivia, Brazil, Chile, Colombia,
Ecuador, Peru, Uruguay, Venezuela, Guyana e Suriname. Paraguai sem servico.
O frontend legado considera somente os aneis exteriores dos poligonos.
A geometria de cobertura fornecida a captura foi dividida em -58 graus de
longitude para abrir o vazio do Paraguai, mantendo exatamente a mesma area
e fronteiras. A equivalencia geometrica e verificada pelo preparador.
Essa adaptacao e feita apenas no JSON de captura, sem modificar o app.js.
O toggle original de mitigacao esta desligado: nao ha exclusao circular ou PBO.

Como solicitado, apenas a ilustracao coloca o receptor em Ciudad del Este,
aproximadamente (-25.5169,-54.6169), referencia urbana de
https://mapcarta.com/Ciudad_del_Este . A campanha permanece com sua coordenada
original (-25.5549751,-54.5746686). Nenhum input ou resultado foi alterado.

Trata-se de uma visualizacao geometrica, nao um snapshot dos outputs de INR.
O perfil original nao reproduz o sorteio LF. Seus cones sao envelopes de
atendimento ilustrativos, nao contornos de ganho de antena calculados.

## Reproducao

Executar `tools/prepare_tcc_geography.py`, depois
`node tools/capture_tcc_geography.cjs`.
Para alterar apenas a montagem, reutilizando as capturas salvas, executar
`node tools/capture_tcc_geography.cjs --layout-only`.
O servidor de captura le os arquivos originais do frontend sem os reescrever.
A copia de YAML para ilustracao e o quadro ficam em `figuras/tcc_geographic_capture`.
A versao alternativa rejeitada foi retirada; existe somente como backup em
`figuras/backups/geography_alternative_renderer_20261112`.
