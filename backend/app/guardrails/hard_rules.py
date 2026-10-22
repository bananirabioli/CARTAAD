"""Reglas duras HR-01…HR-11.

Viven en código y no se pueden desactivar: ningún estilo, directriz, configuración ni instrucción del copiloto
las anula. Este módulo expone:

* ``HARD_RULES``: registro con id, título y descripción (para la UI y para los prompts).
* ``check_text_against_hard_rules``: detección determinista de textos (directrices, guías de estilo,
  instrucciones del copiloto) que piden violar una regla dura.
* Funciones ``assert_*`` / ``sanitize_*`` que los servicios invocan en los puntos de control
  (ingesta, generación, aprobación, programación).

Todas operan sobre datos simples (atributos o dicts) para no depender de los modelos.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.i18n import t
from app.textnorm import find_terms, normalize


class HardRuleViolation(Exception):
    def __init__(self, rule_id: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(f"{rule_id}: {message}")
        self.rule_id = rule_id
        self.message = message
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "message": self.message, "details": self.details}


@dataclass(frozen=True)
class HardRule:
    id: str
    patterns: tuple[re.Pattern[str], ...] = field(default=())

    @property
    def title(self) -> str:
        return t(f"hard_rules.{self.id}.title")

    @property
    def description(self) -> str:
        return t(f"hard_rules.{self.id}.description")


def _p(*patterns: str) -> tuple[re.Pattern[str], ...]:
    # "~" stands for "any char that does not end a clause", so matches never span sentences.
    return tuple(re.compile(p.replace("~", "[^.;:]")) for p in patterns)


_USE = r"(us\w*|cre\w*|activ\w*|oper\w*|emple\w*|contrat\w*|compr\w*|apoy\w*|amplific\w*|impuls\w*|moviliz\w*|abr\w*|registr\w*|manej\w*|difundir|publicar|recurr\w*)"
_FAKE = r"(bots?|trolls?|(cuentas?|perfiles?) (falsas?|falsos?|ficticias?|ficticios?|anonimas?|anonimos?|alternas?|alternos?|fake|apocrifas?|espejo|satelite)|granjas? de \w+|sockpuppets?)"

# Patterns run over normalize()d text (lowercase, no accents). A match preceded by a negation
# ("no", "nunca", "evitar", "prohibido"...) is a prohibition of the behaviour, not a violation.
HARD_RULES: dict[str, HardRule] = {
    rule.id: rule
    for rule in [
        HardRule(
            "HR-01",
            _p(
                r"\b(invent\w*|fabric\w*|maquill\w*|infl(ar|en|ando|ado|e))\b~{0,40}\b(cifras?|datos?|numeros?|montos?|porcentajes?|estadisticas?)\b",
                r"\b(redonde\w*|estim\w*|aproxim\w*|supon\w*|calcul\w*)\b~{0,60}\b(cifras?|datos?|numeros?|montos?|porcentajes?)\b~{0,60}\b(sin (citar|fuente|respaldo|documento)|cuando falte|si falta|si no hay|aunque no (haya|exista))",
                r"\b(cuando falte|si falta|si no hay)\b~{0,40}\b(redonde\w*|estim\w*|aproxim\w*|supon\w*|invent\w*)\b~{0,30}\b(cifras?|datos?|numeros?|montos?)\b",
                r"\b(sin|no) (citar|mostrar|incluir|poner|mencionar|atribuir) (la |las |el |los |su |sus )?(fuentes?|fechas?)\b",
                r"\b(ocult\w*|omit\w*|quit\w*|elimin\w*|borr\w*)\b (la |las |el |los |su |sus )?(fuentes?|fechas? de (la )?fuente)\b",
            ),
        ),
        HardRule(
            "HR-02",
            _p(
                rf"\b{_USE}\b~{{0,40}}\b{_FAKE}\b",
                r"\b(publicacion(es)?|difusion) masivas? (automatizadas?|automaticas?)\b",
                r"\bautomatizar (la |las )?(publicacion\w*|difusion|respuestas?)\b",
                r"\bastroturf\w*\b",
            ),
        ),
        HardRule(
            "HR-03",
            _p(
                r"\b(perfil\w*|identific\w*|rastre\w*|guard\w*|registr\w*|expon\w*|exhib\w*|ubic\w*|dox\w*|fich\w*)\b~{0,40}\b(comentarist\w*|quien(es)? comenta\w*|(usuarios?|personas?|ciudadan[oa]s?) que (comenta|critica|opina|responde)\w*|nombres? de (los |las )?(usuarios?|comentaristas?)|handles? de)",
            ),
        ),
        HardRule(
            "HR-04",
            _p(
                r"\b(ignor\w*|salt\w*|omit\w*|desactiv\w*|evad\w*|brinc\w*|no aplicar)\b~{0,12}\b(veda|modo veda|restricciones? (electorales?|de veda))\b",
            ),
        ),
        HardRule(
            "HR-05",
            _p(
                r"\b(quejas?|reclamos?|denuncias?) (ciudadanas?|legitimas?|vecinales?)\b~{0,60}\b(como (un )?ataques?|desmentir\w*|confront\w*|minimiz\w*|no canaliz\w*|ignor\w*)",
                r"\b(desmentir|confrontar|atacar|minimizar|ignorar|exhibir)\b~{0,40}\b(quejas?|reclamos?) (ciudadan\w*|legitim\w*|vecinal\w*)",
            ),
        ),
        HardRule(
            "HR-06",
            _p(
                r"\b(imagen\w*|fotos?|fotografias?|ilustracion\w*)\b~{0,40}\b(generad\w*|creada\w* (con|por) ia|de ia|sintetic\w*)\b~{0,60}\b(evidencia|pruebas?|como (si fuera )?reales?|fotos? reales?|documentar)",
                r"\b(presentar|usar|mostrar|hacer pasar)\b~{0,30}\b(ilustracion\w*|imagen\w* generad\w*)\b~{0,30}\b(como|cual) (fotos?|evidencia|pruebas?)",
            ),
        ),
        HardRule(
            "HR-07",
            _p(
                r"\b(quit\w*|omit\w*|elimin\w*|sin|no (poner|incluir|usar|mostrar)|borr\w*)\b~{0,40}ilustracion representativa",
                r"\b(invent\w*|fabric\w*|simul\w*)\b~{0,30}\btestimoni\w*",
                r"\btestimoni\w*~{0,40}\bsin (consentimiento|autorizacion|permiso)",
                r"\b(presentar|hacer pasar)\b~{0,40}\b(figuras?|ilustracion\w*|personajes?)\b~{0,30}\b(personas?|ciudadan[oa]s?) reales?",
            ),
        ),
        HardRule(
            "HR-08",
            _p(
                r"\b(acus\w*|atribu\w*|afirm\w*|senal\w*|decir que)\b~{0,60}\bsin (respaldo|pruebas?|datos?|hechos?|evidencia|sustento|fuentes?)\b",
                r"\b(insinu\w*|sugerir)\b (que )?~{0,40}\b(corrupt\w*|robos?|roba|robaron|delitos?|fraudes?|desvio\w*)\b",
            ),
        ),
        HardRule(
            "HR-09",
            _p(
                r"\b(publicar|programar|subir|difundir)\b~{0,40}\b(sin|antes de) (la |una )?(aprobacion|revision|verificacion|autorizacion)\b",
                r"\b(salt\w*|omit\w*|brinc\w*|no (requerir|necesitar|pedir))\b~{0,30}\b(la |una )?(aprobacion|verificacion de cifras|revision humana)\b",
                r"\b(auto ?aprob\w*|aprobacion automatica|publicacion automatica|publicar automaticamente|publicar directamente)\b",
            ),
        ),
        HardRule(
            "HR-10",
            _p(
                r"\b(imit\w*|copi\w*|parodi\w*|al estilo de|a la manera de|inspirad\w* en|clon\w*)\b~{0,50}\b(personajes?|marcas?|medios?|periodicos?|noticieros?|caricaturas?|logos?|muppets?|disney|pixar|simpsons?|marvel|plaza sesamo)\b",
                r"\b(caricatur\w*|ridiculiz\w*|burl\w*)\b~{0,40}\b(rasgos fisicos|aspecto fisico|personas? reales?|funcionari[oa]s? (reales?|identificables?)|su cara|su rostro|su cuerpo)\b",
                r"\bmuppets?\b",
                r"\b(sin|omit\w*|salt\w*)\b~{0,20}\brevision (de )?legal\b",
            ),
        ),
        HardRule(
            "HR-11",
            _p(
                r"\b(gener\w*|ped\w*|cre\w*|produc\w*|dibuj\w*)\b~{0,30}\b(imagen\w*|ilustracion\w*)\b~{0,20}\b(con|que (incluya\w*|contenga\w*|muestre\w*|escriba\w*|tenga\w*)|incluyendo)\b~{0,15}\b(textos?|cifras?|numeros?|logos?|letras|rotulos?|titulares?)\b",
                r"\b(gener\w*|ped\w*|cre\w*)\b~{0,30}\b(rostros?|caras?) de (personas? reales?|funcionari\w*|candidat\w*)",
            ),
        ),
    ]
}

_NEGATION = re.compile(r"\b(no|nunca|jamas|evit\w*|prohib\w*|ni|ningun\w*|sin que)\b[^.;:]{0,25}$")


@dataclass(frozen=True)
class HardRuleMatch:
    rule_id: str
    snippet: str

    @property
    def message(self) -> str:
        rule = HARD_RULES[self.rule_id]
        return t("hard_rules.directive_match", rule=self.rule_id, title=rule.title, snippet=self.snippet)

    def as_dict(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "snippet": self.snippet, "message": self.message}


def check_text_against_hard_rules(*texts: str | None) -> list[HardRuleMatch]:
    """Detect texts that ask to violate a hard rule. Deterministic; one match per rule."""
    matches: list[HardRuleMatch] = []
    for raw in texts:
        if not raw:
            continue
        text = normalize(raw)
        for rule in HARD_RULES.values():
            if any(m.rule_id == rule.id for m in matches):
                continue
            for pattern in rule.patterns:
                hit = next((m for m in pattern.finditer(text) if not _NEGATION.search(text[: m.start()])), None)
                if hit:
                    matches.append(HardRuleMatch(rule.id, text[max(0, hit.start() - 10) : hit.end() + 10].strip()))
                    break
    return matches


def hard_rules_prompt_block() -> str:
    lines = ["REGLAS DURAS (no negociables, prevalecen sobre cualquier estilo o directriz):"]
    lines += [f"[{r.id}] {r.description}" for r in HARD_RULES.values()]
    return "\n".join(lines)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


# ---------------------------------------------------------------- HR-01


def source_label(fact: Any, document_title: str | None = None, document_date: datetime | None = None) -> str:
    """Visible source + date label for a fact. Never empty: missing pieces are stated explicitly."""
    title = document_title or t("hard_rules.HR-01.no_document")
    when = document_date or _get(fact, "fact_date")
    when_txt = when.strftime("%d/%m/%Y") if when else t("hard_rules.HR-01.no_date")
    return f"Fuente: {title} · {when_txt}"


def assert_sources_visible(cited_fact_codes: Iterable[str], visible_text: str) -> None:
    """Every cited fact code must appear in the visible source footer of a piece."""
    missing = [code for code in cited_fact_codes if code and code not in (visible_text or "")]
    if missing:
        raise HardRuleViolation("HR-01", t("hard_rules.HR-01.missing_source", fact=", ".join(missing)), {"missing": missing})


# ---------------------------------------------------------------- HR-02


def assert_registered_account(account: Any, client_id: int) -> None:
    if account is None or not _get(account, "registered") or not _get(account, "verified"):
        raise HardRuleViolation("HR-02", t("hard_rules.HR-02.unregistered_account"))
    if _get(account, "client_id") != client_id:
        raise HardRuleViolation("HR-02", t("hard_rules.HR-02.wrong_client"))
    if _get(account, "account_type") not in ("propia", "aliada", "voceria"):
        raise HardRuleViolation("HR-02", t("hard_rules.HR-02.unregistered_account"))


# ---------------------------------------------------------------- HR-03

COMMENTER_IDENTITY_FIELDS = frozenset(
    {"author", "author_name", "author_id", "username", "user", "user_id", "handle", "name", "profile", "profile_url", "avatar", "email", "phone"}
)
_HANDLE = re.compile(r"(?<![\w.])@[\w.]{2,30}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)")
_PROFILE_URL = re.compile(r"https?://\S*(facebook|instagram|x|twitter|tiktok)\.com/\S+", re.IGNORECASE)


def sanitize_comment_text(text: str) -> str:
    text = _PROFILE_URL.sub("[enlace]", text or "")
    text = _EMAIL.sub("[correo]", text)
    text = _HANDLE.sub("@usuario", text)
    return _PHONE.sub("[teléfono]", text).strip()


def strip_commenter_identity(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Drop any commenter identifier from an inbound comment payload. Returns (clean, dropped_fields)."""
    dropped = sorted(k for k in payload if k.lower() in COMMENTER_IDENTITY_FIELDS)
    clean = {k: v for k, v in payload.items() if k.lower() not in COMMENTER_IDENTITY_FIELDS}
    if "text" in clean:
        clean["text"] = sanitize_comment_text(str(clean["text"]))
    return clean, dropped


