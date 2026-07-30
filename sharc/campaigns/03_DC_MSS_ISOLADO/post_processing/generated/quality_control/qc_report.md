# Relatório de controle de qualidade

Este relatório foi produzido sem alterar os outputs brutos.

## Resumo

- PASS: 336
- WARNING: 1
- FAIL: 0

## Verificações

| Status | Verificação | Cenário | Evidência |
|---|---|---|---|
| PASS | `selected_scenario_count` | `campaign` | Cenários selecionados=26; esperado=26. |
| PASS | `baseline_count` | `campaign` | Baselines por load factor=[0.2, 0.5]. |
| PASS | `positive_scenarios_per_load_factor` | `campaign` | Contagens={0.2: 12, 0.5: 12}; esperado=12 por load factor. |
| PASS | `configured_parameter_levels` | `campaign` | LF=[0.2, 0.5]; PBO=[0.0, 5.0, 10.0, 15.0, 20.0]; frações=[0.05, 0.1, 0.15]. |
| WARNING | `superseded_output_candidates` | `campaign` | Diretórios candidatos não selecionados por estarem menos completos: 23. |
| PASS | `structured_csv_exists` | `LF20_PBO00_F00` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO0dB_F00pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO00_F00` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO00_F00` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO00_F00` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO00_F00` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO00_F00` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO00_F00` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO00_F00` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO00_F00` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO00_F00` | Erro salvo/observado=0; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO00_F00` | Snapshots sem feixe afetado: 1000. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO00_F00` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO05_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO5dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO05_F05` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO05_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO05_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO05_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO05_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO05_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO05_F05` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO05_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO05_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO05_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO05_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO05_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO5dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO05_F10` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO05_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO05_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO05_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO05_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO05_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO05_F10` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO05_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO05_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO05_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO05_F10` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO05_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO5dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO05_F15` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO05_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO05_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO05_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO05_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO05_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO05_F15` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO05_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO05_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO05_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO05_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO10_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO10dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO10_F05` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO10_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO10_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO10_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO10_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO10_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO10_F05` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO10_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO10_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO10_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO10_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO10_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO10dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO10_F10` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO10_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO10_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO10_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO10_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO10_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO10_F10` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO10_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO10_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO10_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO10_F10` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO10_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO10dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO10_F15` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO10_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO10_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO10_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO10_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO10_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO10_F15` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO10_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO10_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO10_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO10_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO15_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO15dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO15_F05` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO15_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO15_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO15_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO15_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO15_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO15_F05` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO15_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO15_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO15_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO15_F05` | Erro absoluto máximo contra a equação do SHARC=2.66e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO15_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO15dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO15_F10` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO15_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO15_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO15_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO15_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO15_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO15_F10` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO15_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO15_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO15_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO15_F10` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO15_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO15dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO15_F15` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO15_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO15_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO15_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO15_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO15_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO15_F15` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO15_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO15_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO15_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO15_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO20_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO20dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO20_F05` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO20_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO20_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO20_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO20_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO20_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO20_F05` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO20_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO20_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO20_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO20_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO20_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO20dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO20_F10` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO20_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO20_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO20_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO20_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO20_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO20_F10` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO20_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO20_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO20_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO20_F10` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF20_PBO20_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF20_PBO20dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF20_PBO20_F15` | Registros lidos: 275169. |
| PASS | `required_columns` | `LF20_PBO20_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF20_PBO20_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF20_PBO20_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF20_PBO20_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF20_PBO20_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF20_PBO20_F15` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF20_PBO20_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF20_PBO20_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF20_PBO20_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF20_PBO20_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO00_F00` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO0dB_F00pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO00_F00` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO00_F00` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO00_F00` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO00_F00` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO00_F00` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO00_F00` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO00_F00` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO00_F00` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO00_F00` | Erro salvo/observado=0; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO00_F00` | Snapshots sem feixe afetado: 1000. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO00_F00` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO05_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO5dB_F05pct_2026-07-28_01\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO05_F05` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO05_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO05_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO05_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO05_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO05_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO05_F05` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO05_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO05_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO05_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO05_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO05_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO5dB_F10pct_2026-07-28_01\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO05_F10` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO05_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO05_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO05_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO05_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO05_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO05_F10` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO05_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO05_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO05_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO05_F10` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO05_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO5dB_F15pct_2026-07-28_01\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO05_F15` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO05_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO05_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO05_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO05_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO05_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO05_F15` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO05_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO05_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO05_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO05_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO10_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO10dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO10_F05` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO10_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO10_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO10_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO10_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO10_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO10_F05` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO10_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO10_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO10_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO10_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO10_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO10dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO10_F10` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO10_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO10_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO10_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO10_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO10_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO10_F10` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO10_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO10_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO10_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO10_F10` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO10_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO10dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO10_F15` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO10_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO10_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO10_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO10_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO10_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO10_F15` | Erro máximo PBO=0 dB; erro máximo de potência=0 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO10_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO10_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO10_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO10_F15` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO15_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO15dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO15_F05` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO15_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO15_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO15_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO15_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO15_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO15_F05` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO15_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO15_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO15_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO15_F05` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO15_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO15dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO15_F10` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO15_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO15_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO15_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO15_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO15_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO15_F10` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO15_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO15_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO15_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO15_F10` | Erro absoluto máximo contra a equação do SHARC=2.66e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO15_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO15dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO15_F15` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO15_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO15_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO15_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO15_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO15_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO15_F15` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO15_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO15_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO15_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO15_F15` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO20_F05` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO20dB_F05pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO20_F05` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO20_F05` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO20_F05` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO20_F05` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO20_F05` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO20_F05` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO20_F05` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO20_F05` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO20_F05` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO20_F05` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO20_F05` | Erro absoluto máximo contra a equação do SHARC=2.22e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO20_F10` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO20dB_F10pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO20_F10` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO20_F10` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO20_F10` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO20_F10` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO20_F10` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO20_F10` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO20_F10` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO20_F10` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO20_F10` | Erro salvo/observado=9.71e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO20_F10` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO20_F10` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `structured_csv_exists` | `LF50_PBO20_F15` | C:\GitHub\SHARC\sharc\campaigns\03_DC_MSS_ISOLADO\output\output_dc_mss_isolado_Sys3_340km_LF50_PBO20dB_F15pct_2026-07-28_02\imt_dl_selected_ue_metrics.csv |
| PASS | `structured_csv_readable` | `LF50_PBO20_F15` | Registros lidos: 689089. |
| PASS | `required_columns` | `LF50_PBO20_F15` | As 12 colunas obrigatórias estão presentes. |
| PASS | `finite_values` | `LF50_PBO20_F15` | NaN=0; todos finitos=True. |
| PASS | `unique_snapshot_ue_beam` | `LF50_PBO20_F15` | Registros em chaves duplicadas: 0. |
| PASS | `snapshot_count` | `LF50_PBO20_F15` | Snapshots observados=1000; configurados=1000. |
| PASS | `selected_beams_active` | `LF50_PBO20_F15` | Registros selecionados com beam_active=False: 0. |
| PASS | `tx_power_consistency` | `LF50_PBO20_F15` | Erro máximo PBO=0 dB; erro máximo de potência=3.55e-15 dB. |
| PASS | `unaffected_nominal_power` | `LF50_PBO20_F15` | Erro máximo em feixes não afetados=0 dB. |
| PASS | `realized_fraction` | `LF50_PBO20_F15` | Erro salvo/observado=8.33e-17; erro de arredondamento=0; máximo de valores distintos por snapshot=1. |
| PASS | `snapshots_without_affected_beams` | `LF50_PBO20_F15` | Snapshots sem feixe afetado: 0. |
| PASS | `spectral_efficiency_proxy_formula` | `LF50_PBO20_F15` | Erro absoluto máximo contra a equação do SHARC=1.78e-15. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.2, fração=5%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.2, fração=5%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.2, fração=10%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.2, fração=10%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.2, fração=15%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.2, fração=15%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.2, PBO=5 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.2, PBO=10 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.2, PBO=15 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.2, PBO=20 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.5, fração=5%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.5, fração=5%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.5, fração=10%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.5, fração=10%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `identical_masks_across_pbo` | `campaign` | LF=0.5, fração=15%: máscaras de 5, 10, 15 e 20 dB idênticas. |
| PASS | `paired_geometry_and_users` | `campaign` | LF=0.5, fração=15%: chaves snapshot_id+ue_id+beam_id coincidem com o baseline. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.5, PBO=5 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.5, PBO=10 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.5, PBO=15 dB: 5% ⊆ 10% ⊆ 15% = True. |
| PASS | `nested_fraction_masks` | `campaign` | LF=0.5, PBO=20 dB: 5% ⊆ 10% ⊆ 15% = True. |
