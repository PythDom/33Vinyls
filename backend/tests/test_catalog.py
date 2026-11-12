from vinyls import demo_data


def test_text_search(admin):
    r = admin.get("/api/search", params={"q": "velvet static neon harbour"})
    assert r.status_code == 200
    titles = {c["title"] for c in r.json()["candidates"]}
    assert titles == {"Neon Harbour"}
    assert len(r.json()["candidates"]) == 6


def test_barcode_lookup(admin):
    code = demo_data.ean13("505419701234")
    r = admin.get("/api/identify/barcode", params={"code": code}).json()
    assert r["valid"] is True
    assert [c["id"] for c in r["candidates"]] == [100105]


def test_release_detail_and_thumb(admin):
    r = admin.get("/api/releases/100101").json()
    assert r["artist"] == "The Velvet Static"
    assert r["matrix"] == ["HL-2001-A1", "HL-2001-B1"]
    assert r["labels"][0]["catno"] == "HL 2001"
    t = admin.get("/api/thumbs/100101")
    assert t.status_code == 200 and t.headers["content-type"] == "image/jpeg" and len(t.content) > 1000


def test_price_card_and_deal(admin):
    card = admin.get("/api/releases/100101/price").json()
    assert card["currency"] == "EUR"
    assert card["suggested"]["NM"] == 240.0
    assert card["suggested"]["VG+"] == 180.0
    assert admin.post("/api/releases/100101/deal", json={"asking": 100, "media": "VG+"}).json()["verdict"] == "green"
    assert admin.post("/api/releases/100101/deal", json={"asking": 190, "media": "VG+"}).json()["verdict"] == "amber"
    assert admin.post("/api/releases/100101/deal", json={"asking": 400, "media": "NM"}).json()["verdict"] == "red"
    worse_sleeve = admin.post("/api/releases/100101/deal", json={"asking": 100, "media": "VG+", "sleeve": "G"}).json()
    assert worse_sleeve["estimate"] < 180.0


def test_pressing_by_runout(admin):
    r = admin.post("/api/pressing/match", json={"master_id": 9001, "matrix": "HL 2001 A2"}).json()
    assert r["candidates"][0]["id"] == 100102
    assert any("runout" in m for m in r["candidates"][0]["matched"])


def test_pressing_questions_narrow_down(admin):
    r = admin.post("/api/pressing/match", json={"master_id": 9001}).json()
    assert r["total"] == 6
    q = r["question"]
    assert q and len(q["options"]) >= 2
    answers = {}
    for _ in range(6):
        if not r["question"]:
            break
        attr = r["question"]["attribute"]
        # answer as the 1973 German pressing would
        target = {"country": "Germany", "year": "1973", "label": "Harbourline", "catno": "6305 117", "format": "Vinyl, LP, Album"}
        answers[attr] = target[attr]
        r = admin.post("/api/pressing/match", json={"master_id": 9001, "answers": answers}).json()
    assert [c["id"] for c in r["candidates"]] == [100103]


def test_pressing_by_catno(admin):
    r = admin.post("/api/pressing/match", json={"master_id": 9001, "catno": "cr4410"}).json()
    assert r["candidates"][0]["id"] == 100104


def test_versions(admin):
    r = admin.get("/api/masters/9002/versions").json()
    assert {v["country"] for v in r["versions"]} == {"France", "UK", "Japan", "Europe"}


def test_pressing_skip_moves_to_next_question(admin):
    first = admin.post("/api/pressing/match", json={"master_id": 9001}).json()["question"]["attribute"]
    nxt = admin.post("/api/pressing/match", json={"master_id": 9001, "skip": [first]}).json()["question"]
    assert nxt is None or nxt["attribute"] != first
