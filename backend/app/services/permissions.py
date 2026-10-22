"""Role → permission matrix (section 11). `kb_owner` is a flag that adds KB curation permissions."""

from app.models.core import User

ANALISTA = {
    "case.capture",
    "case.classify_edit",
    "case.decide",
    "case.rate",
    "generation.run",
    "copilot.use",
    "piece.edit",
    "figure.verify",
    "directive.propose",
    "metrics.record",
    "kb.read",
    "audit.read_own",
}
APROBADOR = ANALISTA | {"piece.approve", "piece.discard", "schedule.manage", "ally.manage", "export.pieces", "audit.read"}
LEGAL = {"kb.read", "legal.review", "style.approve_high_risk", "directive.propose", "audit.read", "piece.legal"}
DISENO = {"kb.read", "piece.edit", "copilot.use", "assets.upload", "templates.edit", "style.visual_guide", "export.pieces"}
ADMIN = {
    "kb.read",
    "config.manage",
    "sources.manage",
    "catalog.manage",
    "style.edit",
    "style.activate",
    "style.visual_guide",
    "directive.propose",
    "directive.activate",
    "veda.manage",
    "users.manage",
    "audit.read",
    "templates.edit",
    "assets.upload",
    "case.capture",
}
KB_OWNER = {"kb.curate", "fact.verify", "figure.verify", "directive.propose", "directive.activate_kb", "assets.upload"}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "analista": ANALISTA,
    "aprobador": APROBADOR,
    "legal": LEGAL,
    "diseno": DISENO,
    "admin": ADMIN,
}

# Directive types a kb_owner may activate (section 11: "redactar y activar directrices de narrativa y vocabulario").
KB_OWNER_DIRECTIVE_TYPES = {"narrativa", "vocabulario"}


def permissions_for(user: User) -> set[str]:
    perms = set(ROLE_PERMISSIONS.get(user.role, set()))
    if user.kb_owner:
        perms |= KB_OWNER
    return perms


def has_permission(user: User, permission: str) -> bool:
    return permission in permissions_for(user)
