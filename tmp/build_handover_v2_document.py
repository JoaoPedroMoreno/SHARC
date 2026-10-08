from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path(r"C:\GitHub\SHARC\sharc\campaigns\04_DC_MSS_to_EESS\documentation\Interference_Aware_Inter_Satellite_Handover_V2_SHARC.docx")
BLUE = "2E74B5"; DARK = "1F4D78"; LIGHT = "E8EEF5"; GRAY = "F2F4F7"; INK = "222222"

def font(run, size=11, bold=False, color=INK, italic=False):
    run.font.name = "Calibri"; run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size); run.bold = bold; run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tcPr.append(shd)

def margins(cell, top=80, start=120, bottom=80, end=120):
    tcPr = cell._tc.get_or_add_tcPr(); tcMar = tcPr.first_child_found_in("w:tcMar")
    if tcMar is None: tcMar = OxmlElement("w:tcMar"); tcPr.append(tcMar)
    for tag, value in (("top",top),("start",start),("bottom",bottom),("end",end)):
        node=OxmlElement("w:"+tag); node.set(qn("w:w"),str(value)); node.set(qn("w:type"),"dxa"); tcMar.append(node)

def set_repeat_header(row):
    trPr=row._tr.get_or_add_trPr(); el=OxmlElement("w:tblHeader"); el.set(qn("w:val"),"true"); trPr.append(el)

def table(doc, headers, rows, widths=None):
    t=doc.add_table(rows=1, cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; shade(c,LIGHT); margins(c); p=c.paragraphs[0]; r=p.add_run(h); font(r,10,bold=True,color=DARK)
    set_repeat_header(t.rows[0])
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row):
            margins(cells[i]); cells[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            r=cells[i].paragraphs[0].add_run(str(v)); font(r,9.5)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t

def para(doc, text="", bold_prefix=None, italic=False):
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(6); p.paragraph_format.line_spacing=1.2
    if bold_prefix and text.startswith(bold_prefix):
        font(p.add_run(bold_prefix),bold=True); font(p.add_run(text[len(bold_prefix):]),italic=italic)
    else: font(p.add_run(text),italic=italic)
    return p

def bullet(doc, text):
    p=doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after=Pt(4); p.paragraph_format.line_spacing=1.2; font(p.add_run(text)); return p

def code(doc, text):
    p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.25); p.paragraph_format.right_indent=Inches(.25); p.paragraph_format.space_after=Pt(8)
    pPr=p._p.get_or_add_pPr(); shd=OxmlElement("w:shd"); shd.set(qn("w:fill"),"F4F6F9"); pPr.append(shd)
    r=p.add_run(text); r.font.name="Consolas"; r._element.get_or_add_rPr().rFonts.set(qn("w:ascii"),"Consolas"); r.font.size=Pt(9); return p

def heading(doc, text, level=1):
    p=doc.add_paragraph(style=f"Heading {level}"); p.paragraph_format.keep_with_next=True; p.add_run(text); return p

doc=Document(); sec=doc.sections[0]
sec.page_width=Inches(8.5); sec.page_height=Inches(11); sec.top_margin=sec.bottom_margin=sec.left_margin=sec.right_margin=Inches(1)
sec.header_distance=sec.footer_distance=Inches(.492)
styles=doc.styles
normal=styles["Normal"]; normal.font.name="Calibri"; normal.font.size=Pt(11); normal.font.color.rgb=RGBColor.from_string(INK)
normal.paragraph_format.space_after=Pt(6); normal.paragraph_format.line_spacing=1.2
for name,size,before,after,color in [("Heading 1",16,18,10,BLUE),("Heading 2",13,14,7,BLUE),("Heading 3",12,10,5,DARK)]:
    s=styles[name]; s.font.name="Calibri"; s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor.from_string(color); s.paragraph_format.space_before=Pt(before); s.paragraph_format.space_after=Pt(after)
header=sec.header.paragraphs[0]; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT; font(header.add_run("SHARC | DC-MSS -> EESS | Nota técnica"),9,color="666666")
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER; font(footer.add_run("Interference-Aware Inter-Satellite Handover V2"),8.5,color="777777")

