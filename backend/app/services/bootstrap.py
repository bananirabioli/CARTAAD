"""Client bootstrap: every new client receives a private copy of the base templates (client_id = NULL).

Each milestone registers a cloner; the order matters (formats reference styles by slug, etc.).
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.core import Client

Cloner = Callable[[Session, Client], None]
_CLONERS: list[tuple[str, Cloner]] = []


def register_cloner(name: str) -> Callable[[Cloner], Cloner]:
    def deco(fn: Cloner) -> Cloner:
        if all(n != name for n, _ in _CLONERS):
            _CLONERS.append((name, fn))
        return fn

    return deco


def bootstrap_client(db: Session, client: Client) -> list[str]:
    from app.services import catalog_bootstrap  # noqa: F401  (registers cloners)

    done = []
    for name, fn in _CLONERS:
        fn(db, client)
        done.append(name)
    db.flush()
    return done
