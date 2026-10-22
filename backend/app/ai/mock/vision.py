"""ocr_vision (mock): cannot read pixels offline, so it returns the text typed by the person and a neutral description."""

import re
from typing import Any

_HANDLE = re.compile(r"@[\w.]{2,30}")


def ocr_vision(ctx: dict[str, Any]) -> dict[str, Any]:
    text = (ctx.get("user_text") or "").strip()
    network = ctx.get("network") or "una red social"
    return {
        "extracted_text": text,
        "visual_context": f"Captura de pantalla de una publicación en {network} (descripción generada en modo mock: sin lectura real de la imagen).",
        "detected_names": sorted(set(_HANDLE.findall(text))),
    }
