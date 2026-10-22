"""Knowledge-base seed (fictitious). Years are relative to the current date so the demo stays coherent."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import embed
from app.api.deps import next_code
from app.db import utcnow
from app.models.core import Client, Topic, User
from app.models.kb import Actor, ApprovedImage, Brief, Competence, Fact, GovLevel, KeyMessage, ResponseHistory, SourceDocument
from app.seed import placeholder_images as ph
from app.services.documents import index_document, make_text_pdf
from app.services.facts import refresh_embedding
from app.storage import client_key, get_storage


def base_year() -> int:
    now = utcnow()
    return now.year if now.month >= 7 else now.year - 1


def d(y: int, m: int, day: int) -> datetime:
    return datetime(y, m, day, tzinfo=UTC)


def _ids(db: Session, client: Client) -> tuple[dict[str, int], dict[str, int]]:
    topics = {t.slug: t.id for t in db.scalars(select(Topic).where(Topic.client_id == client.id))}
    levels = {g.slug: g.id for g in db.scalars(select(GovLevel).where(GovLevel.client_id == client.id))}
    return topics, levels


def _documents(y: int) -> list[dict]:
    return [
        {
            "key": "obra",
            "title": f"Informe semestral de obra pública y servicios, enero–junio {y}",
            "issuer": "Dirección de Obras Públicas · Municipio Ejemplo",
            "doc_type": "informe",
            "issued_at": d(y, 7, 10),
            "level": "municipio",
            "topic": "obra_publica",
            "body": [
                f"Durante el primer semestre de {y} la Dirección de Obras Públicas del Municipio Ejemplo reparó 8,320 baches en vialidades municipales y repavimentó 47.5 km de calles.",
                "El tiempo promedio de atención a un reporte de bache fue de 72 horas desde su registro en la línea de atención ciudadana.",
                f"En {y} se rehabilitaron 14 parques públicos y el Puente Vecinal Norte alcanzó un avance físico de 76% al 30 de septiembre.",
                "Las vialidades estatales que cruzan el municipio, como la Avenida Central, son responsabilidad del Gobierno Estatal Ejemplo conforme al convenio de coordinación vial.",
            ],
        },
        {
            "key": "presupuesto",
            "title": f"Presupuesto de egresos {y} del Municipio Ejemplo",
            "issuer": "Tesorería Municipal · Municipio Ejemplo",
            "doc_type": "presupuesto",
            "issued_at": d(y - 1, 12, 20),
            "level": "municipio",
            "topic": None,
            "body": [
                f"El presupuesto de egresos {y} asigna 182 millones de pesos a mantenimiento vial, 95 millones de pesos a agua potable y 410 millones de pesos a obra pública municipal.",
                "El Gobierno Federal Ejemplo aporta recursos a vialidades a través del fondo de infraestructura municipal.",
            ],
        },
        {
            "key": "convenio",
            "title": f"Convenio de coordinación vial Estado–Municipio {y}",
            "issuer": "Gobierno Estatal Ejemplo y Municipio Ejemplo",
            "doc_type": "convenio",
            "issued_at": d(y, 2, 15),
            "level": "estado",
            "topic": "baches",
            "body": [
                f"El Gobierno Estatal Ejemplo aporta 64 millones de pesos para vialidades del municipio durante {y}.",
                "El 38% de las vialidades reportadas en redes sociales por baches corresponden a carreteras estatales.",
                f"De la inversión total en vialidades del municipio en {y}, el Municipio Ejemplo aporta el 66%, el Gobierno Estatal Ejemplo el 23% y el Gobierno Federal Ejemplo el 11%.",
            ],
        },
        {
            "key": "seguridad",
            "title": f"Reporte mensual de seguridad pública, septiembre {y}",
            "issuer": "Secretaría de Seguridad Ciudadana · Municipio Ejemplo",
            "doc_type": "estadistica",
            "issued_at": d(y, 10, 5),
            "level": "municipio",
            "topic": "seguridad",
            "body": [
                f"Los robos a transeúnte disminuyeron 18% entre septiembre de {y - 1} y septiembre de {y}.",
                f"En septiembre de {y} el municipio operó 142 patrullas en servicio y el tiempo promedio de respuesta a emergencias fue de 9 minutos.",
                f"Entre enero y septiembre de {y} se instalaron 2,600 luminarias LED en colonias prioritarias.",
                "La investigación y persecución de delitos corresponde a la Fiscalía del Estado Ejemplo.",
            ],
        },
        {
            "key": "agua",
            "title": f"Diagnóstico de la red de agua potable {y - 1}",
            "issuer": "Organismo Operador de Agua · Municipio Ejemplo",
            "doc_type": "diagnostico",
            "issued_at": d(y - 1, 11, 30),
            "level": "municipio",
            "topic": "agua",
            "body": [
                f"En {y - 1}, el 62% de las fugas reportadas se repararon en menos de 48 horas.",
                "La red municipal cuenta con 1,180 km de tubería y el 41% de la tubería supera la vida útil recomendada.",
                "El abasto de agua en bloque corresponde a la Comisión Estatal del Agua Ejemplo; la distribución en colonias corresponde al organismo operador municipal.",
            ],
        },
        {
            "key": "anual",
            "title": f"Informe anual {y - 1} del Municipio Ejemplo",
            "issuer": "Presidencia Municipal · Municipio Ejemplo",
            "doc_type": "informe",
            "issued_at": d(y, 1, 31),
            "level": "municipio",
            "topic": None,
            "body": [
                f"Entre enero y junio de {y - 1} se repararon 5,140 baches.",
                f"En {y - 2} se atendieron 3,900 reportes ciudadanos de baches.",
                f"En {y - 3} se entregaron 12,000 tinacos a hogares con tandeo.",
            ],
        },
        {
            "key": "estatal_obra",
            "title": f"Programa estatal de infraestructura {y}",
            "issuer": "Secretaría de Infraestructura · Gobierno Estatal Ejemplo",
            "doc_type": "programa",
            "issued_at": d(y, 3, 1),
            "level": "estado",
            "topic": "obra_publica",
            "body": [
                f"En {y} el Gobierno Estatal Ejemplo invierte 120 millones de pesos en obra pública dentro del Municipio Ejemplo.",
                "El programa incluye la rehabilitación de la Avenida Central, vialidad de jurisdicción estatal.",
            ],
        },
        {
            "key": "reglamento",
            "title": "Reglamento de vialidad y distribución de competencias",
            "issuer": "Cabildo · Municipio Ejemplo",
            "doc_type": "reglamento",
            "issued_at": d(y - 2, 5, 12),
            "level": "municipio",
            "topic": "baches",
            "body": [
                "Las calles locales son de jurisdicción municipal. Las carreteras y avenidas estatales, como la Avenida Central, son de jurisdicción estatal.",
                "Las carreteras federales y autopistas son de jurisdicción federal.",
            ],
        },
    ]


def _facts(y: int) -> list[dict]:
    """(statement, value, unit, base, period_label, start, end, fact_date, doc, level, topic, valid_until)."""
    cur = d(y + 1, 12, 31)
    old = d(y - 1, 6, 30)
    return [
        # baches
        dict(statement=f"El Municipio Ejemplo reparó 8,320 baches entre enero y junio de {y}.", value=8320, unit="baches", period_label=f"enero–junio {y}", period_start=d(y, 1, 1), period_end=d(y, 6, 30), doc="obra", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"El Municipio Ejemplo repavimentó 47.5 km de calles en el primer semestre de {y}.", value=47.5, unit="km", period_label=f"enero–junio {y}", period_start=d(y, 1, 1), period_end=d(y, 6, 30), doc="obra", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"El presupuesto municipal para mantenimiento vial en {y} es de 182 millones de pesos.", value=182_000_000, unit="pesos", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="presupuesto", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"El Gobierno Estatal Ejemplo aporta 64 millones de pesos para vialidades del municipio en {y}.", value=64_000_000, unit="pesos", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="convenio", level="estado", topic="baches", valid_until=cur),
        dict(statement="El 38% de las vialidades reportadas en redes por baches son carreteras estatales.", value=38, unit="%", base="vialidades reportadas", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="convenio", level="estado", topic="baches", valid_until=cur),
        dict(statement="La Avenida Central es una vialidad de jurisdicción estatal.", value=None, unit="", period_label="vigente", doc="reglamento", level="estado", topic="baches", valid_until=None),
        dict(statement="El tiempo promedio de atención a un reporte de bache es de 72 horas.", value=72, unit="horas", base="promedio", period_label=f"enero–junio {y}", period_start=d(y, 1, 1), period_end=d(y, 6, 30), doc="obra", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"Entre enero y junio de {y - 1} se repararon 5,140 baches.", value=5140, unit="baches", period_label=f"enero–junio {y - 1}", period_start=d(y - 1, 1, 1), period_end=d(y - 1, 6, 30), doc="anual", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"En {y - 2} se atendieron 3,900 reportes ciudadanos de baches.", value=3900, unit="reportes", period_label=str(y - 2), period_start=d(y - 2, 1, 1), period_end=d(y - 2, 12, 31), doc="anual", level="municipio", topic="baches", valid_until=old),
        dict(statement=f"El Municipio Ejemplo aporta el 66% de la inversión total en vialidades del municipio en {y}.", value=66, unit="%", base="inversión total en vialidades", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="convenio", level="municipio", topic="baches", valid_until=cur),
        dict(statement=f"El Gobierno Estatal Ejemplo aporta el 23% de la inversión total en vialidades del municipio en {y}.", value=23, unit="%", base="inversión total en vialidades", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="convenio", level="estado", topic="baches", valid_until=cur),
        dict(statement=f"El Gobierno Federal Ejemplo aporta el 11% de la inversión total en vialidades del municipio en {y}.", value=11, unit="%", base="inversión total en vialidades", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="convenio", level="federacion", topic="baches", valid_until=cur),
        # seguridad
        dict(statement=f"Los robos a transeúnte bajaron 18% entre septiembre de {y - 1} y septiembre de {y}.", value=18, unit="%", base="variación anual", period_label=f"septiembre {y - 1} – septiembre {y}", period_start=d(y - 1, 9, 1), period_end=d(y, 9, 30), doc="seguridad", level="municipio", topic="seguridad", valid_until=cur),
        dict(statement=f"El municipio operó 142 patrullas en servicio en septiembre de {y}.", value=142, unit="patrullas", period_label=f"septiembre {y}", period_start=d(y, 9, 1), period_end=d(y, 9, 30), doc="seguridad", level="municipio", topic="seguridad", valid_until=cur),
        dict(statement=f"Se instalaron 2,600 luminarias LED entre enero y septiembre de {y}.", value=2600, unit="luminarias", period_label=f"enero–septiembre {y}", period_start=d(y, 1, 1), period_end=d(y, 9, 30), doc="seguridad", level="municipio", topic="seguridad", valid_until=cur),
        dict(statement="La investigación y persecución de delitos corresponde a la Fiscalía del Estado Ejemplo.", value=None, unit="", period_label="vigente", doc="seguridad", level="estado", topic="seguridad", valid_until=None),
        dict(statement="El tiempo promedio de respuesta a emergencias es de 9 minutos.", value=9, unit="minutos", base="promedio", period_label=f"septiembre {y}", period_start=d(y, 9, 1), period_end=d(y, 9, 30), doc="seguridad", level="municipio", topic="seguridad", valid_until=cur),
        dict(statement="Se capacitó a 300 policías en proximidad social.", value=300, unit="policías", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc=None, level="municipio", topic="seguridad", valid_until=cur, notes="Dato pendiente de documento de origen (sirve para demostrar HR-01)."),
        # agua
        dict(statement=f"El 62% de las fugas reportadas en {y - 1} se repararon en menos de 48 horas.", value=62, unit="%", base="fugas reportadas", period_label=str(y - 1), period_start=d(y - 1, 1, 1), period_end=d(y - 1, 12, 31), doc="agua", level="municipio", topic="agua", valid_until=cur),
        dict(statement="La red municipal de agua tiene 1,180 km de tubería.", value=1180, unit="km", period_label=str(y - 1), period_start=d(y - 1, 1, 1), period_end=d(y - 1, 12, 31), doc="agua", level="municipio", topic="agua", valid_until=cur),
        dict(statement="El 41% de la tubería municipal supera la vida útil recomendada.", value=41, unit="%", base="tubería municipal", period_label=str(y - 1), period_start=d(y - 1, 1, 1), period_end=d(y - 1, 12, 31), doc="agua", level="municipio", topic="agua", valid_until=cur),
        dict(statement=f"La inversión municipal en agua potable para {y} es de 95 millones de pesos.", value=95_000_000, unit="pesos", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="presupuesto", level="municipio", topic="agua", valid_until=cur),
        dict(statement="El abasto de agua en bloque corresponde a la Comisión Estatal del Agua Ejemplo.", value=None, unit="", period_label="vigente", doc="agua", level="estado", topic="agua", valid_until=None),
        dict(statement=f"En {y - 3} se entregaron 12,000 tinacos a hogares con tandeo.", value=12000, unit="tinacos", period_label=str(y - 3), period_start=d(y - 3, 1, 1), period_end=d(y - 3, 12, 31), doc="anual", level="municipio", topic="agua", valid_until=old),
        # obra pública
        dict(statement=f"El Puente Vecinal Norte tiene un avance físico de 76% al 30 de septiembre de {y}.", value=76, unit="%", base="avance físico", period_label=f"al 30 de septiembre de {y}", fact_date=d(y, 9, 30), period_end=d(y, 9, 30), doc="obra", level="municipio", topic="obra_publica", valid_until=cur),
        dict(statement=f"Se rehabilitaron 14 parques públicos en {y}.", value=14, unit="parques", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="obra", level="municipio", topic="obra_publica", valid_until=cur),
        dict(statement=f"La inversión en obra pública municipal en {y} suma 410 millones de pesos.", value=410_000_000, unit="pesos", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="presupuesto", level="municipio", topic="obra_publica", valid_until=cur),
        dict(statement=f"El Gobierno Estatal Ejemplo invierte 120 millones de pesos en obra pública en el municipio en {y}.", value=120_000_000, unit="pesos", period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), doc="estatal_obra", level="estado", topic="obra_publica", valid_until=cur),
        dict(statement=f"La obra del Puente Vecinal Norte se adjudicó por licitación pública el 15 de marzo de {y}.", value=None, unit="", period_label=f"15 de marzo de {y}", fact_date=d(y, 3, 15), doc="obra", level="municipio", topic="obra_publica", valid_until=cur),
        dict(statement="La Avenida Central se rehabilita con recursos del programa estatal de infraestructura.", value=None, unit="", period_label=str(y), doc="estatal_obra", level="estado", topic="obra_publica", valid_until=cur),
    ]


BRIEFS = {
    "baches": (
        "Baches: jurisdicción y responsabilidad compartida",
        """## Contexto
