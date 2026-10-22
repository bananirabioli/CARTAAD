"""red_team (mock): likely rebuttals and weak points per piece. Informative only; never a validator."""

from typing import Any

from app.textnorm import normalize
from app.validators.numbers import extract_figures

STRONG = ("falso", "corrige", "correccion", "incorrecto", "contradice", "nunca", "siempre", "todos", "nadie")


def red_team(ctx: dict[str, Any]) -> dict[str, Any]:
    facts = {f["id"]: f for f in ctx.get("facts") or []}
    notes = []
    for piece in ctx.get("pieces") or []:
        text = piece.get("text", "")
        norm = normalize(text)
        pid = piece["id"]
        figures = [f for f in extract_figures(text) if f.kind in ("number", "percent", "money")]
        for fig in figures[:2]:
            notes.append({"piece_id": pid, "kind": "punto_debil", "severity": "media", "text": f"La cifra «{fig.raw}» puede cuestionarse por el periodo o la base; tener a mano el documento citado.", "target": fig.raw})
        for fid in piece.get("fact_ids") or []:
            f = facts.get(fid)
            if f and f.get("expired"):
                notes.append({"piece_id": pid, "kind": "punto_debil", "severity": "alta", "text": f"Se apoya en {f['code']}, que está vencido: el adversario puede decir que el dato es viejo.", "target": f["code"]})
        hits = [w for w in STRONG if f" {w}" in f" {norm}"]
        if hits:
            notes.append({"piece_id": pid, "kind": "punto_debil", "severity": "media", "text": f"Palabras absolutas o tajantes («{hits[0]}») se pueden sacar de contexto; verificar que el veredicto lo respalde.", "target": hits[0]})
        if "responsabilidad compartida" in norm or "nivel de gobierno" in norm or "estatal" in norm:
            notes.append({"piece_id": pid, "kind": "replica", "severity": "media", "text": "Réplica probable: «siempre culpan a otro nivel de gobierno». Reforzar con lo que sí hizo el municipio.", "target": "responsabilidad compartida"})
        if piece.get("satirical"):
            notes.append({"piece_id": pid, "kind": "replica", "severity": "alta", "text": "Réplica probable: «se burlan del problema». Cuidar que la ironía apunte a hechos, no a personas.", "target": "tono satírico"})
        if not figures and piece.get("kind") == "copy":
            notes.append({"piece_id": pid, "kind": "replica", "severity": "baja", "text": "Réplica probable: «puras palabras, ¿dónde están los datos?».", "target": ""})
        if ctx.get("post_text") and any(w in normalize(ctx["post_text"]) for w in ("corrup", "roban", "fraude")):
            notes.append({"piece_id": pid, "kind": "replica", "severity": "alta", "text": "Réplica probable: «no niegan la acusación». No repetir la acusación; responder solo con hechos.", "target": ""})
    return {"notes": [{"kind": n["kind"], "severity": n["severity"], "text": n["text"], "target": f"{n['piece_id']}::{n['target']}"} for n in notes]}
