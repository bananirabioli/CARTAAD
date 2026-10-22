"""Add N synthetic monitored sources to a client (to try the monitoring screen with 100+ pages).

Usage:  python scripts/seed_sources.py --n 100 [--client municipio-ejemplo]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.core import Client  # noqa: E402
from app.models.monitoring import MonitoredSource  # noqa: E402

KINDS = ["medio", "influencer", "pagina_ciudadana", "actor_politico"]
NETWORKS = ["facebook", "instagram", "x", "tiktok"]
PREFIX = {"medio": "Noticias", "influencer": "Opina", "pagina_ciudadana": "Vecinos de", "actor_politico": "Comité"}
PLACES = ["Colonia Centro", "Colonia Norte", "Colonia Sur", "Lomas del Valle", "Barrio Antiguo", "Fraccionamiento Jardines", "Ejido Ejemplo", "Zona Oriente"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--client", default="municipio-ejemplo")
    args = parser.parse_args()
    rng = random.Random(42)
    with SessionLocal() as db:
        client = db.scalar(select(Client).where(Client.slug == args.client))
        if not client:
            raise SystemExit(f"cliente no encontrado: {args.client}")
        start = db.scalar(select(MonitoredSource.id).order_by(MonitoredSource.id.desc()).limit(1)) or 0
        for i in range(args.n):
            kind = rng.choice(KINDS)
            name = f"{PREFIX[kind]} {rng.choice(PLACES)} {start + i + 1}"
            db.add(
                MonitoredSource(
                    client_id=client.id, name=name, network=rng.choice(NETWORKS), handle=f"@fuente{start + i + 1}", source_type=kind,
                    priority=rng.choice(["alta", "media", "media", "baja", "baja"]), check_frequency_minutes=rng.choice([60, 120, 240]),
                    active=rng.random() > 0.1, adapter="mock", notes="Fuente sintética (scripts/seed_sources.py)",
                )
            )
        db.commit()
    print(f"{args.n} fuentes agregadas a {args.client}")


if __name__ == "__main__":
    main()
