import unittest
from unittest.mock import patch

from backend.routing import bicycle_route


class RoutingTests(unittest.TestCase):
    @patch("backend.routing.fetch_json", return_value={"code": "Ok", "routes": []})
    def test_bicycle_route_uses_osrm(self, fetch):
        result = bicycle_route(-23.55, -46.63, -23.56, -46.64)
        self.assertEqual(result["code"], "Ok")
        self.assertIn("router.project-osrm.org", fetch.call_args.args[0])
        self.assertIn("bicycle", fetch.call_args.args[0])

    def test_bicycle_route_rejects_coordinates_outside_geographic_bounds(self):
        invalid_routes = [
            (90.01, 0, 0, 0),
            (-90.01, 0, 0, 0),
            (0, 180.01, 0, 0),
            (0, -180.01, 0, 0),
            (0, 0, 91, 0),
            (0, 0, 0, 181),
        ]
        with patch("backend.routing.fetch_json") as fetch:
            for coordinates in invalid_routes:
                with self.subTest(coordinates=coordinates):
                    with self.assertRaises(ValueError):
                        bicycle_route(*coordinates)
            fetch.assert_not_called()

    def test_bicycle_route_rejects_non_finite_and_boolean_coordinates(self):
        invalid_routes = [
            (float("nan"), 0, 0, 0),
            (0, float("inf"), 0, 0),
            (0, 0, float("-inf"), 0),
            (True, 0, 0, 0),
        ]
        with patch("backend.routing.fetch_json") as fetch:
            for coordinates in invalid_routes:
                with self.subTest(coordinates=coordinates):
                    with self.assertRaises(ValueError):
                        bicycle_route(*coordinates)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