# ---------------------------------------------------------------- HR-04


def restriction_active(restriction: Any, when: datetime) -> bool:
    if restriction is None or not _get(restriction, "active"):
        return False
    start, end = _get(restriction, "starts_at"), _get(restriction, "ends_at")
    return (start is None or start <= when) and (end is None or when <= end)


def assert_not_restricted(restriction: Any, when: datetime, format_slug: str | None = None, creative_slug: str | None = None) -> None:
    if not restriction_active(restriction, when):
        return
    name = _get(restriction, "name", "")
    if format_slug and format_slug in (_get(restriction, "blocked_formats") or []):
        raise HardRuleViolation("HR-04", t("hard_rules.HR-04.format_blocked", format=format_slug, name=name), {"format": format_slug})
    if creative_slug and creative_slug in (_get(restriction, "blocked_creatives") or []):
        raise HardRuleViolation("HR-04", t("hard_rules.HR-04.creative_blocked", creative=creative_slug, name=name), {"creative": creative_slug})


def required_legends(restriction: Any, when: datetime) -> list[str]:
    return list(_get(restriction, "mandatory_legends") or []) if restriction_active(restriction, when) else []


# ---------------------------------------------------------------- HR-05

LEGIT_COMPLAINT = "queja_ciudadana_legitima"
COMPLAINT_ALLOWED_STRATEGIES = frozenset({"contextualizar", "agradecer"})


