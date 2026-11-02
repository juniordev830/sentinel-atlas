"""Both distributions of the OSM-derived dams must remain byte-equivalent as features.

GeoJSON is the compact archival/review representation; JSONL is the runtime
streaming representation. Tests do not call the network or mutate source data.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "local_data" / "dams"


def test_dams_snapshot_matches_runtime_jsonl_exactly():
    archive = json.loads((DATA / "dams.geojson").read_text(encoding="utf-8"))
    runtime_lines = (DATA / "dams.geojsonl").read_text(encoding="utf-8").splitlines()
    assert archive["type"] == "FeatureCollection"
    assert len(runtime_lines) == 704
    assert len(archive["features"]) == len(runtime_lines)

    for index, (expected, line) in enumerate(zip(archive["features"], runtime_lines)):
        actual = json.loads(line)
        assert actual == expected, f"Dam data out of sync at feature {index}"
