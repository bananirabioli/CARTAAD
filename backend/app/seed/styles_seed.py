"""Directives and modo veda seed (fictitious). Includes, on purpose: a conflicting pair, one that violates a hard rule
and one that clashes with a scheduled veda."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import next_code
from app.db import utcnow
from app.models.core import Client, User
from app.models.ops import RestrictionMode
from app.models.styles import Directive
from app.services.directive_checker import check_directive

F3, F4 = "formato_titeres", "formato_comparativa"


def _directives(now) -> list[dict]:  # noqa: ANN001
    return [
        dict(dtype="narrativa", title="Responsabilidad compartida entre niveles de gobierno", mandatory="obligatoria", priority=70,
             text="Al explicar un problema de servicios, mencionar que es una responsabilidad compartida entre municipio, estado y federación, con el dato de inversión de cada nivel cuando exista.",
             structured={"vocabulario_obligatorio": ["responsabilidad compartida"]}, scope={"topics": ["baches", "agua"], "flows": ["A"]}, status="activa"),
        dict(dtype="linea_roja", title="No culpar a otro nivel de gobierno sin un hecho que lo respalde", mandatory="obligatoria", priority=90,
             text="Toda mención a otro nivel de gobierno se limita a lo que dice un hecho de la base; nada de culpas genéricas.",
             structured={"vocabulario_prohibido": ["por culpa de", "es culpa del", "la culpa es"]}, scope={}, status="activa"),
        dict(dtype="leyenda", title="Leyenda de transparencia en piezas con cifras", mandatory="obligatoria", priority=60,
             text="Las piezas del clásico post en Flujo A llevan la leyenda de transparencia.",
             structured={"leyenda_texto": "Datos con fuente oficial: consulte el documento citado."}, scope={"formats": ["formato_clasico"], "flows": ["A"]}, status="activa"),
        dict(dtype="prioridad_tematica", title="Prioridad temática: agua durante el estiaje", mandatory="sugerida", priority=50,
             text="Durante el estiaje, priorizar respuestas sobre abasto y fugas de agua.", structured={"temas_prioritarios": ["agua"]}, scope={}, status="activa"),
        dict(dtype="vocabulario", title="Vocabulario institucional", mandatory="sugerida", priority=40,
             text="Preferir «obra» y «trabajo» en lugar de expresiones coloquiales.", structured={"vocabulario_prohibido": ["chamba"], "vocabulario_preferido": ["obra", "trabajo"]}, scope={}, status="activa"),
        dict(dtype="estilo", title="Sin diminutivos paternalistas", mandatory="obligatoria", priority=55,
             text="Evitar diminutivos que suenen condescendientes.", structured={"vocabulario_prohibido": ["obrita", "callecita", "vecinito"]}, scope={}, status="activa"),
        dict(dtype="vocabulario", title="Destacar la inversión histórica en obra pública", mandatory="obligatoria", priority=60,
             text="En obra pública, usar la frase «inversión histórica» al hablar del presupuesto.", structured={"vocabulario_obligatorio": ["inversión histórica"]}, scope={"topics": ["obra_publica"]}, status="activa"),
        dict(dtype="vocabulario", title="Evitar triunfalismo", mandatory="obligatoria", priority=60,
             text="No usar adjetivos triunfalistas como «histórico» en ninguna pieza.", structured={"vocabulario_prohibido": ["histórica", "histórico"]}, scope={}, status="en_revision"),
        dict(dtype="estilo", title="Cuando falte el dato, redondear cifras sin citar fuente", mandatory="sugerida", priority=30,
             text="Si no hay dato oficial a la mano, redondear cifras sin citar fuente para responder rápido.", structured={}, scope={}, status="en_revision"),
        dict(dtype="prioridad_tematica", title="Impulsar la comparativa de inversión en obra", mandatory="sugerida", priority=45,
             text="Durante las próximas semanas, priorizar piezas en formato La comparativa sobre inversión en obra pública.",
             structured={"temas_prioritarios": ["obra_publica"]}, scope={"formats": [F4], "topics": ["obra_publica"]},
             valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=60), status="en_revision"),
        dict(dtype="linea_roja", title="Sin humor sobre víctimas o tragedias", mandatory="obligatoria", priority=95,
             text="Ninguna pieza satírica toca accidentes, víctimas o tragedias.", structured={"vocabulario_prohibido": ["víctima", "tragedia", "accidente"]}, scope={"styles": ["satirico"]}, status="activa"),
        dict(dtype="estilo", title="Respuestas firmes a datos falsos con intensidad cuatro", mandatory="obligatoria", priority=50,
             text="Para desmentir datos falsos con estilo directo, subir la intensidad a cuatro.", structured={"intensidad_requerida": 4}, scope={"styles": ["directo"]}, status="borrador"),
    ]


CANDIDATURA_DIRECTIVES = [
    dict(dtype="narrativa", title="Proponer antes que criticar", mandatory="obligatoria", priority=70, text="Cada contraste termina con una propuesta concreta.", structured={}, scope={}, status="activa"),
    dict(dtype="linea_roja", title="Sin ataques personales", mandatory="obligatoria", priority=95, text="Nunca adjetivar a personas; se contrastan datos y propuestas.", structured={"vocabulario_prohibido": ["inepto", "ratero"]}, scope={}, status="activa"),
]


def seed_veda(db: Session, client: Client, admin: User | None) -> RestrictionMode:
    existing = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == client.id))
    if existing:
        return existing
    now = utcnow()
    veda = RestrictionMode(
        client_id=client.id, name="Veda electoral de demostración", active=True, starts_at=now + timedelta(days=30), ends_at=now + timedelta(days=75),
        blocked_formats=[F3, F4], blocked_creatives=["agradecimiento", "carrusel_resultados"], mandatory_legends=["Información de interés público."],
        reason="Periodo de veda ficticio para la demo; el equipo lo gestiona manualmente (la app no interpreta la ley).", created_by_id=admin.id if admin else None,
    )
    db.add(veda)
    db.flush()
    return veda


def _create(db: Session, client: Client, spec: dict, creator: User | None, approver: User | None) -> Directive:
    status = spec.pop("status")
    d = Directive(client_id=client.id, code=next_code(db, client.id, "directive", "D"), version=1, status="borrador", created_by_id=creator.id if creator else None, **spec)
    db.add(d)
    db.flush()
    check_directive(db, d, use_ai=True)
    if d.status != "rechazada":
        d.status = status
        if status == "activa":
            d.approved_by_id, d.approved_at = (approver.id if approver else None), utcnow()
    return d


def seed_styles(db: Session, clients: dict[str, Client]) -> None:
    municipio = clients["municipio-ejemplo"]
    if db.scalar(select(Directive.id).where(Directive.client_id == municipio.id).limit(1)):
        return
    admin = db.scalar(select(User).where(User.role == "admin"))
    analyst = db.scalar(select(User).where(User.role == "analista", User.kb_owner.is_(False)))
    seed_veda(db, municipio, admin)
    created = [_create(db, municipio, spec, analyst, admin) for spec in _directives(utcnow())]
    # Re-check once everything exists so pair conflicts are reported on both sides.
    for d in created:
        if d.status != "rechazada":
            check_directive(db, d, use_ai=False)
    for spec in CANDIDATURA_DIRECTIVES:
        _create(db, clients["candidatura-ejemplo"], dict(spec), analyst, admin)
    db.flush()