Las calles locales son responsabilidad del municipio; las avenidas estatales (como la **Avenida Central**) del Gobierno Estatal Ejemplo.

## Qué decir
- Explicar la **responsabilidad compartida** entre niveles de gobierno con los porcentajes de inversión del convenio vial.
- Dar el avance del semestre con fuente.
- Si el reporte es de una calle local: canalizar y dar folio.

## Qué no decir
- No culpar a otro nivel sin dato de la base.
- No prometer fechas sin compromiso registrado.
""",
    ),
    "seguridad": (
        "Seguridad: proximidad y datos abiertos",
        """## Contexto
La policía preventiva y el alumbrado son municipales; la investigación de delitos es de la Fiscalía del Estado Ejemplo.

## Qué decir
- Datos del reporte mensual con fuente.
- Reconocer la percepción de inseguridad antes de dar cifras.

## Qué no decir
- No minimizar casos individuales.
""",
    ),
    "agua": (
        "Agua: red antigua y abasto en bloque",
        """## Contexto
El abasto en bloque depende de la Comisión Estatal del Agua Ejemplo; la distribución y las fugas, del organismo operador municipal.

## Qué decir
- Reconocer el problema y explicar el plan de renovación de tubería.
- Canalizar reportes de fugas a atención ciudadana.
""",
    ),
    "obra_publica": (
        "Obra pública: avance verificable",
        """## Contexto
