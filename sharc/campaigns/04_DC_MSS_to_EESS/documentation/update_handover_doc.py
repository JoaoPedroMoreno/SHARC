from pathlib import Path
from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "Interference_Aware_Inter_Satellite_Handover_V2_SHARC.docx"
DST = ROOT / "Interference_Aware_Inter_Satellite_Handover_V2_SHARC_Final.docx"

doc = Document(SRC)
p = doc.paragraphs

replacements = {
    7: "O V2 não utiliza o detector main-beam/main-beam como gatilho. Primeiro, o SHARC calcula a interferência agregada não mitigada Iagg_before. Somente quando Iagg_before > -154 dBW/MHz o mecanismo ordena as contribuições individuais e examina os top-K links. Para cada link dominante, todos os satélites elegíveis para a mesma célula são avaliados com o próprio modelo físico do SHARC. O candidato de menor interferência é aceito se respeitar a redução mínima e a perda máxima de elevação configuradas.",
    14: "A estratégia usa informação perfeita disponível dentro do simulador: o risco é identificado pela interferência agregada calculada no snapshot e os targets são comparados pela interferência física prevista. Portanto, ela representa um limite superior de mitigação, e não um protocolo temporal de rede.",
    16: "topologia + load -> EESS e pointing -> BS/UE -> power control -> coupling losses\n-> I_link e Iagg_before -> risk gate -> ranking top-K -> avaliação dos candidatos\n-> handover aceito (se houver) -> Iagg_after -> resultados normais",
    25: "Quando o risk gate é satisfeito, o ranking é estável em ordem decrescente de I_i. Em empate, beam_row_idx crescente resolve a ordem. Os primeiros K elementos formam o conjunto de links examinados.",
    30: "A função select_triggered_links() recebe o mapa beam_row_idx -> I_link_linear_mw. No modo da campanha, RISK_GATED_TOP_K, nenhum link é avaliado quando Iagg_before <= risk_gate_dbw_per_mhz. Acima do gate, as contribuições são ordenadas e no máximo top_k linhas são retornadas. O antigo critério main-main não participa da decisão.",
    51: "Todas as configurações usam seed 157 e a mesma sequência de geração da topologia, load, EESS e apontamento. A decisão V2 não contém chamadas aleatórias. Iagg_before registra a realização original dentro do próprio run e Iagg_after registra a mesma realização após a mitigação.",
    53: "Consequentemente, com V2 desligado o baseline permanece inalterado. Na campanha final não foi necessário gerar um baseline separado para cada frequência, pois cada execução V2 conserva explicitamente Iagg_before e Iagg_after para comparação pareada no mesmo snapshot.",
    55: "interference_aware_handover_v2:\n  enabled: true\n  top_k: 3\n  trigger_mode: RISK_GATED_TOP_K\n  risk_gate_dbw_per_mhz: -154.0\n  min_reduction_db: 0.0\n  max_service_elevation_loss_deg: 90.0\n  max_handovers_per_snapshot: 1\n  record_candidate_details: false",
    59: "A campanha PIBIC utiliza somente a configuração B validada: legacy OFF e V2 RISK_GATED_TOP_K ON. Não há baseline separado. Cada run contém 5000 snapshots e registra Iagg_before, Iagg_after, gate, handovers, compliance, concentração C1/C1:3, redução e custo de elevação.",
    61: "2 altitudes x 2 EESS x 2 loads x 7 guard bands = 56 execuções V2",
    64: "A instrumentação física pesada permanece disponível, mas fica disabled para evitar aumento de I/O. Os CSVs leves de snapshot e eventos permanecem ativos.",
    76: "Os testes do gerador validam a quantidade de combinações solicitada em cada etapa e impedem a geração de guard bands não autorizados.",
    77: "A campanha final contém GB = 80, 75, 70, 65, 60, 10 e 5 MHz. A largura DC-MSS permanece exatamente 5 MHz e fc = 2197,5 - GB.",
    78: "Os 56 runs concluíram com 5000 snapshots. As lookup tables P.619 de FOZ correspondentes às frequências utilizadas foram verificadas antes da geração dos inputs.",
    79: "14. Limitações e interpretação científica",
    86: "As lookup tables P.619 devem existir para cada frequência. O gerador faz uma verificação fail-fast antes de escrever YAMLs; as tabelas FOZ necessárias à campanha final foram confirmadas.",
    88: "15. Arquivos da implementação",
    90: "16. Pseudocódigo consolidado",
    91: "calcular I_link de todos os beams ativos\nIagg_before = soma linear de I_link\nse Iagg_before <= -154 dBW/MHz:\n    manter associações e publicar Iagg_after = Iagg_before\nsenão:\n    links = top_K(I_link)\n    para link em links, limitado a 1 handover:\n        cell = beam_grid_idx[link]\n        candidatos = satélites elegíveis(cell, minimum_service_angle)\n        para satélite em candidatos:\n            Icandidate = modelo_físico_SHARC(satélite, mesma cell, EESS)\n        target = argmin(Icandidate) sujeito à qualidade de serviço\n        se 10log10(Icurrent / Itarget) >= min_reduction_db:\n            Iagg = Iagg - Icurrent + Itarget\n            atualizar somente a associação serving-satellite da linha\npublicar Iagg_after e continuar o fluxo normal",
    93: "A mitigação V2 foi incorporada como decisão determinística e independente em cada snapshot. O risk gate evita handovers quando a EESS já atende ao critério; acima dele, o método atua nos links dominantes e escolhe o target com o próprio modelo físico do SHARC. Nos resultados finais, todos os cenários com GB >= 10 MHz ficaram abaixo de 1% de excedência após o V2. Em GB=5 MHz, o salto da SpectralMaskMSS tornou a interferência excessiva e nenhum cenário atingiu 1%, embora o handover ainda produzisse redução relevante.",
}
for idx, text in replacements.items():
    p[idx].text = text

