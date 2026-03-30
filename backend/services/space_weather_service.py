"""
NOAA SWPC (Space Weather Prediction Center) service.

Fetches real-time space weather data from NOAA SWPC JSON API:
  - Solar proton flux (GOES)
  - Geomagnetic Kp index
  - Solar wind speed/density
  - X-ray flux (flare activity)

Data source: https://services.swpc.noaa.gov/
All endpoints are free, no API key required.
"""

import httpx
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

SWPC_BASE = "https://services.swpc.noaa.gov"

# Timeouts: 10s connect, 15s read
_TIMEOUT = httpx.Timeout(10.0, read=15.0)


@dataclass
class SpaceWeatherSnapshot:
    """Current space weather conditions relevant to satellite operations."""
    kp_index: float = 0.0            # 0-9 geomagnetic activity
    kp_category: str = "QUIET"       # QUIET | UNSETTLED | ACTIVE | STORM | SEVERE_STORM
    solar_wind_speed_km_s: float = 0.0
    solar_wind_density_p_cm3: float = 0.0
    proton_flux_pfu: float = 0.0     # >= 10 MeV protons (pfu)
    electron_flux: float = 0.0       # >= 2 MeV electrons
    xray_flux: float = 0.0           # 0.1-0.8nm X-ray flux (W/m²)
    flare_class: str = "NONE"        # A | B | C | M | X
    storm_warning: bool = False
    data_sources: list[str] | None = None

    @property
    def geomag_severity(self) -> str:
        if self.kp_index >= 8:
            return "CRITICAL"
        if self.kp_index >= 6:
            return "HIGH"
        if self.kp_index >= 4:
            return "MEDIUM"
        return "LOW"


def _classify_kp(kp: float) -> str:
    if kp >= 8:
        return "SEVERE_STORM"
    if kp >= 6:
        return "STORM"
    if kp >= 4:
        return "ACTIVE"
    if kp >= 3:
        return "UNSETTLED"
    return "QUIET"


def _classify_flare(xray: float) -> str:
    if xray >= 1e-4:
        return "X"
    if xray >= 1e-5:
        return "M"
    if xray >= 1e-6:
        return "C"
    if xray >= 1e-7:
        return "B"
    return "A"


async def fetch_space_weather() -> SpaceWeatherSnapshot:
    """
    Fetch current space weather from NOAA SWPC.

    Combines multiple SWPC endpoints for a comprehensive snapshot.
    Falls back to defaults if any endpoint fails.
    """
    snapshot = SpaceWeatherSnapshot(data_sources=[])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # 1. Planetary K-index (3-hour)
        try:
            resp = await client.get(f"{SWPC_BASE}/products/noaa-planetary-k-index.json")
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1:
                    latest = data[-1]  # last entry is most recent
                    kp_val = float(latest[1]) if latest[1] else 0.0
                    snapshot.kp_index = kp_val
                    snapshot.kp_category = _classify_kp(kp_val)
                    snapshot.data_sources.append("NOAA Planetary K-index")
        except Exception:
            log.warning("Kp fetch failed", exc_info=True)

        # 2. Solar wind plasma (DSCOVR)
        try:
            resp = await client.get(f"{SWPC_BASE}/products/solar-wind/plasma-7-day.json")
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1:
                    # Find most recent non-null entry
                    for entry in reversed(data[1:]):
                        density, speed = entry[1], entry[2]
                        if density and speed:
                            snapshot.solar_wind_density_p_cm3 = float(density)
                            snapshot.solar_wind_speed_km_s = float(speed)
                            snapshot.data_sources.append("DSCOVR Solar Wind Plasma")
                            break
        except Exception:
            log.warning("Solar wind fetch failed", exc_info=True)

        # 3. GOES X-ray flux
        try:
            resp = await client.get(f"{SWPC_BASE}/json/goes/primary/xrays-6-hour.json")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    latest = data[-1]
                    xray = float(latest.get("flux", 0))
                    snapshot.xray_flux = xray
                    snapshot.flare_class = _classify_flare(xray)
                    snapshot.data_sources.append("GOES X-ray Flux")
        except Exception:
            log.warning("X-ray fetch failed", exc_info=True)

        # 4. GOES proton flux
        try:
            resp = await client.get(f"{SWPC_BASE}/json/goes/primary/integral-protons-6-hour.json")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    # Find >=10 MeV channel
                    for entry in reversed(data):
                        if entry.get("energy", "") == ">=10 MeV":
                            snapshot.proton_flux_pfu = float(entry.get("flux", 0))
                            snapshot.data_sources.append("GOES Proton Flux")
                            break
        except Exception:
            log.warning("Proton flux fetch failed", exc_info=True)

        # Storm warning if Kp >= 5 or proton event
        snapshot.storm_warning = snapshot.kp_index >= 5 or snapshot.proton_flux_pfu >= 10

    return snapshot


def format_weather_summary(weather: SpaceWeatherSnapshot) -> str:
    """Format space weather into context string for agents."""
    return (
        f"Space Weather (NOAA SWPC):\n"
        f"  Kp Index: {weather.kp_index:.1f} ({weather.kp_category})\n"
        f"  Solar Wind: {weather.solar_wind_speed_km_s:.0f} km/s, "
        f"{weather.solar_wind_density_p_cm3:.1f} p/cm³\n"
        f"  X-ray Flux: {weather.xray_flux:.2e} W/m² (Class {weather.flare_class})\n"
        f"  Proton Flux (>=10 MeV): {weather.proton_flux_pfu:.2e} pfu\n"
        f"  Storm Warning: {'YES' if weather.storm_warning else 'No'}\n"
        f"  Geomagnetic Severity: {weather.geomag_severity}"
    )