def assert_complaint_routing(message_type: str | None, canalizar: bool, strategy: str | None = None) -> None:
    if message_type != LEGIT_COMPLAINT:
        return
    if not canalizar:
        raise HardRuleViolation("HR-05", t("hard_rules.HR-05.not_routed"))
    if strategy and strategy not in COMPLAINT_ALLOWED_STRATEGIES:
        raise HardRuleViolation("HR-05", t("hard_rules.HR-05.attack_strategy", strategy=strategy), {"strategy": strategy})


# ---------------------------------------------------------------- HR-06


def assert_evidence_images(images: Iterable[Mapping[str, Any]]) -> None:
    """Images used to show real facts must be approved real photos with credit; generated images never qualify."""
    for img in images:
        label = img.get("title") or img.get("id") or "?"
        if img.get("generada_por_ia") or img.get("ilustracion") or img.get("image_type") != "foto_real":
            raise HardRuleViolation("HR-06", t("hard_rules.HR-06.generated_as_evidence", image=label), {"image": label})
        if not (img.get("credit") or "").strip():
            raise HardRuleViolation("HR-06", t("hard_rules.HR-06.missing_credit", image=label), {"image": label})


def generated_image_metadata(**extra: Any) -> dict[str, Any]:
    """Metadata every generated image must carry (HR-06 / 9.5.3)."""
    return {"generada_por_ia": True, "ilustracion": True, "no_es_evidencia": True, **extra}


