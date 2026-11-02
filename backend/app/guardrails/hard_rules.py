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


# ---------------------------------------------------------------- per-client configuration
#
# Every rule's wording can be edited per client (ClientSettings.rules[<id>].text). Creative and workflow parts can be
# switched off per client through the SWITCHES below. The integrity core (LOCKED_RULES) cannot be switched off: invented
# figures, fake accounts, profiling commenters, AI images as evidence, invented testimonies, unbacked accusations,
# impersonating media/brands and real faces stay enforced in code whatever the configuration says.

LOCKED_RULES = frozenset({"HR-01", "HR-02", "HR-03", "HR-06", "HR-07", "HR-08", "HR-10", "HR-11"})

SWITCHES: dict[str, dict[str, str]] = {
    "HR-04": {"parent": "HR-04", "title": "Modo veda", "help": "Bloqueos de formatos y leyendas obligatorias mientras haya una restricción activa."},
    "HR-05": {"parent": "HR-05", "title": "Canalizar quejas legítimas", "help": "Forzar canalización a atención y solo estrategias informativas ante quejas ciudadanas."},
    "HR-07L": {"parent": "HR-07", "title": "Etiqueta «ilustración representativa»", "help": "Exigir la etiqueta en piezas con figuras ilustradas."},
    "HR-09V": {"parent": "HR-09", "title": "Verificación de cifras y legal antes de aprobar", "help": "Cada cifra verificada por una persona y liberación legal antes de aprobar. La aprobación humana sigue siendo obligatoria."},
    "HR-10S": {"parent": "HR-10", "title": "Sátira con revisión legal", "help": "Sátira y caricatura pasan por legal; no se burla de rasgos físicos."},
    "HR-11T": {"parent": "HR-11", "title": "Imágenes sin texto", "help": "Apágala para que el modelo de imagen dibuje titulares y rótulos."},
    "HR-11N": {"parent": "HR-11", "title": "Imágenes sin cifras", "help": "Apágala para permitir números dentro de la imagen (las cifras deben venir de hechos)."},
    "HR-11L": {"parent": "HR-11", "title": "Imágenes sin logos", "help": "Apágala para permitir el logo o marca propia del cliente."},
}

# (rule id, pattern index) -> switch that disables that pattern. Patterns not listed are always on.
_PATTERN_SWITCH: dict[tuple[str, int], str] = {
    ("HR-04", 0): "HR-04",
    ("HR-05", 0): "HR-05",
    ("HR-05", 1): "HR-05",
    ("HR-07", 0): "HR-07L",
    ("HR-10", 1): "HR-10S",
    ("HR-10", 3): "HR-10S",
}


def rule_enabled(rules: Mapping[str, Any] | None, rule_id: str) -> bool:
    """Locked rules are always on; a switch is on unless the client turned it off."""
    if rule_id in LOCKED_RULES or not rules:
        return True
    cfg = rules.get(rule_id)
    if cfg is None:
        return True
    return bool(_get(cfg, "enabled", True))


def rule_text(rules: Mapping[str, Any] | None, rule_id: str) -> str | None:
    cfg = (rules or {}).get(rule_id)
    text = _get(cfg, "text") if cfg is not None else None
    return text.strip() if isinstance(text, str) and text.strip() else None


def _hr11_switch_for(snippet: str) -> str:
    if re.search(r"\blogo", snippet):
        return "HR-11L"
    if re.search(r"\b(cifras?|numeros?)\b", snippet):
        return "HR-11N"
    return "HR-11T"


def check_text_against_hard_rules(*texts: str | None, rules: Mapping[str, Any] | None = None) -> list[HardRuleMatch]:
    """Detect texts that ask to violate a hard rule. Deterministic; one match per rule. Switched-off parts are skipped."""
    matches: list[HardRuleMatch] = []
    for raw in texts:
        if not raw:
            continue
        text = normalize(raw)
        for rule in HARD_RULES.values():
            if any(m.rule_id == rule.id for m in matches):
                continue
            for idx, pattern in enumerate(rule.patterns):
                switch = _PATTERN_SWITCH.get((rule.id, idx))
                if switch and not rule_enabled(rules, switch):
                    continue
                hit = next((m for m in pattern.finditer(text) if not _NEGATION.search(text[: m.start()])), None)
                if hit and rule.id == "HR-11" and idx == 0 and not rule_enabled(rules, _hr11_switch_for(hit.group(0))):
                    hit = None
                if hit:
                    matches.append(HardRuleMatch(rule.id, text[max(0, hit.start() - 10) : hit.end() + 10].strip()))
                    break
    return matches


