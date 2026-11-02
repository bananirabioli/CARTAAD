"""Seed only when the database has no clients yet (used by the container entrypoint).

DEMO_MODE=true loads the fictitious demo; DEMO_MODE=false creates the MVP client and master user only.
"""

import logging

from app.config import get_settings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if get_settings().demo_mode:
        from app.seed.seed import seed_if_empty

        print("seed: datos demo cargados" if seed_if_empty() else "seed: la base ya tenía datos")
    else:
        from app.seed.production import seed_production_if_empty

        print("seed: cliente y usuario maestro creados" if seed_production_if_empty() else "seed: la base ya tenía datos")
