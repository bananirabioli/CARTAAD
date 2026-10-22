"""Creative rendering: HTML/CSS templates → PNG with Playwright (Chromium headless). Pillow fallback for tests/local.

Images never carry text: titles, figures, sources and labels are overlaid here by code (HR-11).
"""

import base64
import io
import textwrap
import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import get_settings
from app.i18n import t
from app.models.cases import Case
from app.models.generation import Piece
from app.models.kb import ApprovedImage
from app.models.monitoring import Post
from app.models.styles import CreativeType, Format, Style
from app.services.catalog import get_creative, get_format
from app.storage import client_key, get_storage

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape(["html", "j2"]))
SIZE = (1080, 1350)
FRAMES = {"contexto", "historieta", "titeres", "comparativa", "voz_pueblo", "clasico"}


def _data_uri(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _read(key: str | None) -> bytes | None:
    if not key:
        return None
    storage = get_storage()
    return storage.read(key) if storage.exists(key) else None


def render_model(db: Session, piece: Piece) -> list[dict[str, Any]]:
    """One model per output image (carousels produce one per slide)."""
    fmt: Format | None = get_format(db, piece.client_id, piece.format_slug)
    creative: CreativeType | None = get_creative(db, piece.client_id, piece.creative_slug) if piece.creative_slug else None
    style = db.get(Style, piece.style_id) if piece.style_id else None
    case = db.get(Case, piece.case_id)
    post = db.get(Post, case.post_id) if case else None
    content = piece.content or {}
    slots = {k: v.get("text", "") for k, v in (content.get("slots") or {}).items()}
    options = (fmt.options if fmt else {}) or {}
    frame = fmt.template if fmt and fmt.template in FRAMES else "clasico"
    palette = (style.palette if style and style.palette else []) + ["#1F3A5F", "#E8EDF3", "#5B7A99", "#F2B134"]

    photos, hero, background = [], None, None
    for img in content.get("images") or []:
        if img.get("approved_image_id"):
            ai = db.get(ApprovedImage, img["approved_image_id"])
            data = _read(ai.file_key) if ai else None
            if data:
                caption = "Antes" if "antes" in (ai.tags or []) else "Después" if "despues" in (ai.tags or []) else ai.title
                photos.append({"src": _data_uri(data), "caption": caption, "credit": f"Foto: {ai.credit}"})
        elif img.get("generated"):
            data = _read(img.get("key"))
            if data:
                background = _data_uri(data)
    if frame == "contexto" and post and post.image_key:
        data = _read(post.image_key)
        background = _data_uri(data) if data else background
    if frame == "clasico" and photos:
        hero = photos[0]
    layout = creative.template if creative else "texto"
    points = [v for k, v in slots.items() if k.startswith(("punto_", "hito_", "dato", "historia", "mensaje", "copy_sugerido", "pie"))]
    base = {
        "width": SIZE[0], "height": SIZE[1], "palette": palette[:4], "frame": frame, "flow": piece.flow, "layout": layout, "slots": slots,
        "points": [p for p in points if p], "headline": content.get("headline") or "", "photos": photos, "hero": hero, "background": background,
        "alert_label": options.get("alert_label", "ALERTA") if piece.flow == "A" else options.get("label_flow_b", "DATO"),
        "banner_label": options.get("label_flow_a", "CONTEXTO") if piece.flow == "A" else options.get("label_flow_b", "DATO"),
        "masthead": options.get("masthead", ""), "closing": content.get("closing") or options.get("closing_phrase"),
        "representative_label": content.get("label") if options.get("illustrated_figures") else None,
        "illustration_tag": t("pieces.label_illustration") if any(i.get("generated") for i in content.get("images") or []) and frame != "voz_pueblo" else None,
        "sources": content.get("sources") or [], "legends": content.get("legends") or [], "topic_name": content.get("topic_name") or "",
        "slide": None, "slide_counter": None,
    }
    slides = content.get("slides") or []
    if layout == "carrusel" and slides:
        return [{**base, "slide": s, "slide_counter": f"{i + 1} / {len(slides)}"} for i, s in enumerate(slides)]
    return [base]


def render_html(model: dict[str, Any]) -> str:
    return _env.get_template("piece.html.j2").render(**model)


def _png_playwright(htmls: list[str]) -> list[bytes]:
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
        for html in htmls:
            page.set_content(html, wait_until="load")
            out.append(page.screenshot(type="png", clip={"x": 0, "y": 0, "width": SIZE[0], "height": SIZE[1]}))
        browser.close()
    return out


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _png_pillow(model: dict[str, Any]) -> bytes:
    """Readable fallback with the same text content (titles, body, sources, legends)."""
    w, h = SIZE
    img = Image.new("RGB", (w, h), "#f4f4f2")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 110], fill=model["palette"][0])
    d.text((60, 36), f"{model['frame'].upper()} · {model['banner_label'] if model['frame'] == 'contexto' else model['layout']}", fill="white", font=_font(36))
    y = 150
    texts = [model["slide"]["title"], model["slide"]["text"]] if model.get("slide") else [*model["slots"].values()]
    for txt in texts:
        for line in textwrap.wrap(str(txt), 44)[:8]:
            d.text((60, y), line, fill="#161616", font=_font(34))
            y += 46
        y += 18
    fy = h - 40 - 30 * (len(model["sources"]) + len(model["legends"]))
    d.rectangle([0, fy - 20, w, h], fill="white")
    for line in [*model["sources"], *model["legends"]]:
        d.text((60, fy), line[:95], fill="#333", font=_font(22))
        fy += 30
    if model.get("representative_label"):
        d.rectangle([0, 110, w, 160], fill="#161616")
        d.text((60, 120), model["representative_label"], fill="white", font=_font(26))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_piece(db: Session, piece: Piece) -> list[str]:
    creative = get_creative(db, piece.client_id, piece.creative_slug) if piece.creative_slug else None
    if piece.kind != "creative" or (creative and creative.text_only):
        piece.render_status, piece.renders = "no_aplica", []
        return []
    models = render_model(db, piece)
    try:
        if get_settings().renderer == "playwright":
            pngs = _png_playwright([render_html(m) for m in models])
        else:
            pngs = [_png_pillow(m) for m in models]
    except Exception as exc:  # noqa: BLE001 - keep the piece usable and report the error
        piece.render_status, piece.render_error = "error", str(exc)[:500]
        return []
    storage = get_storage()
    batch = uuid.uuid4().hex[:8]
    keys = [storage.save(client_key(piece.client_id, "renders", f"{piece.id}-v{piece.current_version}-{batch}-{i + 1}.png"), png, "image/png") for i, png in enumerate(pngs)]
    piece.renders, piece.render_status, piece.render_error = keys, "listo", ""
    return keys
