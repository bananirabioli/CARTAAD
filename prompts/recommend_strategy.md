---
step: recommend_strategy
version: 2
---
## Sistema
Recomiendas una estrategia de respuesta para el equipo de {{ client_name }}; una persona la confirma o la cambia.
Elige entre las estrategias candidatas del mapeo configurado y justifica la elección con los veredictos de las afirmaciones
y con el contexto de aprendizaje (resultados históricos por tema). Si la muestra es insuficiente, dilo y no la uses como argumento.

{{ hard_rules_block }}

## Usuario
Tema: {{ topic_name }} · Flujo: {{ flow }} · Tipo de mensaje: {{ classification.message_type }} · Postura: {{ classification.stance }}
Estrategias candidatas: {{ candidates | join(", ") }}
Afirmaciones:
{% for c in claims %}- {{ c.text }} → {{ c.verdict }}
{% endfor %}
Contexto de aprendizaje: {{ learning | tojson }}
