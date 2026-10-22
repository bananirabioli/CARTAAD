"""Monitoring seed: sources with snapshot history (baselines), ~40 synthetic posts covering every stance, message type
and alert level, and the client's registered accounts (one per format)."""

import json
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.sources import RawPost, RawSnapshot
from app.config import FIXTURES_DIR
from app.db import utcnow
from app.models.core import Client, User
from app.models.monitoring import MonitoredSource, OwnedAccount, Post
from app.services.alert import apply_alert, refresh_source_baseline
from app.services.client_settings import get_client_settings
from app.services.ingest import store_post

TARGET_RATIO = {"bajo": 0.7, "medio": 2.3, "alto": 4.3, "critico": 8.8, "sin_linea_base": 2.5}
SNAP_HOURS = [1, 2, 4, 6, 9, 12, 18, 24, 30, 36, 42, 48]
HISTORY_TEXTS = [
    "Resumen semanal de noticias locales del Valle.",
    "Agenda cultural del fin de semana en la plaza principal.",
    "Pronóstico del clima para la semana en el Valle.",
    "Recomendaciones de tránsito para el regreso a clases.",
    "Así se vivió el tianguis dominical en la Colonia Centro.",
    "Horarios de atención en oficinas públicas durante el puente.",
    "Concurso de fotografía vecinal: se amplía la convocatoria.",
    "Mercado de productores locales este sábado.",
]

ACCOUNTS = [
    ("facebook", "@MunicipioEjemploContexto", "Municipio Ejemplo · Contexto", "propia", "formato_contexto", None, True),
    ("instagram", "@MunicipioEjemploExplica", "Municipio Ejemplo Explica", "propia", "formato_historieta", None, True),
    ("tiktok", "@ElTeatrinoDelValle", "El Teatrino del Valle", "propia", "formato_titeres", None, True),
    ("facebook", "@DatosLadoALado", "Datos Lado a Lado", "propia", "formato_comparativa", None, True),
    ("instagram", "@VocesDeLaColonia", "Voces de la Colonia", "propia", "formato_voz_pueblo", None, True),
    ("facebook", "@CronicaMunicipal", "Crónica Municipal", "propia", "formato_clasico", "institucional", True),
    ("facebook", "@ColectivoVecinalAliado", "Colectivo Vecinal (aliado)", "aliada", "formato_clasico", "cercano", True),
    ("x", "@VoceriaObrasPublicas", "Vocería de Obras Públicas", "voceria", "formato_clasico", "institucional", True),
    ("facebook", "@CuentaPendienteRegistro", "Cuenta pendiente de registro", "propia", "formato_clasico", None, False),
]


def _fixture() -> dict:
    return json.loads((FIXTURES_DIR / "mock" / "seed_posts.json").read_text(encoding="utf-8"))


def _split(total: int) -> tuple[int, int, int]:
    likes, comments = int(total * 0.7), int(total * 0.2)
    return likes, comments, total - likes - comments


def _history(db: Session, client: Client, source: MonitoredSource, days: int, baseline: float, now) -> None:  # noqa: ANN001
    step = max(2, days // 8)
    for i, day in enumerate(range(days, 3, -step)):
        published = now - timedelta(days=day, hours=i % 5)
        snaps = []
        for h in (6, 24, 48, 72):
            taken = published + timedelta(hours=h)
            if taken < now - timedelta(days=2):
                snaps.append(RawSnapshot(taken, *_split(int(baseline * h))))
        raw = RawPost(text=f"{HISTORY_TEXTS[i % len(HISTORY_TEXTS)]} ({source.name})", published_at=published, network=source.network, snapshots=snaps)
        store_post(db, client, raw, source=source, run_pipeline=False, is_history=True)


def seed_monitoring_client(db: Session, client: Client, data: dict, only: set[str] | None = None) -> None:
    now = utcnow()
    sources: dict[str, MonitoredSource] = {}
    for spec in data["sources"]:
        if only and spec["key"] not in only:
            continue
        src = MonitoredSource(
            client_id=client.id, name=spec["name"], network=spec["network"], handle=spec["handle"], source_type=spec["source_type"], priority=spec["priority"],
            check_frequency_minutes=60 if spec["priority"] == "alta" else 180, adapter="mock", last_checked_at=now - timedelta(minutes=20),
        )
        db.add(src)
        db.flush()
        _history(db, client, src, spec["history_days"], spec["baseline"], now)
        refresh_source_baseline(db, src, now)
        sources[spec["key"]] = src
    baselines = {k: s.baseline_per_hour or 1.0 for k, s in sources.items()}
    settings = get_client_settings(client)
    for spec in data["posts"]:
        src = sources.get(spec["source"])
        if src is None:
            continue
        rate = TARGET_RATIO[spec["alert"]] * baselines[spec["source"]]
        published = now - timedelta(hours=spec["hours_ago"])
        hours = [h for h in SNAP_HOURS if h < spec["hours_ago"]] + [spec["hours_ago"]]
        snaps = [RawSnapshot(published + timedelta(hours=h), *_split(int(rate * h))) for h in hours]
        raw = RawPost(text=spec["text"], published_at=published, network=src.network, snapshots=snaps, comments=[{"text": c} for c in spec["comments"]],
                      meta={"growth_per_hour": rate, "seed": {k: spec[k] for k in ("stance", "message_type", "topic", "alert")}})
        post, _ = store_post(db, client, raw, source=src, run_pipeline=False)
        apply_alert(post, settings, now)
    db.flush()


def seed_accounts(db: Session, client: Client, specs: list[tuple], admin: User | None) -> None:
    now = utcnow()
    for network, handle, name, atype, fmt, style, registered in specs:
        db.add(
            OwnedAccount(
                client_id=client.id, network=network, handle=handle, display_name=name, account_type=atype, format_slug=fmt, default_style_slug=style,
                registered=registered, verified=registered, verified_by_id=admin.id if (admin and registered) else None, verified_at=now if registered else None,
                notes="" if registered else "Cuenta de prueba sin registro: sirve para demostrar HR-02.",
            )
        )


def seed_monitoring(db: Session, clients: dict[str, Client]) -> None:
    municipio = clients["municipio-ejemplo"]
    if db.scalar(select(Post.id).where(Post.client_id == municipio.id).limit(1)):
        return
    admin = db.scalar(select(User).where(User.role == "admin"))
    data = _fixture()
    seed_monitoring_client(db, municipio, data)
    seed_accounts(db, municipio, ACCOUNTS, admin)

    candidatura = clients["candidatura-ejemplo"]
    small = {"sources": [s for s in data["sources"] if s["key"] in {"noticias_valle", "opinador", "partido_azul"}], "posts": [p for p in data["posts"] if p["source"] in {"opinador", "partido_azul"}][:5]}
    seed_monitoring_client(db, candidatura, small)
    seed_accounts(db, candidatura, [("facebook", "@CandidaturaCiudadanaEj", "Candidatura Ciudadana Ejemplo", "propia", "formato_clasico", "cercano", True),
                                    ("instagram", "@CandidaturaExplica", "Candidatura Explica", "propia", "formato_historieta", None, True)], admin)
    db.flush()