# ---------------------------------------------------------------- HR-07

REPRESENTATIVE_LABEL = "ilustración representativa"


def assert_testimony_consent(consent: Any) -> None:
    if consent is None or not (_get(consent, "file_path") or _get(consent, "file_key")):
        raise HardRuleViolation("HR-07", t("hard_rules.HR-07.missing_consent"))


def assert_representative_label(visible_text: str) -> None:
    if not find_terms(visible_text, [REPRESENTATIVE_LABEL]):
        raise HardRuleViolation("HR-07", t("hard_rules.HR-07.missing_label"))


# ---------------------------------------------------------------- HR-08


def assert_claims_backed(segments: Iterable[Mapping[str, Any]], valid_fact_ids: set[int]) -> None:
    for seg in segments:
        if seg.get("type") != "asercion_factual":
            continue
        ids = {int(x) for x in seg.get("fact_ids") or []}
        if not ids or not ids <= valid_fact_ids:
            raise HardRuleViolation("HR-08", t("hard_rules.HR-08.unbacked", text=seg.get("text", "")[:120]), {"segment": seg.get("text")})


# ---------------------------------------------------------------- HR-09


@dataclass
class PieceGate:
    status: str
    current_version: int
    approved_version: int | None
    figures_total: int
    figures_verified: int
    blocking_findings: int
    legal_required: bool
    legal_status: str | None


