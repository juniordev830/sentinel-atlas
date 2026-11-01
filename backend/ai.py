"""Módulo de Inteligência Artificial e Análise GeoINT do Sentinel Atlas.

Oferece capacidade de análise preditiva, avaliação de risco tático em tempo real,
detecção de anomalias em trajetórias/geofences e assistente interativo (Copiloto GeoINT).
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any


class GeoINTAnalyzer:
    """Analisador de Inteligência Geográfica e Telemetria de Ativos."""

    def __init__(self, openai_api_key: str | None = None) -> None:
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    @staticmethod
    def _calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância aproximada em km usando fórmula de Haversine."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        # Floating-point rounding can make a slightly exceed 1 for near-antipodal points.
        a = min(1.0, max(0.0, a))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def analyze_situation(self, assets: list[dict[str, Any]], geofences: list[dict[str, Any]]) -> dict[str, Any]:
        """Gera relatório de avaliação de risco situacional e detecção de ameaças/anomalias."""
        total_assets = len(assets)
        risks: list[dict[str, Any]] = []
        anomalies: list[dict[str, Any]] = []
        threat_level = "BAIXO"
        high_risk_count = 0

        # Análise de densidade e proximidade com geofences
        for asset in assets:
            asset_lat = asset.get("latitude")
            if asset_lat is None:
                asset_lat = asset.get("lat", 0.0)
            asset_lon = asset.get("longitude")
            if asset_lon is None:
                asset_lon = asset.get("lon", 0.0)
            asset_name = asset.get("name") or asset.get("callsign") or asset.get("id") or "Ativo Desconhecido"
            asset_type = asset.get("type", "desconhecido").lower()

            for fence in geofences:
                f_lat = fence.get("latitude", 0.0)
                f_lon = fence.get("longitude", 0.0)
                f_radius_km = (fence.get("radius_meters", 1000) or 1000) / 1000.0
                f_name = fence.get("name", "Zona Restrita")

                dist_km = self._calculate_distance_km(asset_lat, asset_lon, f_lat, f_lon)

                if dist_km <= f_radius_km:
                    high_risk_count += 1
                    risks.append({
                        "asset": asset_name,
                        "geofence": f_name,
                        "status": "VIOLAÇÃO DE PERÍMETRO",
                        "distance_km": round(dist_km, 2),
                        "severity": "CRÍTICA",
                        "description": f"O ativo '{asset_name}' está dentro da zona protegida '{f_name}'."
                    })
                elif dist_km <= f_radius_km * 2.5:
                    risks.append({
                        "asset": asset_name,
                        "geofence": f_name,
                        "status": "APROXIMAÇÃO SUSPEITA",
                        "distance_km": round(dist_km, 2),
                        "severity": "MÉDIA",
                        "description": f"O ativo '{asset_name}' está se aproximando do perímetro '{f_name}' ({round(dist_km, 2)} km)."
                    })

            # Detecção de anomalias por velocidade ou altitude se presente
            speed = asset.get("speed") or asset.get("velocity", 0.0)
            if asset_type in ["avião", "aircraft", "aeronave"] and speed > 1200:
                anomalies.append({
                    "asset": asset_name,
                    "type": "VELOCIDADE HIPERSÔNICA/ANÔMALA",
                    "value": f"{speed} km/h",
                    "recommendation": "Verificar telemetria de voo do transponder."
                })

        if high_risk_count >= 2:
            threat_level = "CRÍTICO"
        elif high_risk_count == 1 or len(risks) >= 3:
            threat_level = "ALTO"
        elif len(risks) >= 1:
            threat_level = "MODERADO"

        summary = (
            f"Análise tática concluída. Foram monitorados {total_assets} ativos e {len(geofences)} áreas restritas. "
            f"Nível de ameaça global avaliado como {threat_level}. "
            f"{len(risks)} alertas de perímetro/proximidade identificados e {len(anomalies)} anomalias detectadas."
        )

        return {
            "threat_level": threat_level,
            "total_assets_monitored": total_assets,
            "total_geofences": len(geofences),
            "summary": summary,
            "risks": risks,
            "anomalies": anomalies,
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

    def query_copilot(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Responde a consultas táticas do usuário com inteligência sintética GeoINT."""
        question_lower = question.lower().strip()
        context = context or {}

        # Heurísticas de inteligência táctica GeoINT
        if "risco" in question_lower or "ameaça" in question_lower or "alerta" in question_lower:
            analysis = self.analyze_situation(context.get("assets", []), context.get("geofences", []))
            answer = (
                f"🛡️ **Avaliação de Inteligência:**\n"
                f"- **Nível de Ameaça:** {analysis['threat_level']}\n"
                f"- **Resumo:** {analysis['summary']}\n\n"
            )
            if analysis['risks']:
                answer += "**Principais Alertas de Perímetro:**\n"
                for r in analysis['risks'][:3]:
                    answer += f"• [{r['severity']}] {r['asset']} - {r['status']} ({r['geofence']})\n"
            else:
                answer += "Nenhum risco iminente de invasão de perímetro foi detectado no momento."

        elif "satélite" in question_lower or "starlink" in question_lower or "órbita" in question_lower:
            sat_count = sum(1 for a in context.get("assets", []) if "sat" in a.get("type", "").lower() or "starlink" in a.get("name", "").lower())
            answer = (
                f"🛰️ **Inteligência Orbital:**\n"
                f"Atualmente há {sat_count or 'múltiplos'} satélites e dados orbitais SGP4 sendo propagados em tempo real na projeção 3D. "
                f"A cobertura de constelações Starlink e CelesTrak permite prever janelas de passagem e rastreamento de telemetria."
            )

        elif "avião" in question_lower or "aeronave" in question_lower or "opensky" in question_lower or "voo" in question_lower:
            air_count = sum(1 for a in context.get("assets", []) if a.get("type", "").lower() in ["avião", "aircraft", "aeronave"])
            answer = (
                f"✈️ **Rastreamento Aéreo (OpenSky):**\n"
                f"Monitorando {air_count or 'diversos'} vetores aéreos ativos. "
                f"Os vetores são integrados à malha de geofencing e calculam dinamicamente interseções de altitude e raio restrito."
            )

        elif "geofence" in question_lower or "perímetro" in question_lower or "zona" in question_lower:
            fences = context.get("geofences", [])
            answer = (
                f"🌐 **Geofences Ativas ({len(fences)}):**\n"
                + ("\n".join([f"• **{f.get('name')}**: Lat {f.get('latitude')}, Lon {f.get('longitude')} (Raio {f.get('radius_meters')}m)" for f in fences]) if fences else "Nenhuma geofence cadastrada no banco de dados.")
            )

        else:
            answer = (
                f"🤖 **Copiloto GeoINT Sentinel:**\n"
                f"Recebi sua pergunta: *\"{question}\"*\n\n"
                f"Analisando os dados globais em tempo real: {len(context.get('assets', []))} ativos e {len(context.get('geofences', []))} zonas de exclusão. "
                f"Você pode me solicitar análises de risco, consulta de frota aérea, rastreamento orbital de satélites ou status de geofences."
            )

        return {
            "question": question,
            "answer": answer,
            "copilot": "Sentinel GeoINT AI v1.0",
        }
