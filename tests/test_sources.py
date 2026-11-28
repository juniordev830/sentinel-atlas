import unittest
from unittest.mock import patch

from backend.source_clients import fetch_celestrak, fetch_opensky, parse_tle_text


class SourceClientTests(unittest.TestCase):
    @patch("backend.source_clients.fetch_json", return_value=[{"NAME": "ISS"}])
    def test_celestrak_filters_non_objects(self, fetch):
        self.assertEqual(fetch_celestrak("https://example.test"), [{"NAME": "ISS"}])
        fetch.assert_called_once()

    @patch("backend.source_clients.fetch_json", return_value={"states": [["icao"]]})
    def test_opensky_returns_payload(self, fetch):
        self.assertEqual(fetch_opensky("https://example.test")["states"], [["icao"]])
        fetch.assert_called_once()

    def test_parse_tle_text_groups_name_and_two_lines(self):
        payload = "Starlink-1\n1 00005U 58002B   24001.00000000  .00000000  00000-0  00000-0 0  9999\n2 00005  34.2682 331.5174 1849677 331.7664  19.3264 10.82419157413667\n"
        records = parse_tle_text(payload)
        self.assertEqual(records[0]["OBJECT_NAME"], "Starlink-1")
        self.assertTrue(records[0]["TLE_LINE1"].startswith("1 "))


if __name__ == "__main__":
    unittest.main()


@patch("backend.source_clients.MAX_SOURCE_BYTES", 4)
@patch("backend.source_clients.source_opener.open")
def test_source_rejects_oversized_stream(open_source):
    from backend.source_clients import SourceUnavailable, fetch_text
    from pytest import raises

    response = open_source.return_value.__enter__.return_value
    response.headers = {}
    response.read.return_value = b"12345"
    with raises(SourceUnavailable):
        fetch_text("https://source.example.test/data")
    response.read.assert_called_once_with(5)
