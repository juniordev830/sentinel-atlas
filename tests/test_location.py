"""Testes para o serviço e endpoint de inteligência de localização."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.location import get_location_info


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        test_sources = patch("backend.location.fetch_json", return_value={})
        self.addCleanup(test_sources.stop)
        test_sources.start()

    def test_get_location_info_sp(self):
        info = get_location_info(-23.5505, -46.6333)
        self.assertEqual(info["latitude"], -23.5505)
        self.assertEqual(info["longitude"], -46.6333)
        self.assertIn(info["country"], ["Brasil", "Oceano / Território Internacional"])
        self.assertIn("demographics", info)
        self.assertIn("estimated_population", info["demographics"])
        self.assertIn("business", info)
        self.assertIn("sample_companies", info["business"])

    def test_api_location_info_endpoint(self):
        response = self.client.get("/api/location/info?lat=-23.5505&lng=-46.6333")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["latitude"], -23.5505)
        self.assertEqual(data["longitude"], -46.6333)
        self.assertIn("demographics", data)
        self.assertIn("business", data)

    def test_api_location_info_invalid_coords(self):
        response = self.client.get("/api/location/info?lat=100&lng=-46.6333")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
