import pytest
from backend.app import AIAnalyzeInput, AIQueryInput
@pytest.mark.parametrize("asset", [{"lat": "bad", "lon": 0}, {"lat": 91, "lon": 0}, {"lat": 0, "lon": 0, "type": 42}, {"lat": 0, "lon": 0, "speed": float("inf")}])
def test_rejects_malformed_analysis(asset):
    with pytest.raises(ValueError):
        AIAnalyzeInput(assets=[asset])
def test_bounds_query_context():
    with pytest.raises(ValueError):
        AIQueryInput(question="risco", context={"assets": [{}] * 1001})
def test_valid_coordinates_are_accepted():
    assert AIAnalyzeInput(assets=[{"latitude": 0, "longitude": 0}]).assets
