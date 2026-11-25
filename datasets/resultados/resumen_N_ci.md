# Evaluación externa · N · Carhuaz–Yungay (−78,00/−9,235/−77,50/−8,735)

Entrenamiento solo en Huaraz; protocolo prerregistrado (commits 610f756 y cd21595).

## Huellas de los datos frente a los manifiestos versionados

| Dataset | Coincide | SHA-256 (CI) |
|---|---|---|
| inv_a | sí | `4306cb1aaa5d8193…` |
| lito_a | sí | `a362b3e75607c3b5…` |
| dem_a | no (fuente cambiada) | `1865f052a01ec683…` |
| inv_b | sí | `12fbd084125356fa…` |
| lito_b | sí | `629d6cd2fbb3f171…` |
| dem_b | no (fuente cambiada) | `c94547c75f5bdb45…` |

## todos: 160 eventos externos

| Modelo | Estado | AUC externo (franja) | IC 95 % |
|---|---|---|---|
| V-pendiente_deg | NO VALIDADO | 0.4387 | [0.3804, 0.5258] |
| V-elevacion_m | EXPERIMENTAL | 0.7333 | [0.6399, 0.8255] |
| V-curvatura | NO VALIDADO | 0.5856 | [0.5658, 0.6744] |
| V-tpi_m | EXPERIMENTAL | 0.6266 | [0.6013, 0.7044] |
| V-dist_cauce_m | EXPERIMENTAL | 0.6568 | [0.6001, 0.7158] |
| R1-solo_elevacion | EXPERIMENTAL | 0.7333 | [0.6399, 0.8255] |
| R2-heuristico_pendiente | NO VALIDADO | 0.4387 | [0.3806, 0.5237] |
| M1-base | EXPERIMENTAL | 0.7202 | [0.6296, 0.8107] |
| M2-topografico | EXPERIMENTAL | 0.7432 | [0.674, 0.8166] |
| M4-bosque | EXPERIMENTAL | 0.7052 | [0.658, 0.7711] |
| M3-topo+litologia | EXPERIMENTAL | 0.7318 | [0.6698, 0.8062] |
| M3s-sin_Sedimento | EXPERIMENTAL | 0.7269 | [0.6649, 0.7991] |

## 1000|1100: 41 eventos externos

| Modelo | Estado | AUC externo (franja) | IC 95 % |
|---|---|---|---|
| V-pendiente_deg | NO VALIDADO | 0.5927 | [0.4379, 0.6836] |
| V-elevacion_m | VALIDACIÓN INSUFICIENTE | 0.6393 | [0.4364, 0.82] |
| V-curvatura | EXPERIMENTAL | 0.6337 | [0.5324, 0.6619] |
| V-tpi_m | EXPERIMENTAL | 0.6502 | [0.5656, 0.7026] |
| V-dist_cauce_m | EXPERIMENTAL | 0.6125 | [0.5283, 0.734] |
| R1-solo_elevacion | VALIDACIÓN INSUFICIENTE | 0.6393 | [0.4364, 0.82] |
| R2-heuristico_pendiente | NO VALIDADO | 0.5921 | [0.4383, 0.6819] |
| M1-base | EXPERIMENTAL | 0.6837 | [0.5302, 0.7903] |
| M2-topografico | EXPERIMENTAL | 0.7189 | [0.5962, 0.7952] |
| M4-bosque | VALIDACIÓN EXTERNA PROMETEDORA | 0.713 | [0.6274, 0.7801] |
| M3-topo+litologia | EXPERIMENTAL | 0.6666 | [0.5462, 0.7227] |
| M3s-sin_Sedimento | EXPERIMENTAL | 0.6702 | [0.5524, 0.7467] |

## 1000|1300: 56 eventos externos

| Modelo | Estado | AUC externo (franja) | IC 95 % |
|---|---|---|---|
| V-pendiente_deg | NO VALIDADO | 0.4835 | [0.3744, 0.5558] |
| V-elevacion_m | VALIDACIÓN INSUFICIENTE | 0.6274 | [0.4009, 0.7319] |
| V-curvatura | NO VALIDADO | 0.5101 | [0.4743, 0.6326] |
| V-tpi_m | NO VALIDADO | 0.5474 | [0.5043, 0.6554] |
| V-dist_cauce_m | NO VALIDADO | 0.5967 | [0.5062, 0.6467] |
| R1-solo_elevacion | VALIDACIÓN INSUFICIENTE | 0.6274 | [0.4009, 0.7319] |
| R2-heuristico_pendiente | NO VALIDADO | 0.4835 | [0.3744, 0.5558] |
| M1-base | VALIDACIÓN INSUFICIENTE | 0.6263 | [0.3953, 0.7363] |
| M2-topografico | VALIDACIÓN INSUFICIENTE | 0.6401 | [0.4374, 0.7488] |
| M4-bosque | NO VALIDADO | 0.5779 | [0.4837, 0.619] |
| M3-topo+litologia | VALIDACIÓN INSUFICIENTE | 0.5974 | [0.3641, 0.7094] |
| M3s-sin_Sedimento | VALIDACIÓN INSUFICIENTE | 0.5967 | [0.3634, 0.7098] |

## 1000|1500: 50 eventos externos

| Modelo | Estado | AUC externo (franja) | IC 95 % |
|---|---|---|---|
| V-pendiente_deg | EXPERIMENTAL | 0.6974 | [0.5672, 0.7943] |
| V-elevacion_m | VALIDACIÓN INSUFICIENTE | 0.6008 | [0.4082, 0.7523] |
| V-curvatura | EXPERIMENTAL | 0.6393 | [0.5469, 0.7091] |
| V-tpi_m | EXPERIMENTAL | 0.6796 | [0.5699, 0.7869] |
| V-dist_cauce_m | VALIDACIÓN EXTERNA PROMETEDORA | 0.7589 | [0.7067, 0.7906] |
| R1-solo_elevacion | VALIDACIÓN INSUFICIENTE | 0.6008 | [0.4082, 0.7523] |
| R2-heuristico_pendiente | NO VALIDADO | 0.3029 | [0.2059, 0.4315] |
| M1-base | VALIDACIÓN INSUFICIENTE | 0.5876 | [0.3968, 0.739] |
| M2-topografico | EXPERIMENTAL | 0.6748 | [0.5773, 0.7733] |
| M4-bosque | EXPERIMENTAL | 0.6379 | [0.5108, 0.7658] |
| M3-topo+litologia | EXPERIMENTAL | 0.7012 | [0.6123, 0.8068] |
| M3s-sin_Sedimento | EXPERIMENTAL | 0.6855 | [0.5903, 0.7882] |

Recursos: {'pico_proceso_mb': 517.3, 'perfil': 'estandar', 'medido_en': 1795570886.0}
