"""Adversarial tests for the deterministic validators (9.1–9.5)."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import utcnow
from app.models.cases import Case
from app.models.generation import Piece, Proposal
from app.models.kb import ApprovedImage, Fact
from app.models.monitoring import OwnedAccount
from app.models.ops import RestrictionMode
from app.services.catalog import active_style
from app.validators.runner import validate_piece

CLIENT = 1


def fact(db, statement_part: str) -> Fact:
    return db.scalar(select(Fact).where(Fact.client_id == CLIENT, Fact.statement.contains(statement_part)))


def make_piece(db, *, kind="copy", content=None, style="cercano", fmt="formato_clasico", creative=None, flow="A") -> Piece:
    case = db.scalar(select(Case).where(Case.client_id == CLIENT, Case.topic_slug == "baches"))
    account = db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == CLIENT, OwnedAccount.format_slug == fmt, OwnedAccount.registered.is_(True)))
    st = active_style(db, CLIENT, style)
    proposal = Proposal(client_id=CLIENT, case_id=case.id, account_id=account.id, format_slug=fmt, flow=flow, strategy="contextualizar", status="listo")
    db.add(proposal)
    db.flush()
    piece = Piece(client_id=CLIENT, proposal_id=proposal.id, case_id=case.id, kind=kind, creative_slug=creative, format_slug=fmt, account_id=account.id, flow=flow,
                  style_id=st.id, style_slug=st.slug, style_version=st.version, strategy="contextualizar", intensity=st.intensity_min, content=content or {})
    db.add(piece)
    db.flush()
    return piece


def seg(text, typ="asercion_factual", ids=()):
    return {"text": text, "type": typ, "fact_ids": list(ids)}


def codes(piece: Piece) -> set[str]:
    return {f["code"] for f in piece.validation}


def run(db, piece):
    status = validate_piece(db, piece)
    return status, codes(piece)


# ------------------------------------------------------------------ 9.1 numeric


def test_exact_figures_pass_and_rounded_figure_blocks(db):
    h1 = fact(db, "8,320 baches")
    ok = make_piece(db, content={"segments": [seg(f"Le contamos: {h1.statement[0].lower()}{h1.statement[1:]}", ids=[h1.id])]})
    _, found = run(db, ok)
    assert not {"mismatch", "unsourced"} & found
    assert "legend_missing" in found, "D-003 requires its legend in formato_clasico / flow A"
    assert len(ok.figures) == 2 and all(f.matched for f in ok.figures)
    bad = make_piece(db, content={"segments": [seg("El Municipio Ejemplo reparó 8,300 baches entre enero y junio de 2026.", ids=[h1.id])]})
    status, found = run(db, bad)
    assert status == "block" and "mismatch" in found and bad.status == "bloqueado"


def test_number_without_source_blocks(db):
    p = make_piece(db, content={"segments": [seg("Se instalaron 500 luminarias nuevas.", typ="opinion_marcada")]})
    status, found = run(db, p)
    assert status == "block" and "unsourced" in found


def test_year_outside_cited_fact_blocks(db):
    h1 = fact(db, "8,320 baches")
    p = make_piece(db, content={"segments": [seg("En 2019 el Municipio Ejemplo reparó 8,320 baches.", ids=[h1.id])]})
    _, found = run(db, p)
    assert "mismatch" in found


def test_expired_fact_and_fact_without_document_block(db):
    expired = db.scalar(select(Fact).where(Fact.client_id == CLIENT, Fact.valid_until < utcnow()))
    p = make_piece(db, content={"segments": [seg(expired.statement, ids=[expired.id])]})
    _, found = run(db, p)
    assert "fact_expired" in found
    nodoc = db.scalar(select(Fact).where(Fact.client_id == CLIENT, Fact.document_id.is_(None)))
    p2 = make_piece(db, content={"segments": [seg(nodoc.statement, ids=[nodoc.id])]})
    status, found = run(db, p2)
    assert status == "block" and "fact_no_document" in found


def test_comparison_requires_same_period_and_base(db):
    muni, estado = fact(db, "410 millones"), fact(db, "120 millones de pesos en obra")
    good = make_piece(db, kind="creative", creative="mito_vs_realidad", fmt="formato_comparativa", style="institucional", content={
        "slots": {"mito": {"text": "x", "fact_ids": []}, "realidad": {"text": muni.statement, "fact_ids": [muni.id]}},
        "comparison": {"left": [muni.id], "right": [estado.id], "mode": "comparativa"}, "sources": [muni.code, estado.code]})
    _, found = run(db, good)
    assert "comparison_mismatch" not in found
    tinacos = fact(db, "tinacos")
    bad = make_piece(db, kind="creative", creative="mito_vs_realidad", fmt="formato_comparativa", style="institucional", content={
        "slots": {"realidad": {"text": muni.statement, "fact_ids": [muni.id]}}, "comparison": {"left": [muni.id], "right": [tinacos.id], "mode": "comparativa"}, "sources": [muni.code, tinacos.code]})
    status, found = run(db, bad)
    assert status == "block" and "comparison_mismatch" in found


def test_before_after_requires_same_base_and_period_length(db):
    now_, before = fact(db, "8,320 baches"), fact(db, "5,140 baches")
    ok = make_piece(db, kind="creative", creative="antes_despues", style="institucional", content={
        "slots": {"pie": {"text": f"{before.statement} {now_.statement}", "fact_ids": [before.id, now_.id]}},
        "comparison": {"left": [before.id], "right": [now_.id], "mode": "antes_despues"}, "sources": [before.code, now_.code]})
    _, found = run(db, ok)
    assert "comparison_mismatch" not in found and "mismatch" not in found
    reports = fact(db, "3,900 reportes")
    bad = make_piece(db, kind="creative", creative="antes_despues", style="institucional", content={
        "slots": {}, "comparison": {"left": [reports.id], "right": [now_.id], "mode": "antes_despues"}, "sources": [reports.code, now_.code]})
    _, found = run(db, bad)
    assert "comparison_mismatch" in found


# ------------------------------------------------------------------ 9.2 claims


def test_actor_assertion_without_fact_blocks(db):
    p = make_piece(db, content={"segments": [seg("El Gobierno Estatal Ejemplo recortó el presupuesto de calles.")]})
    status, found = run(db, p)
    assert status == "block" and "factual_unbacked" in found
    p2 = make_piece(db, content={"segments": [seg("El gobierno estatal nunca ha hecho nada por las calles.", typ="opinion_marcada")]})
    status, found = run(db, p2)
    assert status == "block" and "actor_attribution" in found


def test_assertion_citing_foreign_fact_blocks(db):
    other_client_fact = db.scalar(select(Fact).where(Fact.client_id == 2))
    p = make_piece(db, content={"segments": [seg("Dato.", ids=[other_client_fact.id])]})
    _, found = run(db, p)
    assert {"factual_unbacked", "fact_missing"} & found


# ------------------------------------------------------------------ 9.3 style


@pytest.mark.parametrize("word", ["MENTIROSO", "mentírosó", "m e n t i r o s o", "Mentiroso!"])
def test_prohibited_vocab_hidden_in_caps_or_accents_blocks(db, word):
    p = make_piece(db, content={"segments": [seg(f"Eso lo dijo un {word}.", typ="opinion_marcada")]})
    status, found = run(db, p)
    assert status == "block" and "prohibited_term" in found


# ------------------------------------------------------------------ 9.4 compatibility


def test_matrix_none_and_style_not_allowed_block(db):
    p = make_piece(db, kind="creative", creative="voz_ciudadana", fmt="formato_voz_pueblo", style="cercano", content={"slots": {}, "label": "ilustración representativa"})
    _, found = run(db, p)
    assert "matrix_none" in found
    p2 = make_piece(db, content={"segments": [seg("Hola.", typ="saludo")]}, style="satirico", fmt="formato_clasico")
    _, found = run(db, p2)
    assert "style_not_allowed" in found


def test_veda_blocks_format(db):
    veda = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == CLIENT))
    veda.starts_at, veda.ends_at = utcnow() - timedelta(days=1), utcnow() + timedelta(days=3)
    p = make_piece(db, content={"segments": [seg("Hola.", typ="saludo")]}, style="satirico", fmt="formato_titeres")
    _, found = run(db, p)
    assert "veda_format" in found
    assert any(f["rule_id"] == "HR-04" for f in p.validation)


# ------------------------------------------------------------------ 9.5 labels and images


def test_representative_label_required_in_voz_del_pueblo(db):
    h1 = fact(db, "8,320 baches")
    p = make_piece(db, kind="creative", creative="dato_duro", fmt="formato_voz_pueblo", style="cercano", content={
        "slots": {"cifra": {"text": "8,320 baches", "fact_ids": [h1.id]}}, "sources": [h1.code]})
    _, found = run(db, p)
    assert "representative_label" in found
    p.content = {**p.content, "label": "ILUSTRACIÓN REPRESENTATIVA · no corresponde a una persona real"}
    _, found = run(db, p)
    assert "representative_label" not in found


def test_generated_images_are_never_evidence_and_carry_metadata(db):
    p = make_piece(db, kind="creative", creative="antes_despues", style="institucional", content={
        "slots": {}, "images": [{"generated": True, "key": "x", "meta": {"generada_por_ia": True, "ilustracion": True}}]})
    _, found = run(db, p)
    assert "generated_as_evidence" in found
    p2 = make_piece(db, kind="creative", creative="infografia", fmt="formato_historieta", style="didactico", content={"slots": {}, "images": [{"generated": True, "key": "x", "meta": {}}]})
    _, found = run(db, p2)
    assert "generated_meta" in found
    illustration = db.scalar(select(ApprovedImage).where(ApprovedImage.client_id == CLIENT, ApprovedImage.image_type == "ilustracion"))
    p3 = make_piece(db, kind="creative", creative="antes_despues", style="institucional", content={"slots": {}, "images": [{"approved_image_id": illustration.id}]})
    _, found = run(db, p3)
    assert "evidence_not_real" in found


def test_creative_must_show_sources_of_cited_facts(db):
    h1 = fact(db, "8,320 baches")
    p = make_piece(db, kind="creative", creative="dato_duro", style="institucional", content={"slots": {"cifra": {"text": "8,320 baches", "fact_ids": [h1.id]}}, "sources": []})
    status, found = run(db, p)
    assert status == "block" and "sources_missing" in found


def test_voz_ciudadana_requires_consent_and_real_testimony(db):
    p = make_piece(db, kind="creative", creative="voz_ciudadana", style="institucional", content={"slots": {"cita": {"text": "", "fact_ids": []}}})
    _, found = run(db, p)
    assert {"consent_missing", "testimony_missing"} <= found
