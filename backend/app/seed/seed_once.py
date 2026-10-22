"""Seed demo data only when the database has no clients yet (used by the container entrypoint)."""

import logging

from app.seed.seed import seed_if_empty

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("seed: datos demo cargados" if seed_if_empty() else "seed: la base ya tenía datos")
