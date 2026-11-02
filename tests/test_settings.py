import os
import unittest
from unittest.mock import patch

from python.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_public_sources_are_available_without_credentials(self):
        names = Settings.from_environment().enabled_sources()
        self.assertIn("NASA GIBS", names)
        self.assertIn("USGS Earthquakes", names)
        self.assertIn("CelesTrak satellites", names)

    def test_example_credentials_do_not_enable_private_sources(self):
        with patch.dict(os.environ, {
            "GOOGLE_MAPS_API_KEY": "configured-later",
            "AISSTREAM_API_KEY": "",
        }, clear=False):
            names = Settings.from_environment().enabled_sources()
        self.assertNotIn("Google Maps", names)
        self.assertNotIn("AISStream vessels", names)

    def test_production_requires_long_api_token(self):
        with patch.dict(os.environ, {
            "SENTINEL_ENV": "production",
            "SENTINEL_API_TOKEN": "",
        }, clear=False):
            with self.assertRaisesRegex(ValueError, "at least 32 characters"):
                Settings.from_environment()

    def test_production_accepts_long_api_token(self):
        token = "test-token-" + ("x" * 32)
        with patch.dict(os.environ, {
            "SENTINEL_ENV": "production",
            "SENTINEL_API_TOKEN": token,
        }, clear=False):
            settings = Settings.from_environment()
        self.assertEqual(settings.environment, "production")
        self.assertEqual(settings.api_token, token)


if __name__ == "__main__":
    unittest.main()