p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(90); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("INTERFERENCE-AWARE\nINTER-SATELLITE HANDOVER V2"),27,bold=True,color=DARK)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; font(p.add_run("Implementação no SHARC para cenários DC-MSS -> EESS"),15,color=BLUE)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(25); font(p.add_run("Descrição técnica da arquitetura, modelo matemático, integração e campanha"),11,italic=True,color="555555")
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(150); font(p.add_run("Repositório: C:/GitHub/SHARC\nCampanha: 04_DC_MSS_to_EESS\nAgosto de 2026"),10,color="666666")
doc.add_page_break()

heading(doc,"Resumo executivo",1)
para(doc,"O mecanismo implementado modifica exclusivamente a associação entre uma service cell do SERVICE_GRID e seu satélite servidor dentro de cada snapshot Monte Carlo. Ele não cria continuidade temporal, estado de handover entre snapshots, histerese, dwell time, atraso de sinalização ou interrupção de serviço.")
para(doc,"O V2 não utiliza o detector main-beam/main-beam como gatilho. Após o SHARC calcular a contribuição individual final de cada beam ativo para a estação EESS, os top-K links mais interferentes são examinados. Para cada um, todos os satélites já elegíveis para a mesma célula são avaliados com o próprio modelo físico do SHARC. O candidato que produzir a menor interferência é aceito somente se respeitar as restrições de serviço configuradas e a redução mínima exigida.")
table(doc,["Aspecto","Comportamento implementado"],[("Unidade de decisão","Uma service cell em um snapshot independente"),("Trigger V2","Ranking top-K por I_link final"),("Target","Satélite elegível que minimiza I_link"),("Identidade preservada","beam_grid_idx e centro da célula"),("Atualização agregada","Potência linear: Iagg - Icurrent + Icandidate"),("RNG","Estado de propagação restaurado após cada avaliação"),("Baseline","Legacy OFF e V2 OFF")],[1.7,4.8])

heading(doc,"1. Motivação e escopo",1)
para(doc,"A primeira versão de mitigação acionava a troca apenas quando o beam transmissor DC-MSS e a região de ganho máximo da antena EESS estavam simultaneamente alinhados. A auditoria mostrou que, embora eficaz nos poucos eventos detectados, esse gatilho era raro demais para alterar de forma relevante o percentil associado a 1% de excedência. O V2 foi implementado para atuar diretamente sobre os links que dominam a interferência agregada.")
bullet(doc,"A implementação é específica para DC-MSS como interferente e uma estação EESS como vítima.")
bullet(doc,"O caminho suportado é adjacent-channel, máscara espectral configurada, recepção adjacente EESS desligada e imt.ue.k = 1.")
bullet(doc,"O método preserva o modelo de antena, propagação, potência, largura de banda e máscara espectral existentes.")
bullet(doc,"A estratégia é uma referência de informação perfeita: ela usa a interferência física calculada no próprio snapshot.")

heading(doc,"2. Posição no fluxo do snapshot",1)
code(doc,"topologia + load -> EESS e pointing -> BS/UE -> power control -> coupling losses\n-> I_link de cada beam ativo -> ranking top-K -> avaliação dos candidatos\n-> handover aceito (se houver) -> I_agg final -> resultados normais")
para(doc,"A integração ocorre dentro de SimulationDownlink.calculate_external_interference(), depois que os ganhos, perdas e potência fora de banda necessários para cada link corrente já foram calculados. Com V2 desligado, o caminho original permanece inalterado: o dicionário de contribuições individuais nem sequer é necessário para a decisão.")

heading(doc,"3. Definições matemáticas",1)
heading(doc,"3.1 Contribuição individual",2)
para(doc,"Para cada beam ativo i, o SHARC produz a contribuição recebida final I_i em mW. No cenário da campanha, a contribuição adjacente é obtida a partir da potência fora de banda da máscara espectral e do coupling loss calculado para o enlace DC-MSS -> EESS.")
code(doc,"I_i [mW] = 10^((P_OOB,i [dBm] - L_coupling,i [dB]) / 10)")
para(doc,"L_coupling inclui a perda de propagação, o ganho transmissor na direção da EESS, o ganho receptor na direção do interferente e as perdas adicionais já aplicadas pelo SHARC. O V2 não reconstrói esses termos por uma aproximação externa: ele chama calculate_coupling_loss_system_imt(..., is_co_channel=False).")
heading(doc,"3.2 Interferência agregada",2)
code(doc,"I_agg = sum_i I_i")
para(doc,"O ranking é estável em ordem decrescente de I_i. Em empate, beam_row_idx crescente resolve a ordem. Os primeiros K elementos formam o conjunto de links examinados.")
heading(doc,"3.3 Redução prevista e atualização",2)
code(doc,"Delta_I [dB] = 10 log10(I_current / I_candidate)\nI_agg,new = I_agg,old - I_current + I_candidate")
para(doc,"A subtração nunca é feita em dB. A troca é aceita se Delta_I for maior ou igual a min_reduction_db e se o candidato respeitar a perda máxima de elevação de serviço.")