def _default_description(rule_id: str, rules: Mapping[str, Any] | None) -> str:
    """Rule wording adjusted to the client's switches (so the prompt never says something the code no longer enforces)."""
    on = lambda sw: rule_enabled(rules, sw)  # noqa: E731
    if rule_id == "HR-07" and not on("HR-07L"):
        return "Los testimonios de «Voz ciudadana» son reales y con consentimiento adjunto. Nunca se inventan testimonios."
    if rule_id == "HR-09" and not on("HR-09V"):
        return "Ninguna pieza se publica ni se programa sin aprobación humana."
    if rule_id == "HR-10" and not on("HR-10S"):
        return "Estilos y formatos no imitan ni suplantan personajes, marcas ni medios. La sátira apunta a roles, ideas o instituciones."
    if rule_id == "HR-11":
        banned = [label for sw, label in (("HR-11T", "texto"), ("HR-11N", "cifras"), ("HR-11L", "logos")) if on(sw)]
        allowed = [label for sw, label in (("HR-11T", "texto (titulares cortos, bien escritos, en español)"), ("HR-11N", "cifras que vengan de los hechos citados"), ("HR-11L", "solo el logo propio del cliente")) if not on(sw)]
        base = "Los modelos de imagen y video no producen rostros de personas reales identificables ni personajes o marcas de terceros"
        base += f", ni {', '.join(banned)}" if banned else ""
        base += "." + (f" Sí pueden incluir: {'; '.join(allowed)}." if allowed else "")
        return base
    return HARD_RULES[rule_id].description


def effective_rules(rules: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """What the Laboratorio shows and what the prompt receives: one row per rule with its active wording."""
    out = []
    for rule in HARD_RULES.values():
        switches = [{"id": sw, **meta, "enabled": rule_enabled(rules, sw)} for sw, meta in SWITCHES.items() if meta["parent"] == rule.id]
        whole_off = rule.id in ("HR-04", "HR-05") and not rule_enabled(rules, rule.id)
        custom = rule_text(rules, rule.id)
        out.append({
            "id": rule.id, "title": rule.title, "locked": rule.id in LOCKED_RULES, "default_text": _default_description(rule.id, rules),
            "text": custom or _default_description(rule.id, rules), "custom": custom is not None, "active": not whole_off,
            "switches": [s for s in switches if s["id"] != rule.id], "can_disable": rule.id in ("HR-04", "HR-05"),
        })
    return out


def hard_rules_prompt_block(rules: Mapping[str, Any] | None = None) -> str:
    lines = ["REGLAS DURAS (no negociables, prevalecen sobre cualquier estilo o directriz):"]
    lines += [f"[{r['id']}] {r['text']}" for r in effective_rules(rules) if r["active"]]
    return "\n".join(lines)


def validate_rules_patch(rules: Mapping[str, Any]) -> None:
    """Locked rules cannot be switched off, and no rule wording may ask to break a locked rule."""
    for rule_id, cfg in rules.items():
        if rule_id not in HARD_RULES and rule_id not in SWITCHES:
            raise HardRuleViolation(rule_id, f"regla desconocida: {rule_id}")
        if rule_id in LOCKED_RULES and not bool(_get(cfg, "enabled", True)):
            raise HardRuleViolation(rule_id, f"{rule_id} es parte del núcleo de integridad y no se puede apagar; puedes editar su redacción.")
        text = _get(cfg, "text")
        if isinstance(text, str) and text.strip():
            locked_hits = [m for m in check_text_against_hard_rules(text, rules=rules) if m.rule_id in LOCKED_RULES]
            if locked_hits:
                raise HardRuleViolation(locked_hits[0].rule_id, f"La redacción pide saltarse {locked_hits[0].rule_id} ({locked_hits[0].snippet}).")


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


_IMAGE_SWITCH = {"texto": "HR-11T", "cifras": "HR-11N", "logos": "HR-11L"}
_NEGATIVE_SWITCH = {"text": "HR-11T", "letters": "HR-11T", "words": "HR-11T", "captions": "HR-11T", "numbers": "HR-11N", "digits": "HR-11N",
                    "logos": "HR-11L", "brand marks": "HR-11L"}


def image_text_allowed(rules: Mapping[str, Any] | None) -> bool:
    return not rule_enabled(rules, "HR-11T")


def sanitize_image_prompt(prompt: str, negative_prompt: str = "", rules: Mapping[str, Any] | None = None) -> tuple[str, str]:
    """Reject prompts that ask for text, figures, logos, real faces or third-party works; enforce negatives.
    Text, figures and logos are allowed when the client switched HR-11T/N/L off; real faces and third parties never."""
    norm = normalize(prompt)
    bad = [label for label, rx in _IMAGE_FORBIDDEN.items() if rule_enabled(rules, _IMAGE_SWITCH.get(label, "HR-11")) and rx.search(norm)]
    if bad:
        raise HardRuleViolation("HR-11", t("hard_rules.HR-11.forbidden_request", items=", ".join(bad)), {"items": bad})
    allowed_terms = {term for term, sw in _NEGATIVE_SWITCH.items() if not rule_enabled(rules, sw)}
    negatives = [n.strip() for n in negative_prompt.split(",") if n.strip() and n.strip().lower() not in allowed_terms]
    for term in IMAGE_NEGATIVE_TERMS:
        if term not in negatives and term not in allowed_terms:
            negatives.append(term)
    return prompt.strip(), ", ".join(negatives)
