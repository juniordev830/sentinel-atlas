from fastapi.testclient import TestClient

from backend.ai import GeoINTAnalyzer
from backend.app import app


def test_geoint_analyzer_situation_analysis():
    analyzer = GeoINTAnalyzer()
    assets = [
        {"id": "a1", "name": "Voo Tático 1", "type": "aircraft", "latitude": -23.55, "longitude": -46.63, "speed": 1300},
        {"id": "a2", "name": "Navio Patrulha", "type": "ship", "latitude": 0.0, "longitude": 0.0}
    ]
    geofences = [
        {"name": "Zona Protegida SP", "latitude": -23.5505, "longitude": -46.6333, "radius_meters": 5000}
    ]

    report = analyzer.analyze_situation(assets, geofences)
    assert "threat_level" in report
    assert report["total_assets_monitored"] == 2
    assert report["total_geofences"] == 1
    assert len(report["risks"]) >= 1
    assert report["risks"][0]["status"] == "VIOLAÇÃO DE PERÍMETRO"
    assert len(report["anomalies"]) == 1


def test_geoint_analyzer_copilot_queries():
    analyzer = GeoINTAnalyzer()
    ctx = {
        "assets": [{"type": "satellite", "name": "Starlink-1"}],
        "geofences": [{"name": "Base Beta", "latitude": -10, "longitude": -10, "radius_meters": 1000}]
    }

    res_risk = analyzer.query_copilot("Qual é o risco atual?", ctx)
    assert "Avaliação de Inteligência" in res_risk["answer"]

    res_sat = analyzer.query_copilot("Como está o rastreamento de satélites?", ctx)
    assert "Inteligência Orbital" in res_sat["answer"]

    res_gf = analyzer.query_copilot("Quais são as geofences ativas?", ctx)
    assert "Base Beta" in res_gf["answer"]


def test_ai_api_endpoints():
    client = TestClient(app)

    # Teste POST /api/ai/analyze
    res_analyze = client.post("/api/ai/analyze", json={
        "assets": [{"name": "Vetor Alpha", "latitude": -23.55, "longitude": -46.63}],
        "geofences": [{"name": "Perímetro Alfa", "latitude": -23.55, "longitude": -46.63, "radius_meters": 2000}]
    })
    assert res_analyze.status_code == 200
    data_analyze = res_analyze.json()
    assert "threat_level" in data_analyze
    assert data_analyze["threat_level"] in ["BAIXO", "MODERADO", "ALTO", "CRÍTICO"]

    # Teste POST /api/ai/query
    res_query = client.post("/api/ai/query", json={
        "question": "Análise de risco do perímetro",
        "context": {}
    })
    assert res_query.status_code == 200
    data_query = res_query.json()
    assert "answer" in data_query
    assert "copilot" in data_query


def test_zero_coordinates_are_not_treated_as_missing():
    analyzer = GeoINTAnalyzer()
    report = analyzer.analyze_situation(
        assets=[{"name": "Equator asset", "latitude": 0.0, "lat": 20.0, "longitude": 0.0, "lon": 20.0}],
        geofences=[{"name": "Origin", "latitude": 0.0, "longitude": 0.0, "radius_meters": 1000}],
    )
    assert report["risks"]
    assert report["risks"][0]["status"] == "VIOLAÇÃO DE PERÍMETRO"


def test_haversine_distance_handles_antipodal_points():
    distance = GeoINTAnalyzer._calculate_distance_km(0.0, 0.0, 0.0, 180.0)
    assert 20000 < distance < 20100
