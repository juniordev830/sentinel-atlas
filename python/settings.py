"""Configuração dos conectores externos do Projeto Sentinel Atlas."""

from dataclasses import dataclass
import os
from pathlib import Path


def _load_local_env() -> None:
    """Carrega pares simples do .env sem sobrescrever variáveis do sistema."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _optional_env(name: str) -> str | None:
    """Retorna apenas credenciais reais, ignorando valores vazios ou de exemplo."""
    value = os.getenv(name, "").strip()
    if not value or value.lower() in {"configured-later", "change-me", "your-key-here"}:
        return None
    return value


@dataclass(frozen=True)
class Settings:
    google_maps_api_key: str | None
    copernicus_client_id: str | None
    copernicus_client_secret: str | None
    aisstream_api_key: str | None
    opensky_client_id: str | None
    opensky_client_secret: str | None
    nasa_gibs_base_url: str
    usgs_earthquake_feed: str
    celestrak_gp_url: str
    celestrak_starlink_url: str
    alert_webhook_url: str | None
    api_token: str | None
    environment: str

    @classmethod
    def from_environment(cls) -> "Settings":
        _load_local_env()
        environment = os.getenv("SENTINEL_ENV", "development").strip().lower()
        api_token = _optional_env("SENTINEL_API_TOKEN")
        if environment == "production" and (not api_token or len(api_token) < 32):
            raise ValueError(
                "SENTINEL_API_TOKEN must contain at least 32 characters when SENTINEL_ENV=production"
            )

        return cls(
            google_maps_api_key=_optional_env("GOOGLE_MAPS_API_KEY"),
            copernicus_client_id=_optional_env("COPERNICUS_CLIENT_ID"),
            copernicus_client_secret=_optional_env("COPERNICUS_CLIENT_SECRET"),
            aisstream_api_key=_optional_env("AISSTREAM_API_KEY"),
            opensky_client_id=_optional_env("OPENSKY_CLIENT_ID"),
            opensky_client_secret=_optional_env("OPENSKY_CLIENT_SECRET"),
            nasa_gibs_base_url=os.getenv("NASA_GIBS_BASE_URL", "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"),
            usgs_earthquake_feed=os.getenv("USGS_EARTHQUAKE_FEED", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"),
            celestrak_gp_url=os.getenv("CELESTRAK_GP_URL", "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"),
            celestrak_starlink_url=os.getenv("CELESTRAK_STARLINK_URL", "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json"),
            alert_webhook_url=_optional_env("SENTINEL_ALERT_WEBHOOK_URL"),
            api_token=api_token,
            environment=environment,
        )

    def enabled_sources(self) -> list[str]:
        sources = ["NASA GIBS", "USGS Earthquakes", "CelesTrak satellites"]
        if self.google_maps_api_key: sources.append("Google Maps")
        if self.copernicus_client_id and self.copernicus_client_secret: sources.append("Copernicus Sentinel")
        if self.aisstream_api_key: sources.append("AISStream vessels")
        if self.opensky_client_id and self.opensky_client_secret: sources.append("OpenSky aircraft")
        return sources