heading(doc,"4. Seleção dos links top-K",1)
para(doc,"A função select_triggered_links() recebe o mapa beam_row_idx -> I_link_linear_mw. No modo utilizado pela campanha, ORACLE_TOP_K, ela ordena todas as contribuições ativas e retorna no máximo top_k linhas. O antigo critério main-main não participa dessa seleção.")
table(doc,["Parâmetro","Papel"],[("top_k","Número máximo de links dominantes examinados"),("trigger_mode","ORACLE_TOP_K na campanha principal"),("max_handovers_per_snapshot","Limita quantas trocas podem ser efetivadas no snapshot")],[2.1,4.4])
para(doc,"A arquitetura mantém GEOMETRIC_RULE como ponto de extensão, mas a configuração rejeita sua ativação enquanto não existir uma regra empírica explícita. Isso impede que um limiar geométrico arbitrário seja usado por acidente.")

heading(doc,"5. Enumeração dos satélites candidatos",1)
para(doc,"Os candidatos vêm de topology._service_grid_snapshot, produzido pelo SERVICE_GRID. Portanto, o V2 não pesquisa toda a constelação indiscriminadamente. Ele reutiliza candidate_satellite_indices e candidate_elevations_deg, que representam os satélites geometricamente disponíveis segundo a lógica da topologia no snapshot.")
para(doc,"Para o beam em análise, o algoritmo mantém grid_idx = topology.beam_grid_idx[beam_row]. Cada candidato deve:")
bullet(doc,"ser diferente do satélite servidor corrente;")
bullet(doc,"pertencer à lista de satélites elegíveis do SERVICE_GRID;")
bullet(doc,"observar a mesma célula com elevação maior ou igual a minimum_service_angle;")
bullet(doc,"respeitar max_service_elevation_loss_deg em relação ao servidor corrente.")
para(doc,"Não foram adicionadas restrições de capacidade global de beams, balanceamento de carga, matching combinatório ou dinâmica temporal.")

heading(doc,"6. Avaliação física exata de cada candidato",1)
para(doc,"SimulationDownlink._evaluate_v2_candidate() materializa uma estação IMT_BS temporária na posição do satélite candidato. O boresight é recalculado do satélite para o centro imutável da service cell. A antena é criada pela mesma AntennaFactory e recebe os mesmos parâmetros de antena DC-MSS da campanha.")
code(doc,"beam_vector = cell_position - candidate_satellite_position\nazimuth = atan2(dy, dx)\nelevation = asin(dz / ||beam_vector||)")
para(doc,"Em seguida é criado um PropagationPath entre a EESS já realizada no snapshot e a estação candidata. O coupling loss é calculado pela função normal do SHARC, usando a frequência DC-MSS ativa, os ganhos reais das antenas e o modelo de propagação configurado. A potência espectral tx_oob_dbm usada para o link corrente é reutilizada, pois a troca preserva a mesma linha/célula, potência e configuração espectral.")
para(doc,"A interferência candidata é então calculada com a mesma expressão do caminho adjacente. Entre os candidatos válidos, choose_minimum_interference_target() seleciona o menor I_link_linear_mw.")

heading(doc,"7. Preservação da mesma service cell",1)
para(doc,"O método TopologyImtMssDc.reassign_service_grid_rows() altera somente campos dependentes do satélite servidor. beam_grid_idx não é modificado, e as coordenadas do grid e do centro da célula permanecem intactas.")
table(doc,["Preservado","Atualizado após handover"],[("beam_grid_idx","serving_satellite_idx"),("centro geográfico/ECEF/ENU da célula","posição x/y/z do satélite servidor"),("estado active/load da linha","latitude, longitude e altitude do servidor"),("power_backoff da linha","azimute e elevação do beam"),("identidade da service cell","elevação do satélite vista da célula")],[3.0,3.5])
para(doc,"Após uma troca aceita, a geometria e as antenas das BS são rematerializadas com as associações finais. O objetivo é assegurar que os resultados posteriores do snapshot representem o satélite efetivamente selecionado.")

