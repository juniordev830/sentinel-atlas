import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.storage import GeofenceStore
from python.gps_core import Geofence, Position


class GeofenceStoreTests(unittest.TestCase):
    def test_geofences_survive_a_new_store_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentinel.sqlite3"
            GeofenceStore(path).save(Geofence("base", -23.55, -46.63, 250))
            saved = GeofenceStore(path).list()
        self.assertEqual(saved, [Geofence("base", -23.55, -46.63, 250)])

    def test_delete_geofence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentinel.sqlite3"
            store = GeofenceStore(path)
            store.save(Geofence("base", -23.55, -46.63, 250))
            self.assertTrue(store.delete("base"))
            self.assertFalse(store.delete("base"))
            self.assertEqual(store.list(), [])

    def test_position_history_is_limited_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentinel.sqlite3"
            store = GeofenceStore(path)
            store.save_position(Position(-23.55, -46.63, 1))
            store.save_position(Position(-23.56, -46.64, 2))
            saved = store.list_positions(1)
        self.assertEqual(saved, [Position(-23.56, -46.64, 2)])

    def test_gps_retention_limits_new_positions_without_removing_fences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentinel.sqlite3"
            with patch("backend.storage.POSITION_RETENTION_LIMIT", 3):
                store = GeofenceStore(path)
                store.save(Geofence("porto", -5.8, -35.2, 200))
                for index in range(5):
                    store.save_position(Position(-5.8, -35.2, float(index)))
                assert [item.timestamp for item in store.list_positions(100)] == [4.0, 3.0, 2.0]
                assert [f.name for f in store.list()] == ["porto"]

    def test_existing_database_is_never_pruned_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentinel.sqlite3"
            with patch("backend.storage.POSITION_RETENTION_LIMIT", None):
                store = GeofenceStore(path)
                for index in range(5):
                    store.save_position(Position(-5.8, -35.2, float(index)))
            with patch("backend.storage.POSITION_RETENTION_LIMIT", 2):
                reopened = GeofenceStore(path)
                # Simply starting a new process must not erase historical GPS data.
                assert [item.timestamp for item in reopened.list_positions(100)] == [4.0, 3.0, 2.0, 1.0, 0.0]
                # Only an opt-in writer can apply the operator's retention policy.
                reopened.save_position(Position(-5.8, -35.2, 5.0))
                assert [item.timestamp for item in reopened.list_positions(100)] == [5.0, 4.0]

    def test_default_retention_is_disabled_without_configuration(self):
        import os
        from backend.storage import _retention_limit_from_environment
        with patch.dict(os.environ, {}, clear=True):
            assert _retention_limit_from_environment() is None

    def test_retention_rejects_invalid_configuration(self):
        import os
        from backend.storage import _retention_limit_from_environment
        for value in ("0", "-1", "abc", "1000001", "1.5"):
            with patch.dict(os.environ, {"SENTINEL_POSITION_RETENTION_LIMIT": value}):
                with self.assertRaises(ValueError):
                    _retention_limit_from_environment()

    def test_gps_timestamps_with_ties_have_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GeofenceStore(Path(directory) / "sentinel.sqlite3")
            store.save_position(Position(0, 1, 123))
            store.save_position(Position(0, 2, 123))
            assert [p.longitude for p in store.list_positions(2)] == [2, 1]


if __name__ == "__main__":
    unittest.main()
