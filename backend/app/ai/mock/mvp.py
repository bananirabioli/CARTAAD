"""Mock outputs for the MVP steps (analyze_capture, generate_content): deterministic, built from the context."""

from typing import Any

from app.ai.mock.classify import classify


def analyze_capture(ctx: dict[str, Any]) -> dict[str, Any]:
    text = (ctx.get("user_text") or "").strip() or "Publicación leída de la captura."
    base = classify({"post": {"text": text, "image_text": ""}, "topics": ctx.get("topics", []), "alert": {"level": "bajo"}, "comments_sample": []})
    facts = ctx.get("facts") or []
    claims = [{"text": text[:140], "verdict": "no_verificable" if not facts else "incompleta", "fact_ids": [facts[0]["id"]] if facts else [],
               "explanation": "Revisión simulada.", "missing_data": None if facts else "Dato oficial sobre el tema"}] if base["message_type"] != "opinion" else []
    strategy = "amplificar" if base["stance"] == "a_favor" else ("desmentir" if base["message_type"] == "dato_falso" and facts else "contextualizar")
    return {
        "extracted_text": text, "network_guess": "otra", "visual_context": "Captura simulada.", "author_type": "desconocido",
        "stance": base["stance"], "stance_confidence": base["confidence"], "topic": base["topic"], "message_type": base["message_type"], "tone": [],
        "summary": f"La publicación dice: {text[:120]}", "narrative": "Narrativa simulada.", "claims": claims, "audience_reaction": [], "risk_notes": "",
        "recommendation": base["recommendation"], "explanation": base["explanation"], "strategy": strategy, "strategy_justification": "Estrategia simulada.",
        "alternatives": [], "canalizar_a_atencion": base["canalizar_a_atencion"], "detected_names": [],
    }


def generate_content(ctx: dict[str, Any]) -> dict[str, Any]:
    facts = ctx.get("facts") or []
    copies = []
    for style in ctx.get("styles", []):
        segs = [{"text": f"Te contamos lo que sabemos sobre {ctx.get('topic_name', 'el tema')}.", "type": "opinion_marcada", "fact_ids": []}]
        if facts:
            segs.append({"text": facts[0]["statement"], "type": "asercion_factual", "fact_ids": [facts[0]["id"]]})
        segs.append({"text": "Síguenos para más información.", "type": "llamado", "fact_ids": []})
        copies.append({"style": style["slug"], "segments": segs, "hashtags": [], "cta": "Comparte", "why": f"Variante {style['name']} simulada."})
    images = [{"concept": "Escena de barrio al atardecer", "prompt": "Warm documentary style scene of a neighborhood street at sunset, families walking, soft light",
               "negative_prompt": "", "aspect_ratio": "4:5", "headline": "Lo que sí está pasando"} for _ in range(ctx.get("max_images", 1))]
    video = None
    if ctx.get("want_video"):
        video = {"concept": "Recorrido por la colonia", "scenes": [{"seconds": 6, "visual": "Calle al atardecer", "voiceover": "Esto es lo que sí está pasando."}],
                 "prompt": "Slow dolly-in along a quiet neighborhood street at golden hour, people walking, cinematic", "aspect_ratio": "9:16",
                 "voiceover_full": "Esto es lo que sí está pasando.", "on_screen_text": ["Lo que sí está pasando"]}
    return {"copies": copies, "image_prompts": images, "video": video, "missing_data": [] if facts else ["Dato oficial sobre el tema"]}
