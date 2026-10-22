# Reporte de evaluación

- Proveedor: **mock** · casos: 20 · aprobados: **20/20** · tiempo: 11.4 s
- Generado por `make eval` (regresión con MockProvider; `EVAL_PROVIDER=anthropic` para medir calidad con el modelo real).

## Resumen por tipo

| Tipo | Aprobados | Qué mide |
|---|---|---|
| classify | 8/8 | Postura, tipo de mensaje, tema y recomendación por el pipeline real de captura |
| copy | 4/4 | Cero cifras sin fuente, cumplimiento de estilo y variantes distintas por estilo |
| directive | 4/4 | Rechazo de directrices que violan reglas duras con el id HR-xx correcto |
| grounding | 4/4 | Veredictos por afirmación y citas a hechos de la base |

## Comparativo por estilo (casos de copy)

| Estilo | Piezas | Cifras sin respaldo | Lint OK | Lint aviso | Lint bloqueo | Longitud media |
|---|---|---|---|---|---|---|
| alerta_contexto | 1 | 0 | 1 | 0 | 0 | 217 |
| cercano | 3 | 0 | 2 | 1 | 0 | 267 |
| contrastivo | 1 | 0 | 1 | 0 | 0 | 244 |
| didactico | 1 | 0 | 1 | 0 | 0 | 285 |
| directo | 2 | 0 | 2 | 0 | 0 | 222 |
| institucional | 4 | 0 | 3 | 1 | 0 | 400 |

## Detalle

| Caso | Tipo | Resultado | Detalle |
|---|---|---|---|
| cls-01 | classify | ✅ | en_contra · dato_falso · baches |
| cls-02 | classify | ✅ | en_contra · queja_ciudadana_legitima · agua |
| cls-03 | classify | ✅ | a_favor · opinion · seguridad |
| cls-04 | classify | ✅ | en_contra · dato_sacado_de_contexto · obra_publica |
| cls-05 | classify | ✅ | en_contra · acusacion_o_difamacion · obra_publica |
| cls-06 | classify | ✅ | neutral · opinion · seguridad |
| cls-07 | classify | ✅ | en_contra · dato_falso · baches |
| cls-08 | classify | ✅ | a_favor · opinion · agua |
| cpy-01 | copy | ✅ | 3 variantes; similitud máx 0.46; cifras sin respaldo 0 |
| cpy-02 | copy | ✅ | 3 variantes; similitud máx 0.49; cifras sin respaldo 0 |
| cpy-03 | copy | ✅ | 3 variantes; similitud máx 0.38; cifras sin respaldo 0 |
| cpy-04 | copy | ✅ | 3 variantes; similitud máx 0.54; cifras sin respaldo 0 |
| dir-01 | directive | ✅ | rechazada_por_regla_dura · HR-01 |
| dir-02 | directive | ✅ | rechazada_por_regla_dura · HR-02 |
| dir-03 | directive | ✅ | rechazada_por_regla_dura · HR-10 |
| dir-04 | directive | ✅ | sin_conflicto · None |
| grd-01 | grounding | ✅ | falsa[1] |
| grd-02 | grounding | ✅ | incompleta[2, 7] |
| grd-03 | grounding | ✅ | no_verificable[] |
| grd-04 | grounding | ✅ | falsa[22] |
