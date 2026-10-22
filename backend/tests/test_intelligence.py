from tests.conftest import login


def test_seeded_coordinated_narrative_is_grouped_by_page(client):
    login(client)
    groups = client.get("/intelligence/narratives", params={"days": 30}).json()
    coordinated = [g for g in groups if g["level"] == "coordinado"]
    assert len(coordinated) == 1
    g = coordinated[0]
    assert g["topic"] == "baches" and g["sources"] >= 3 and g["posts"] == len(g["items"])
    assert len({i["source"] for i in g["items"]}) == g["sources"], "one row per page, never per person"
    assert all(i["case_code"] for i in g["items"])


def test_narratives_are_isolated_per_client(client):
    login(client, client_slug="candidatura-ejemplo")
    texts = " ".join(g["representative"] for g in client.get("/intelligence/narratives", params={"days": 30}).json())
    assert "bache" not in texts.lower()


def test_weekly_report_exports_markdown_and_html(client):
    login(client)
    report = client.get("/intelligence/weekly-report").json()
    assert report["summary"]["cases"] > 0 and report["narratives"] and report["topics"]
    md = client.get("/intelligence/weekly-report.md")
    assert md.status_code == 200 and md.headers["content-disposition"].startswith("attachment")
    assert md.text.startswith("# Reporte semanal") and "no prueba de coordinación" in md.text and "D-009" in md.text
    html = client.get("/intelligence/weekly-report.html", params={"download": True})
    assert html.status_code == 200 and "<table>" in html.text and "attachment" in html.headers["content-disposition"]
    assert "<script" not in html.text


def test_weekly_report_tag_filter_and_past_week(client):
    login(client)
    filtered = client.get("/intelligence/weekly-report", params={"tag": "estilo:no-existe"}).json()
    assert filtered["responses"]["pieces"] == 0 and filtered["tag"] == "estilo:no-existe"
    old = client.get("/intelligence/weekly-report", params={"start": "2020-01-06"}).json()
    assert old["summary"]["cases"] == 0 and old["start"].startswith("2020-01-06")
    assert "Sin registros esta semana." in client.get("/intelligence/weekly-report.md", params={"start": "2020-01-06"}).text