def assert_approvable(gate: PieceGate) -> None:
    if gate.status in ("descartado", "programado", "publicado"):
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.bad_status", status=gate.status))
    if gate.blocking_findings:
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.blocked"))
    pending = gate.figures_total - gate.figures_verified
    if pending > 0:
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.figures_pending", count=pending), {"pending": pending})
    if gate.legal_required and gate.legal_status != "liberada":
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.legal_pending"))


def assert_publishable(gate: PieceGate) -> None:
    if gate.status not in ("aprobado", "programado"):
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.not_approved"))
    if gate.approved_version != gate.current_version:
        raise HardRuleViolation("HR-09", t("hard_rules.HR-09.stale_approval"))
    assert_approvable(PieceGate(**{**gate.__dict__, "status": "pendiente"}))


# ---------------------------------------------------------------- HR-10


def check_imitation(*texts: str | None) -> list[HardRuleMatch]:
    return [m for m in check_text_against_hard_rules(*texts) if m.rule_id == "HR-10"]


def assert_no_imitation(*texts: str | None) -> None:
    hits = check_imitation(*texts)
    if hits:
        raise HardRuleViolation("HR-10", t("hard_rules.HR-10.imitation", snippet=hits[0].snippet))


def requires_legal_review(style_requires_legal: bool, satirical: bool, names_actor: bool, message_type: str | None = None) -> bool:
    return bool(style_requires_legal or (satirical and names_actor) or message_type == "acusacion_o_difamacion")


# ---------------------------------------------------------------- HR-11

IMAGE_NEGATIVE_TERMS = (
    "text",
    "letters",
    "words",
    "numbers",
    "digits",
    "captions",
    "logos",
    "watermarks",
    "brand marks",
    "real person faces",
    "celebrity likeness",
    "copyrighted characters",
)
_IMAGE_FORBIDDEN = {
    "texto": re.compile(r"\b(text|texto|letras?|letters|words|palabras|titulo|title|caption|rotulo|slogan|lema)\b"),
    "cifras": re.compile(r"\b(numbers?|numeros?|cifras?|digits?|porcentajes?|percent)\b|\d"),
    "logos": re.compile(r"\b(logos?|logotipos?|brand|marca|watermark)\b"),
    "rostros reales": re.compile(r"\b(real (person|people|face)|rostro real|cara real|retrato de|portrait of|celebrity|famoso)\b"),
    "terceros": re.compile(r"\b(muppets?|disney|pixar|simpsons?|marvel|ghibli|in the style of|al estilo de)\b"),
}


def sanitize_image_prompt(prompt: str, negative_prompt: str = "") -> tuple[str, str]:
    """Reject prompts that ask for text, figures, logos, real faces or third-party works; enforce negatives."""
    norm = normalize(prompt)
    bad = [label for label, rx in _IMAGE_FORBIDDEN.items() if rx.search(norm)]
    if bad:
        raise HardRuleViolation("HR-11", t("hard_rules.HR-11.forbidden_request", items=", ".join(bad)), {"items": bad})
    negatives = [n.strip() for n in negative_prompt.split(",") if n.strip()]
    for term in IMAGE_NEGATIVE_TERMS:
        if term not in negatives:
            negatives.append(term)
    return prompt.strip(), ", ".join(negatives)