heading(doc,"8. Preservação do RNG e pareamento",1)
para(doc,"BASELINE e V2 usam o mesmo seed de campanha e a mesma sequência de geração da topologia, load, EESS e apontamento. O núcleo de seleção não contém chamadas aleatórias.")
para(doc,"Como alguns modelos de propagação mantêm um RandomState interno, _evaluate_v2_candidate() salva seu estado antes de calcular um candidato e o restaura no bloco finally. Assim, avaliações adicionais não avançam permanentemente o RNG da propagação. Todos os candidatos partem do mesmo estado, e snapshots posteriores não são deslocados pelo número de candidatos examinados.")
para(doc,"Consequentemente, com V2 OFF, o baseline não executa avaliações adicionais. Com V2 ON, a diferença pretendida é exclusivamente a reassociação determinística baseada na realização já construída.")

heading(doc,"9. Parâmetros de configuração",1)
code(doc,"interference_aware_handover_v2:\n  enabled: false\n  top_k: 3\n  min_reduction_db: 0.0\n  max_service_elevation_loss_deg: 90.0\n  max_handovers_per_snapshot: 1\n  trigger_mode: ORACLE_TOP_K\n  record_candidate_details: false")
table(doc,["Campo","Descrição"],[("enabled","Ativa ou desativa integralmente o V2"),("top_k","Quantidade de links dominantes avaliados"),("min_reduction_db","Redução mínima prevista para aceitar a troca"),("max_service_elevation_loss_deg","Limite de degradação da elevação de serviço"),("max_handovers_per_snapshot","Número máximo de trocas sequenciais no snapshot"),("trigger_mode","Separação entre seleção dos links e seleção do target"),("record_candidate_details","Reserva para instrumentação detalhada")],[2.25,4.25])
para(doc,"A validação impede ativar simultaneamente o handover legado e o V2. Também falha rapidamente se a configuração física não corresponder ao caminho suportado.")

heading(doc,"10. Configuração da campanha principal",1)
para(doc,"O gerador produz duas estratégias pareadas: BASELINE, com legacy OFF e V2 OFF; e V2, com legacy OFF e V2 ON. Ambas compartilham seed, parâmetros físicos e 5000 snapshots.")
table(doc,["Dimensão","Valores"],[("Altitude","340 e 525 km"),("EESS","Systems B e D"),("Load factor","0,2 e 0,5"),("Guard band","80 a 0 MHz, passo de 5 MHz"),("Estratégia","BASELINE e V2"),("Posição EESS","Paraguai"),("Cobertura","América do Sul")],[2.0,4.5])
code(doc,"2 altitudes x 2 EESS x 2 loads x 17 guard bands x 2 estratégias = 272 inputs")
para(doc,"A largura do canal DC-MSS permanece fixa em 5 MHz. Somente sua frequência central varia:")
code(doc,"f_c,DC-MSS [MHz] = 2197.5 - GB [MHz]")
para(doc,"A instrumentação de diagnóstico permanece disponível, mas é gerada com enabled: false para evitar aumento de I/O na campanha principal.")

heading(doc,"11. Separação em relação ao handover legado",1)
table(doc,["Característica","Legado main-main","V2 top-K"],[("Trigger","psi_DC <= 4,322755 graus e psi_EESS < phi_min","Maiores I_link físicos do snapshot"),("Informação","Geometria angular","Interferência calculada pelo simulador"),("Busca do target","Primeiro seguro em elevação decrescente","Menor interferência entre candidatos válidos"),("Uso na campanha principal","Desligado","Estratégia V2")],[1.55,2.35,2.6])
para(doc,"O legado foi preservado no código para estudos anteriores, mas não é produzido como estratégia da matriz principal. O V2 não consulta psi_DC, psi_EESS ou phi_min para decidir quais links mitigar.")

