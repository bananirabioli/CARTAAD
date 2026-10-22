"""generate_creatives (mock): fills the slots of each candidate creative with facts from context and style phrases."""

from typing import Any

from app.ai.mock.compose import _fmt, _pick, fact_sentence, FLOW_DEFAULT_STRATEGY
from app.ai.mock.fixtures import fixture_for_style


def _fmt_value(f: dict[str, Any]) -> str:
    v = f.get("value")
    if v is None:
        return ""
    unit = f.get("unit") or ""
    if unit == "pesos" and v >= 1_000_000:
        n = v / 1_000_000
        txt = f"{n:,.0f}" if n == int(n) else f"{n:,.1f}"
        return f"{txt} millones de pesos"
    num = f"{v:,.0f}" if v == int(v) else f"{v:,.1f}".rstrip("0").rstrip(".")
    return f"{num}%" if unit == "%" else f"{num} {unit}".strip()


def _numeric(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in facts if f.get("value") is not None]


def _slot(name: str, text: str, fact_ids: list[int] | None = None) -> dict[str, Any]:
    return {"name": name, "text": text, "fact_ids": fact_ids or []}


def _creative(c: dict[str, Any], ctx: dict[str, Any], fx: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    slug, flow = c["slug"], ctx.get("flow", "A")
    strategy = ctx.get("strategy") or FLOW_DEFAULT_STRATEGY.get(flow, "contextualizar")
    level = max(0, int(ctx.get("intensity") or 1) - 1)
    headline = _fmt((fx.get("headline") or {}).get(flow, "{topic}"), ctx)
    opener = _fmt(_pick((fx.get("openers") or {}).get(strategy), level), ctx)
    closer = _fmt((fx.get("closers") or {}).get(flow, ""), ctx)
    question = _fmt(fx.get("question") or "", ctx)
    nums = _numeric(facts)
    claims = ctx.get("claims") or []
    images = ctx.get("images") or []
    out: dict[str, Any] = {"creative_slug": slug, "why": "", "adaptation": None, "slots": [], "slides": [], "image_ids": [], "missing_inputs": []}
    needs_fact = c.get("requires_fact")
    if needs_fact and not nums:
        out["missing_inputs"].append("Dato duro con fuente sobre el tema (pedir al dueño de la base).")
    if c.get("level") == "partial":
        out["adaptation"] = c.get("note") or "Adaptado al formato."

    def fs(f: dict[str, Any], i: int = 0) -> str:
        return fact_sentence(fx, f, i, ctx)

    t = c.get("template")
    if t == "responsabilidad":
        shares = [f for f in nums if f.get("unit") == "%" and "inversion" in (f.get("base") or "").lower().replace("ó", "o")] or nums[:3]
        out["slots"] = [_slot("titulo", headline), _slot("cuerpo", opener)] + [_slot(f"punto_{i + 1}", f["statement"], [f["id"]]) for i, f in enumerate(shares[:3])]
        out["why"] = "Explica quién se encarga de qué y cuánto invierte cada nivel de gobierno."
    elif t == "infografia":
        out["slots"] = [_slot("titulo", headline)] + [_slot(f"punto_{i + 1}", f["statement"], [f["id"]]) for i, f in enumerate((nums or facts)[:3])]
        out["why"] = "Resume el punto de vista con íconos y tres datos verificables."
    elif t == "pregunta":
        out["slots"] = [_slot("titulo", headline), _slot("pregunta", question or opener)]
        out["why"] = "Una pregunta directa invita a revisar la fuente sin repetir el ataque."
    elif t == "mito_realidad":
        myth = next((cl["text"] for cl in claims if cl.get("verdict") in ("falsa", "incompleta")), None)
        fact = next((f for f in nums), None)
        if myth and fact:
            out["slots"] = [_slot("mito", myth), _slot("realidad", fs(fact), [fact["id"]])]
            out["why"] = "Contrasta la afirmación difundida con el dato verificado."
        else:
            out["missing_inputs"].append("Una afirmación falsa o incompleta y su dato verificado.")
            out["slots"] = [_slot("mito", ""), _slot("realidad", "")]
    elif t == "dato_duro":
        fact = nums[0] if nums else None
        if fact:
            out["slots"] = [_slot("cifra", _fmt_value(fact), [fact["id"]]), _slot("descripcion", fact["statement"], [fact["id"]])]
            out["why"] = "Una sola cifra grande con su fuente es lo más difícil de rebatir."
    elif t == "antes_despues":
        before = next((i for i in images if "antes" in i.get("tags", [])), None)
        after = next((i for i in images if "despues" in i.get("tags", [])), None)
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for f in nums:
            groups.setdefault((f.get("unit") or "", (f.get("base") or "").lower()), []).append(f)
        # before/after: same unit and base, different periods (the validator checks equal period length)
        pair = next((sorted(g, key=lambda f: f.get("period_label") or "")[:2] for g in groups.values() if len({f.get("period_label") for f in g}) >= 2), [])
        if before and after:
            out["image_ids"] = [before["id"], after["id"]]
            out["slots"] = [_slot("titulo", headline)]
            if len(pair) == 2:
                ordered = sorted(pair, key=lambda f: f.get("period_label") or "")
                out["slots"].append(_slot("pie", f"{ordered[0]['statement']} {ordered[1]['statement']}", [ordered[0]["id"], ordered[1]["id"]]))
                out["comparison"] = {"left": [ordered[0]["id"]], "right": [ordered[1]["id"]], "mode": "antes_despues"}
            out["why"] = "Muestra con fotos reales de archivo lo que cambió."
        else:
            out["missing_inputs"].append("Par de fotos reales «antes» y «después» con crédito en el banco de imágenes.")
    elif t == "linea_tiempo":
        hits = sorted(nums, key=lambda f: f.get("period_label") or "")[:4]
        out["slots"] = [_slot("titulo", headline)] + [_slot(f"hito_{i + 1}", f["statement"], [f["id"]]) for i, f in enumerate(hits)]
        out["why"] = "Ordena en el tiempo lo que se ha hecho sobre el tema."
    elif t == "carrusel":
        slides = [{"title": headline, "text": opener, "fact_ids": []}]
        slides += [{"title": f"Dato {i + 1}".replace(str(i + 1), ["uno", "dos", "tres", "cuatro", "cinco"][i]), "text": fs(f, i), "fact_ids": [f["id"]]} for i, f in enumerate(nums[:4])]
        if ctx.get("key_messages"):
            slides.append({"title": "En resumen", "text": ctx["key_messages"][0], "fact_ids": []})
        slides.append({"title": "Para cerrar", "text": closer or opener, "fact_ids": []})
        while len(slides) < 5:
            slides.insert(-1, {"title": "Contexto", "text": _fmt(fx.get("no_fact", ""), ctx), "fact_ids": []})
        out["slides"] = slides[:7]
        out["why"] = "Desarma la narrativa paso a paso, una idea por lámina."
    elif t == "guion":
        body = " ".join(fs(f, i) for i, f in enumerate(nums[:2])) or _fmt(fx.get("no_fact", ""), ctx)
        out["slides"] = [
            {"title": "Apertura", "text": opener, "fact_ids": []},
            {"title": "Desarrollo", "text": body, "fact_ids": [f["id"] for f in nums[:2]]},
            {"title": "Cierre", "text": closer or headline, "fact_ids": []},
        ]
        out["why"] = "Guion breve para que una vocería lo grabe en treinta segundos." if slug == "guion_video" else "Reacción en video a la publicación original."
    elif t == "testimonio":
        out["slots"] = [_slot("cita", ""), _slot("persona", "")]
        out["missing_inputs"].append("Testimonio real de una persona beneficiaria, con consentimiento adjunto (HR-07). Nunca se inventa.")
        out["why"] = "Un testimonio real con consentimiento da voz a quien recibió el servicio."
    elif t == "repost":
        fact = nums[0] if nums else None
        out["slots"] = [_slot("comentario", opener)] + ([_slot("dato", fs(fact), [fact["id"]])] if fact else [])
        out["why"] = "Comparte la publicación favorable y le suma un dato verificable."
    elif t == "agradecimiento":
        out["slots"] = [_slot("mensaje", f"{opener} {closer}".strip())]
        out["why"] = "Reconoce a quien publicó sin apropiarse del mérito ciudadano."
    elif t == "historia":
        fact = nums[0] if nums else None
        out["slots"] = [_slot("titulo", headline), _slot("historia", opener)] + ([_slot("dato", fs(fact), [fact["id"]])] if fact else [])
        out["why"] = "Cuenta la historia detrás de la acción que se elogia."
    elif t == "aliados":
        fact = nums[0] if nums else None
        suggested = f"{opener} {fs(fact) if fact else ''}".strip()
        out["slots"] = [_slot("titulo", headline), _slot("mensaje", opener), _slot("copy_sugerido", suggested, [fact["id"]] if fact else [])]
        out["why"] = "Versión lista para que vocerías y aliados la compartan desde sus cuentas registradas."
    return out


def generate_creatives(ctx: dict[str, Any]) -> dict[str, Any]:
    style = ctx.get("style") or {}
    _, fx = fixture_for_style(style.get("slug", "institucional"), style.get("tags"))
    facts = ctx.get("facts") or []
    return {"creatives": [_creative(c, ctx, fx, facts) for c in ctx.get("creatives", [])]}
