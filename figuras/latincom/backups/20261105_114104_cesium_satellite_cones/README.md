# Capturas Cesium para LATINCOM

## Arquivos

- `mapa_zona_exclusao.png`: cobertura regional, com celulas excluidas em torno do FS.
- `mapa_power_backoff.png`: cobertura Brasil/Argentina, com celulas de fronteira destacadas.
- PNGs de 3200 x 1840 pixels, renderizados no Cesium e exportados com legenda em ingles.
- Legenda compacta sobreposta no canto inferior direito, com fonte de 56 px.
- O marcador branco identifica o FS; o texto redundante junto ao ponto foi ocultado.
- Os arquivos originais da pasta Downloads foram preservados.

## Reproducao

Na raiz do repositorio, iniciar `.venv/Scripts/python.exe -m sharc.satellite.ngso.backend.api`.
Abrir um dos enderecos abaixo, aguardar `Ready to capture` e clicar em `Generate PNG`:

- http://127.0.0.1:8000/?profile=presentation&scenario=sa&capture=publication
- http://127.0.0.1:8000/?profile=presentation&scenario=brarg&capture=publication

Ambos usam o frame 1 (tempo orbital 0 s), System 3 a 340 km, e a mesma camera:
alvo (-56.8, -25.0), heading 0 graus, pitch -82 graus e range 3 550 000 m.
Esses valores definem apenas a camera, nao coordenadas de uma estacao.
Textos e legenda sao gerados em `sharc/satellite/ngso/frontend/publication.js`.

## Significado e limites

- Verde: satelite com pelo menos uma celula associada no visualizador.
- Ciano: outro satelite exibido, sem celula associada nesse frame.
- Branco: receptor FS vitima.
- Hexagono laranja: celula de servico sem destaque de mitigacao.
- Hexagono branco: excluido no SA; com destaque de power back-off no BR/ARG.
- Envelopes amarelos: geometria de footprints de servico, nao nivel de interferencia nem lobulos individuais calculados.

Estas sao visualizacoes geometricas, nao amostras extraidas dos outputs de INR.
O frontend associa celulas pelo maior angulo de elevacao, com limiar de 32 graus.
Ele nao reproduz o sorteio de atividade LF dos drops Monte Carlo da campanha.
O modo de apresentacao existente usa raio ilustrativo de exclusao de 180 km e
uma faixa de borda discretizada com pelo menos uma vizinhanca de hexagonos,
mesmo quando os YAMLs de base se chamam EZ0km e M0km. Nao interpretar essas
dimensoes visuais como distancias de conformidade obtidas no artigo.
Nenhum YAML ou output cientifico foi alterado para estas capturas.

Foram ocultados apenas os UEs ilustrativos e o vetor visual de azimute, para
priorizar satelites, celulas, footprints e FS. A posicao do FS nao foi movida.
A atribuicao de Cesium ion, Bing Maps e dos provedores presentes na cena foi
incluida em um rodape estreito de cada PNG, a partir dos creditos carregados pelo Cesium.