heading(doc,"12. Testes e garantias implementadas",1)
bullet(doc,"V2 OFF não altera a potência agregada.")
bullet(doc,"V2 ON substitui I_current por um candidato melhor e altera I_agg.")
bullet(doc,"A atualização linear reproduz exatamente Iagg - Icurrent + Icandidate.")
bullet(doc,"A decisão mantém a identidade da célula.")
bullet(doc,"O ranking top-K é determinístico e estável.")
bullet(doc,"A escolha respeita perda máxima de elevação e redução mínima.")
bullet(doc,"O núcleo não altera o RNG global.")
bullet(doc,"O gerador contém exatamente 272 combinações.")
bullet(doc,"A lista de guard bands é 80, 75, ..., 0 MHz e a largura DC-MSS é 5 MHz.")
para(doc,"Na validação realizada durante a implementação, dez funções de teste unitário passaram. Não foi executada campanha de 5000 snapshots durante essa validação.")

heading(doc,"13. Limitações e interpretação científica",1)
para(doc,"O V2 deve ser interpretado como um handover interference-aware com informação perfeita dentro do simulador. Ele conhece a contribuição individual final dos links e pode recalcular fisicamente cada alternativa. Essa informação não é necessariamente observável em tempo real por um operador DC-MSS.")
bullet(doc,"Não há continuidade do mesmo UE físico entre associações; o requisito atual é mesma service cell/beam_grid_idx.")
bullet(doc,"Não há capacidade máxima de beams por satélite nem coordenação global entre células.")
bullet(doc,"Não há histerese, dwell time, atraso, ping-pong ou trajetória entre snapshots.")
bullet(doc,"A avaliação repetida de candidatos aumenta o custo computacional quando V2 está ativo.")
bullet(doc,"record_candidate_details está configurado, mas a persistência completa de todos os candidatos não faz parte do caminho principal atual.")
bullet(doc,"As lookup tables P.619 devem ser verificadas para cada frequência do sweep; na ausência do arquivo correspondente, o SHARC pode recorrer ao cálculo analítico existente.")
para(doc,"Uma regra operacional futura poderá substituir somente select_triggered_links(), mantendo a enumeração e a seleção física do target. Isso permite comparar uma regra geométrica implementável com o limite superior fornecido pelo V2 sem reescrever todo o mecanismo.")

heading(doc,"14. Arquivos da implementação",1)
table(doc,["Arquivo","Responsabilidade"],[("sharc/interference_aware_handover_v2.py","Ranking, decisão do target e álgebra linear"),("sharc/simulation_downlink.py","Integração, cálculo físico candidato e aplicação"),("sharc/topology/topology_imt_mss_dc.py","Reassociação mantendo a célula"),("sharc/parameters/imt/parameters_imt_mss_dc.py","Parâmetros e validação"),("campaigns/.../Scripts/generate.py","Matriz BASELINE/V2 e sweep espectral"),("tests/test_interference_aware_handover_v2.py","Testes do mecanismo"),("tests/test_campaign_04_generator_matrix.py","Testes da matriz de 272 inputs")],[2.65,3.85])

heading(doc,"15. Pseudocódigo consolidado",1)
code(doc,"calcular I_link de todos os beams ativos\nIagg = soma linear de I_link\nlinks = top_K(I_link)\nhandovers = 0\npara link em links:\n    se handovers == max_handovers: parar\n    cell = beam_grid_idx[link]\n    candidatos = satélites elegíveis(cell, minimum_service_angle)\n    para satélite em candidatos:\n        Icandidate = modelo_físico_SHARC(satélite, mesma cell, EESS)\n    target = argmin(Icandidate) sujeito à qualidade de serviço\n    se 10log10(Icurrent / Itarget) >= min_reduction_db:\n        Iagg = Iagg - Icurrent + Itarget\n        atualizar somente associação serving-satellite da linha\n        handovers += 1\npublicar Iagg final e continuar o fluxo normal")

heading(doc,"Conclusão",1)
para(doc,"A mitigação V2 foi incorporada como uma decisão determinística e independente em cada snapshot. Seu gatilho atua sobre os links que efetivamente dominam a interferência, enquanto a escolha do target reutiliza a geometria, antenas, máscara e propagação do SHARC. A célula permanece fixa, o agregado é atualizado em potência linear e o baseline continua disponível por feature flag. A campanha principal foi estruturada para comparar diretamente BASELINE e V2 em 272 cenários pareados.")

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(OUT)