# Atualiza tabelas preservando a geometria e o estilo existentes.
t = doc.tables
t[0].cell(2,1).text = "Risk gate em Iagg_before seguido de ranking top-K por I_link"
t[0].cell(7,0).text = "Comparação"
t[0].cell(7,1).text = "Iagg_before e Iagg_after pareados no mesmo snapshot"
t[1].cell(2,1).text = "RISK_GATED_TOP_K na campanha principal"
t[3].cell(6,1).text = "RISK_GATED_TOP_K separa necessidade de mitigação e identificação dos links"
t[4].cell(4,1).text = "80, 75, 70, 65, 60, 10 e 5 MHz"
t[4].cell(5,1).text = "V2 RISK_GATED_TOP_K; sem baseline separado"
t[5].cell(1,2).text = "Iagg_before > -154 dBW/MHz; então maiores I_link"
t[5].cell(4,2).text = "Única estratégia da campanha PIBIC"
t[6].cell(5,1).text = "Matriz V2 e pontos espectrais selecionados"
t[6].cell(7,1).text = "Testes da matriz solicitada e parâmetros físicos"

# Insere a seção de resultados antes das limitações.
anchor = p[79]
items = [
    ("13. Resultados consolidados da campanha PIBIC", "Heading 1"),
    ("Foram analisadas 56 execuções completas: 340/525 km, EESS B/D, load factors 0,2/0,5 e sete guard bands, sempre com 5000 snapshots e seed 157.", "Normal"),
    ("Para GB = 80, 75, 70, 65, 60 e 10 MHz, todos os oito cenários por guard band ficaram com probabilidade de excedência inferior a 1% após o V2. Em GB=10 MHz, a excedência residual variou de 0,14% a 0,80% e o P99 após mitigação variou de -159,41 a -154,49 dBW/MHz.", "Normal"),
    ("Em GB=5 MHz, nenhum dos oito cenários atingiu o critério: a excedência após V2 variou de 9,20% a 62,34%, e o P99 permaneceu entre -139,30 e -129,07 dBW/MHz. O mecanismo atuou em 30,44% a 84,28% dos snapshots, mas a redução mediana de aproximadamente 4,44 a 7,89 dB não compensou o aumento espectral.", "Normal"),
    ("A auditoria da SpectralMaskMSS mostrou a causa: com BW=5 MHz, a região plana de -13 dBm/MHz começa 10 MHz após a borda do canal. Assim, GB>=10 permanece no patamar de espúrios; GB=5 é o primeiro ponto amostrado dentro da região variável e aumenta o coupling integrado em aproximadamente 25 dB.", "Normal"),
]
for text, style in items:
    para = anchor.insert_paragraph_before(text)
    para.style = style

# Mantém fonte legível em trechos de código multilinha.
for idx in (16, 21, 24, 27, 43, 55, 63, 91):
    for run in p[idx].runs:
        run.font.name = "Consolas"
        run.font.size = Pt(9)

doc.save(DST)
print(DST)