El Puente Vecinal Norte y la rehabilitación de parques son obra municipal; la Avenida Central es obra estatal.

## Qué decir
- Avance físico con fecha de corte.
- Comparar inversión solo con el mismo periodo y la misma base.
""",
    ),
}

KEY_MESSAGES = [
    ("baches", "Mantener las calles es una responsabilidad compartida entre municipio, estado y federación.", 80),
    ("baches", "Cada reporte de bache tiene folio y seguimiento público.", 70),
    ("seguridad", "La seguridad se construye con proximidad y datos abiertos.", 70),
    ("agua", "El agua es prioridad: renovamos primero la red más antigua.", 75),
    ("obra_publica", "Obra que se ve: avance público y verificable.", 65),
    (None, "Informamos con datos y fuente; si falta un dato, lo decimos.", 90),
]

ACTORS = [
    ("Municipio Ejemplo", ["el municipio", "Ayuntamiento Ejemplo", "el ayuntamiento", "la alcaldía"], "gobierno_municipal", "municipio", True),
    ("Gobierno Estatal Ejemplo", ["Gobierno del Estado", "el gobierno estatal", "gobierno estatal"], "gobierno_estatal", "estado", False),
    ("Gobierno Federal Ejemplo", ["la Federación", "el gobierno federal", "gobierno federal"], "gobierno_federal", "federacion", False),
    ("Partido Azul", ["los azules", "PAZ"], "partido", None, False),
    ("Partido Verde Limón", ["PVL", "los verdes"], "partido", None, False),
    ("Comisión Estatal del Agua Ejemplo", ["CEA Ejemplo", "la comisión del agua"], "organismo", "estado", False),
    ("Fiscalía del Estado Ejemplo", ["la Fiscalía", "fiscalía estatal"], "organismo", "estado", False),
    ("Presidencia Municipal", ["el alcalde", "la alcaldesa", "presidencia municipal"], "funcionario_rol", "municipio", True),
]

COMPETENCES = [
    ("municipio", "baches", "Mantenimiento y bacheo de calles locales.", "Reglamento de vialidad, art. 4"),
    ("estado", "baches", "Carreteras y avenidas estatales que cruzan el municipio (p. ej., Avenida Central).", "Convenio de coordinación vial"),
    ("federacion", "baches", "Carreteras federales y autopistas.", "Ley federal de caminos (referencia ficticia)"),
    ("municipio", "seguridad", "Policía preventiva y de proximidad; alumbrado público.", "Reglamento de seguridad ciudadana"),
    ("estado", "seguridad", "Investigación y persecución de delitos (Fiscalía).", "Ley orgánica de la Fiscalía (ficticia)"),
    ("federacion", "seguridad", "Delitos del fuero federal.", ""),
    ("municipio", "agua", "Distribución, fugas y drenaje a través del organismo operador.", "Reglamento del organismo operador"),
    ("estado", "agua", "Abasto de agua en bloque y acueductos.", "Ley estatal de aguas (ficticia)"),
    ("federacion", "agua", "Concesiones de aguas nacionales.", ""),
    ("municipio", "obra_publica", "Obra en calles locales, parques y equipamiento municipal.", ""),
    ("estado", "obra_publica", "Infraestructura estatal dentro del municipio.", "Programa estatal de infraestructura"),
    ("federacion", "obra_publica", "Fondos federales de infraestructura.", ""),
]

IMAGES = [
    ("Avenida Central — antes de la repavimentación", "street", "before", "foto_real", "baches", ["baches", "antes", "avenida central"], -560),
    ("Avenida Central — después de la repavimentación", "street", "after", "foto_real", "baches", ["baches", "despues", "avenida central"], -150),
    ("Cuadrilla de bacheo en Colonia Centro", "street", "crew", "foto_real", "baches", ["baches", "cuadrilla"], -40),
    ("Patrulla de proximidad en recorrido", "scene", "patrol", "foto_real", "seguridad", ["seguridad", "patrulla"], -60),
    ("Luminarias LED en Calle Hidalgo Ejemplo", "scene", "lights", "foto_real", "seguridad", ["seguridad", "luminarias"], -90),
    ("Reparación de fuga en Colonia Norte", "scene", "pipe", "foto_real", "agua", ["agua", "fuga"], -30),
    ("Puente Vecinal Norte — avance de obra", "scene", "bridge", "foto_real", "obra_publica", ["obra", "puente"], -25),
    ("Parque Las Flores rehabilitado", "scene", "park", "foto_real", "obra_publica", ["obra", "parque"], -70),
    ("Ilustración: calle reparada", "illustration", "street", "ilustracion", "baches", ["ilustracion", "calle"], -10),
    ("Ilustración: vecinos en asamblea", "illustration", "people", "ilustracion", None, ["ilustracion", "vecinos"], -10),
]

# (topic, format, style, strategy, creative, outcome, reach_ratio, sentiment_delta, days_ago)
HISTORY = [
    ("baches", "formato_contexto", "cercano", "contextualizar", "contexto_responsabilidad", "funciono", 1.8, 0.22, 160),
    ("baches", "formato_contexto", "cercano", "contextualizar", "dato_duro", "funciono", 1.4, 0.15, 140),
    ("baches", "formato_clasico", "cercano", "contextualizar", "antes_despues", "funciono", 2.1, 0.3, 120),
    ("baches", "formato_contexto", "cercano", "desmentir", "mito_vs_realidad", "no_funciono", 0.6, -0.05, 100),
    ("baches", "formato_clasico", "cercano", "contextualizar", "linea_tiempo", "funciono", 1.2, 0.1, 80),
    ("baches", "formato_contexto", "cercano", "contextualizar", "contexto_responsabilidad", "funciono", 1.6, 0.18, 60),
    ("baches", "formato_clasico", "cercano", "desmentir", "dato_duro", "no_funciono", 0.7, 0.0, 45),
    ("baches", "formato_contexto", "directo", "desmentir", "mito_vs_realidad", "no_funciono", 0.9, -0.12, 30),
    ("baches", "formato_historieta", "didactico", "contextualizar", "infografia", "funciono", 1.9, 0.2, 20),
    ("seguridad", "formato_clasico", "institucional", "contextualizar", "dato_duro", "funciono", 1.1, 0.05, 90),
    ("seguridad", "formato_contexto", "directo", "desmentir", "mito_vs_realidad", "no_funciono", 0.5, -0.1, 50),
    ("seguridad", "formato_clasico", "empatico", "contextualizar", "lo_que_no_se_vio", "funciono", 1.3, 0.12, 15),
    ("agua", "formato_clasico", "empatico", "contextualizar", "contexto_responsabilidad", "funciono", 1.5, 0.25, 110),
    ("agua", "formato_clasico", "empatico", "contextualizar", "linea_tiempo", "funciono", 1.2, 0.2, 95),
    ("agua", "formato_voz_pueblo", "voz_ciudadana_representativa", "reencuadrar", "pregunta_minimalista", "no_funciono", 0.8, -0.02, 75),
    ("agua", "formato_clasico", "institucional", "contextualizar", "dato_duro", "no_funciono", 0.7, -0.04, 55),
    ("agua", "formato_clasico", "empatico", "contextualizar", "carrusel_explicativo", "funciono", 1.7, 0.18, 35),
    ("agua", "formato_contexto", "institucional", "desmentir", "mito_vs_realidad", "funciono", 1.3, 0.08, 12),
    ("obra_publica", "formato_comparativa", "contrastivo", "contrastar", "antes_despues", "funciono", 2.4, 0.15, 85),
    ("obra_publica", "formato_clasico", "periodistico", "amplificar", "carrusel_resultados", "funciono", 1.9, 0.2, 40),
    ("obra_publica", "formato_titeres", "satirico", "reencuadrar", "carrusel_explicativo", "no_funciono", 1.1, -0.2, 25),
    ("obra_publica", "formato_clasico", "reconocimiento", "agradecer", "agradecimiento", "funciono", 1.4, 0.3, 10),
]


def seed_kb_municipio(db: Session, client: Client) -> None:
    if db.scalar(select(Fact.id).where(Fact.client_id == client.id).limit(1)):
        return
    y = base_year()
    topics, levels = _ids(db, client)
    storage = get_storage()
    kb_owner = db.scalar(select(User).where(User.kb_owner.is_(True)))
    now = utcnow()

    docs: dict[str, SourceDocument] = {}
    for spec in _documents(y):
        doc = SourceDocument(
            client_id=client.id, title=spec["title"], issuer=spec["issuer"], doc_type=spec["doc_type"], issued_at=spec["issued_at"],
            gov_level_id=levels.get(spec["level"]), topic_id=topics.get(spec["topic"]) if spec["topic"] else None,
        )
        db.add(doc)
        db.flush()
        pdf = make_text_pdf(spec["title"], [spec["issuer"], *spec["body"]])
        doc.file_key = storage.save(client_key(client.id, "documents", f"{doc.id}.pdf"), pdf, "application/pdf")
        index_document(db, doc, [f"{spec['issuer']}\n" + "\n".join(spec["body"])])
        docs[spec["key"]] = doc

    for i, spec in enumerate(_facts(y)):
        doc_key = spec.pop("doc")
        level = spec.pop("level")
        topic = spec.pop("topic")
        fact = Fact(
            client_id=client.id, code=next_code(db, client.id, "fact", "H"),
            document_id=docs[doc_key].id if doc_key else None, gov_level_id=levels.get(level), topic_id=topics.get(topic), **spec,
        )
        if fact.fact_date is None and doc_key:
            fact.fact_date = docs[doc_key].issued_at
        if kb_owner and i % 5 != 4:  # most facts verified; a few left pending on purpose
            fact.verified_by_id, fact.verified_at = kb_owner.id, now - timedelta(days=3)
        refresh_embedding(fact)
        db.add(fact)

    for slug, (title, body) in BRIEFS.items():
        db.add(Brief(client_id=client.id, topic_id=topics.get(slug), title=title, body_md=body, embedding=embed(f"{title} {body}"), updated_by_id=kb_owner.id if kb_owner else None))
    for slug, text, prio in KEY_MESSAGES:
        db.add(KeyMessage(client_id=client.id, topic_id=topics.get(slug) if slug else None, text=text, priority=prio))
    for name, aliases, atype, level, own in ACTORS:
        db.add(Actor(client_id=client.id, name=name, aliases=aliases, actor_type=atype, gov_level_id=levels.get(level) if level else None, is_own=own))
    for level, topic, desc, basis in COMPETENCES:
        db.add(Competence(client_id=client.id, gov_level_id=levels[level], topic_id=topics.get(topic), description=desc, legal_basis=basis))

    for i, (title, family, kind, itype, topic, tags, days) in enumerate(IMAGES):
        maker = {"street": ph.street, "scene": ph.scene, "illustration": ph.illustration}[family]
        data = maker(kind, 100 + i, title)
        img = ApprovedImage(
            client_id=client.id, title=title, image_type=itype, topic_id=topics.get(topic) if topic else None, tags=tags,
            credit="Archivo fotográfico municipal (placeholder de demo)" if itype == "foto_real" else "Equipo de diseño (ilustración de demo)",
            license="Uso institucional" if itype == "foto_real" else "Propia", taken_at=now + timedelta(days=days), file_key="",
            meta={"placeholder": True, "ilustracion": itype == "ilustracion"},
        )
        db.add(img)
        db.flush()
        img.file_key = storage.save(client_key(client.id, "images", f"{img.id}.png"), data, "image/png")

    for topic, fmt, style, strategy, creative, outcome, reach, sentiment, days in HISTORY:
        db.add(
            ResponseHistory(
                client_id=client.id, topic_slug=topic, format_slug=fmt, style_slug=style, strategy=strategy, creative_slug=creative,
                flow="B" if strategy in ("amplificar", "agradecer") else "A", outcome=outcome, reach_ratio=reach, sentiment_delta=sentiment,
                summary="Respuesta histórica de demostración.", created_at=now - timedelta(days=days),
            )
        )
    db.flush()


def seed_kb_candidatura(db: Session, client: Client) -> None:
    if db.scalar(select(Fact.id).where(Fact.client_id == client.id).limit(1)):
        return
    y = base_year()
    topics, levels = _ids(db, client)
    storage = get_storage()
    doc = SourceDocument(
        client_id=client.id, title=f"Encuesta ciudadana de movilidad {y} (ficticia)", issuer="Instituto Estadístico Ejemplo", doc_type="estadistica", issued_at=d(y, 8, 1),
    )
    db.add(doc)
    db.flush()
    body = [
        f"El 54% de los hogares encuestados en {y} reporta al menos un bache en su calle.",
        f"El 61% de las personas encuestadas en {y} considera que el alumbrado de su colonia es insuficiente.",
    ]
    doc.file_key = storage.save(client_key(client.id, "documents", f"{doc.id}.pdf"), make_text_pdf(doc.title, body), "application/pdf")
    index_document(db, doc, ["\n".join(body)])
    for statement, value, topic, base in [
        (body[0], 54, "baches", "hogares encuestados"),
        (body[1], 61, "seguridad", "personas encuestadas"),
    ]:
        fact = Fact(
            client_id=client.id, code=next_code(db, client.id, "fact", "H"), statement=statement, value=value, unit="%", base=base,
            period_label=str(y), period_start=d(y, 1, 1), period_end=d(y, 12, 31), fact_date=doc.issued_at, document_id=doc.id,
            topic_id=topics.get(topic), valid_until=d(y + 1, 12, 31),
        )
        refresh_embedding(fact)
        db.add(fact)
    db.add(KeyMessage(client_id=client.id, text="Proponemos con datos: cada propuesta trae su fuente.", priority=80))
    db.add(Actor(client_id=client.id, name="Candidatura Ciudadana Ejemplo", aliases=["la candidatura"], actor_type="partido", is_own=True))
    db.add(Actor(client_id=client.id, name="Partido Azul", aliases=["los azules"], actor_type="partido"))
    db.flush()


def seed_kb(db: Session, clients: dict[str, Client]) -> None:
    seed_kb_municipio(db, clients["municipio-ejemplo"])
    seed_kb_candidatura(db, clients["candidatura-ejemplo"])
