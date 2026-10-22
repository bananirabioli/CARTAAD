"""Evaluation set runner (`make eval`).

Runs every case in /evals/cases against an isolated, freshly seeded SQLite database:
* classify   — stance / message type / topic / recommendation accuracy through the real capture pipeline;
* grounding  — claim verdicts and fact citations;
* copy       — generation in style variants: zero unsourced figures, style compliance, distinct variants;
* directive  — directives that violate a hard rule must be rejected with the right HR id.

Default provider: MockProvider (regression test). `EVAL_PROVIDER=anthropic` (or --provider anthropic) runs the same
cases against the real model as an optional quality check. Writes evals/report.md.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path


def _configure(provider: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cartaad-eval-"))
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{tmp / 'eval.db'}", "AUTO_SEED": "false", "PASSWORD_ITERATIONS": "1000", "CELERY_EAGER": "true",
        "STORAGE_DIR": str(tmp / "files"), "RENDERER": "pillow", "LLM_PROVIDER": provider,
    })
    return tmp


def _jaccard(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return len(wa & wb) / max(1, len(wa | wb))


def main() -> int:  # noqa: C901 - a linear script is clearer here
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default=os.environ.get("EVAL_PROVIDER") or "mock")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    _configure(args.provider)

    from sqlalchemy import select

    from app import models  # noqa: F401
    from app.config import EVALS_DIR
    from app.db import Base, SessionLocal, engine
    from app.models.cases import Case, Classification
    from app.models.core import Client, User
    from app.models.monitoring import OwnedAccount
    from app.models.styles import Directive
    from app.seed.seed import run_seed
    from app.services.capture import capture_manual
    from app.services.cases import decide
    from app.services.directive_checker import check_directive
    from app.services.generation import generate_proposal, start_generation

    Base.metadata.create_all(engine)
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((EVALS_DIR / "cases").glob("*.json"))]
    results: list[dict] = []
    per_style: dict[str, dict] = defaultdict(lambda: {"pieces": 0, "unsourced": 0, "lint_ok": 0, "lint_warn": 0, "lint_block": 0, "chars": 0})
    started = time.perf_counter()
    with SessionLocal() as db:
        run_seed(db)
        db.commit()
        client = db.scalar(select(Client).where(Client.slug == "municipio-ejemplo"))
        analyst = db.scalar(select(User).where(User.email == "analista@demo.mx"))
        for case_def in cases:
            kind, exp = case_def["kind"], case_def["expected"]
            checks: dict[str, bool] = {}
            detail = ""
            try:
                if kind in ("classify", "grounding"):
                    post = capture_manual(db, client, analyst, text=case_def["text"], network="facebook", source_name=f"Eval {case_def['id']}")
                    db.flush()
                    case = db.scalar(select(Case).where(Case.post_id == post.id))
                    cls = db.scalar(select(Classification).where(Classification.post_id == post.id))
                    if kind == "classify":
                        got = {"stance": cls.stance, "message_type": cls.message_type, "topic": cls.topic_slug, "recommendation": case.decision if case.decision else cls.recommendation, "canalizar_a_atencion": cls.canalizar_a_atencion}
                        for key, value in exp.items():
                            checks[key] = got.get(key) == value
                        detail = f"{got['stance']} · {got['message_type']} · {got['topic']}"
                    else:
                        claims = case.interpretation.claims if case.interpretation else []
                        verdicts = [c.verdict for c in claims]
                        checks["verdict"] = exp["verdict"] in verdicts
                        checks["cites_fact"] = any(c.fact_ids for c in claims) == exp["cites_fact"]
                        detail = ", ".join(f"{c.verdict}{c.fact_ids}" for c in claims)
                elif kind == "copy":
                    post = capture_manual(db, client, analyst, text=case_def["text"], network="facebook", source_name=f"Eval {case_def['id']}")
                    db.flush()
                    case = db.scalar(select(Case).where(Case.post_id == post.id))
                    account = db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == client.id, OwnedAccount.format_slug == case_def["format"], OwnedAccount.account_type == "propia", OwnedAccount.registered.is_(True)))
                    if case.status == "monitoreando":
                        case.status = "interpretado"
                    if case.flow is None:
                        case.flow = "A"
                    decide(db, case, analyst, decision="responder", account_id=account.id)
                    proposal = start_generation(db, case, analyst)
                    generate_proposal(db, proposal, analyst)
                    copies = [p for p in proposal.pieces if p.kind == "copy"]
                    texts = {}
                    unsourced = 0
                    for p in copies:
                        codes = [f["code"] for f in p.validation]
                        n_uns = sum(1 for c in codes if c in ("unsourced", "mismatch", "factual_unbacked"))
                        unsourced += n_uns
                        text = " ".join(s["text"] for s in p.content.get("segments", []))
                        texts[p.style_slug] = text
                        st = per_style[p.style_slug]
                        st["pieces"] += 1
                        st["unsourced"] += n_uns
                        st[f"lint_{p.compliance.get('status', 'ok')}"] += 1
                        st["chars"] += len(text)
                    sims = [_jaccard(a, b) for i, a in enumerate(texts.values()) for b in list(texts.values())[i + 1 :]]
                    checks["zero_unsourced"] = unsourced == 0
                    checks["distinct_styles"] = len(texts) >= 2 and max(sims or [0]) < 0.6
                    detail = f"{len(copies)} variantes; similitud máx {max(sims or [0]):.2f}; cifras sin respaldo {unsourced}"
                elif kind == "directive":
                    d = Directive(client_id=client.id, code=f"EV-{case_def['id']}", version=1, status="borrador", **case_def["directive"])
                    db.add(d)
                    db.flush()
                    report = check_directive(db, d, use_ai=False)
                    got = report["hard_rules"][0]["rule_id"] if report["hard_rules"] else None
                    checks["rule_id"] = got == exp["rule_id"]
                    detail = f"{report['status']} · {got}"
            except Exception as exc:  # noqa: BLE001
                checks["error"] = False
                detail = f"error: {exc}"
                db.rollback()
            results.append({"id": case_def["id"], "kind": kind, "passed": all(checks.values()) and bool(checks), "checks": checks, "detail": detail})
            db.commit()
    elapsed = time.perf_counter() - started

    by_kind: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_kind[r["kind"]].append(r)
    passed = sum(r["passed"] for r in results)
    lines = [
        "# Reporte de evaluación",
        "",
        f"- Proveedor: **{args.provider}** · casos: {len(results)} · aprobados: **{passed}/{len(results)}** · tiempo: {elapsed:.1f} s",
        "- Generado por `make eval` (regresión con MockProvider; `EVAL_PROVIDER=anthropic` para medir calidad con el modelo real).",
        "",
        "## Resumen por tipo",
        "",
        "| Tipo | Aprobados | Qué mide |",
        "|---|---|---|",
    ]
    what = {
        "classify": "Postura, tipo de mensaje, tema y recomendación por el pipeline real de captura",
        "grounding": "Veredictos por afirmación y citas a hechos de la base",
        "copy": "Cero cifras sin fuente, cumplimiento de estilo y variantes distintas por estilo",
        "directive": "Rechazo de directrices que violan reglas duras con el id HR-xx correcto",
    }
    for kind, items in by_kind.items():
        lines.append(f"| {kind} | {sum(i['passed'] for i in items)}/{len(items)} | {what.get(kind, '')} |")
    lines += ["", "## Comparativo por estilo (casos de copy)", "", "| Estilo | Piezas | Cifras sin respaldo | Lint OK | Lint aviso | Lint bloqueo | Longitud media |", "|---|---|---|---|---|---|---|"]
    for style, st in sorted(per_style.items()):
        avg = st["chars"] / st["pieces"] if st["pieces"] else 0
        lines.append(f"| {style} | {st['pieces']} | {st['unsourced']} | {st['lint_ok']} | {st['lint_warn']} | {st['lint_block']} | {avg:.0f} |")
    lines += ["", "## Detalle", "", "| Caso | Tipo | Resultado | Detalle |", "|---|---|---|---|"]
    for r in results:
        failed = [k for k, v in r["checks"].items() if not v]
        status = "✅" if r["passed"] else f"❌ {', '.join(failed)}"
        lines.append(f"| {r['id']} | {r['kind']} | {status} | {r['detail'].replace('|', '/')} |")
    out = Path(args.out) if args.out else EVALS_DIR / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} casos aprobados → {out}")
    return 0 if passed == len(results) or args.provider != "mock" else 1


if __name__ == "__main__":
    sys.exit(main())
