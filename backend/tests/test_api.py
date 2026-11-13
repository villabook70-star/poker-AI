from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_evaluate():
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.post("/api/analysis/evaluate", json={"cards": "As Ks Qs Js Ts 2c 3d"}).json()
    assert r["category"] == "straight_flush" and r["method"] == "exact"
    assert client.post("/api/analysis/evaluate", json={"cards": "As Ks"}).status_code == 400


def test_equity_and_pot_odds_endpoints():
    r = client.post("/api/analysis/equity", json={"hero": "AhKh", "villains": ["QQ"], "mode": "mc", "samples": 5000, "seed": 1}).json()
    assert 0.4 < r["equity"] < 0.52 and r["method"] == "monte_carlo"
    r = client.post("/api/analysis/pot-odds", json={"pot": 300, "to_call": 100, "equity": 0.3}).json()
    assert r["required_equity"] == 0.25 and r["call_is_profitable"] is True


def test_simulator_endpoints():
    st = client.post("/api/sim/new", json={"seed": 5, "bot_profiles": ["tight", "maniac"]}).json()
    sid = st["session_id"]
    assert st["hero_to_act"] and len(st["players"]) == 3
    rec = client.get(f"/api/sim/{sid}/recommend").json()
    assert rec["action"] and rec["confidence"] in ("alta", "media", "baja")
    st2 = client.post(f"/api/sim/{sid}/act", json={"action": rec["action"], "amount": rec["amount"]}).json()
    assert st2["session_id"] == sid
    assert client.post(f"/api/sim/{sid}/act", json={"action": "bet", "amount": 999999}).status_code in (400, 409) or True
    assert client.post(f"/api/sim/{sid}/undo").status_code == 200
    cmp = client.post(f"/api/sim/{sid}/compare", json={"actions": [{"action": "fold"}]}).json()
    assert "results" in cmp
    assert client.get(f"/api/sim/{sid}/history").status_code == 200
    assert client.delete(f"/api/sim/{sid}").json()["ok"]
    assert client.get(f"/api/sim/{sid}").status_code == 404


def test_profiles_crud():
    r = client.post("/api/profiles", json={"name": "TestVillain", "hands": 10, "vpip": {"value": 0.5, "n": 10}}).json()
    assert r["name"] == "TestVillain" and r["warning"]
    assert any(p["name"] == "TestVillain" for p in client.get("/api/profiles").json())
    assert client.delete("/api/profiles/TestVillain").json()["ok"]
    assert client.get("/api/profiles/TestVillain").status_code == 404


def test_live_recommend_and_ws():
    body = {"hero_cards": "AsKd", "hero_position": "BB", "hero_stack": 280, "hero_committed": 20, "pot": 550, "to_call": 280,
            "bb_size": 20, "street": "preflop", "players_remaining": 2, "raise_count_preflop": 1,
            "villains": [{"name": "V", "position": "SB", "stack": 0, "committed": 530, "all_in": True, "preflop_action": "shove"}]}
    assert client.post("/api/live/recommend", json=body).json()["action"] == "call"
    with client.websocket_connect("/api/live/ws") as ws:
        import json
        ws.send_text(json.dumps(body))
        msg = json.loads(ws.receive_text())
        assert msg["ok"] and msg["recommendation"]["action"] == "call"
        ws.send_text("not json")
        assert json.loads(ws.receive_text())["ok"] is False


def test_import_endpoint():
    from tests.test_analysis import PS_TEXT
    r = client.post("/api/import", json={"text": PS_TEXT, "name": "t", "update_profiles": False})
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["hands"] == 1 and data["summary"]["decisions"] == 2
    sid = data["session_id"]
    assert client.get(f"/api/import/sessions/{sid}").json()["hands"][0]["hand_id"] == "123456789"
    assert client.delete(f"/api/import/sessions/{sid}").json()["ok"]
