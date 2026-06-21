import httpx
from utils.logger import log

# GPS coordinates for major cricket grounds worldwide
VENUE_COORDINATES = {
    # ── India ───────────────────────────────────
    "wankhede stadium": (18.9388, 72.8258),
    "wankhede": (18.9388, 72.8258),
    "mumbai": (18.9388, 72.8258),
    "eden gardens": (22.5646, 88.3433),
    "kolkata": (22.5646, 88.3433),
    "m. chinnaswamy stadium": (12.9788, 77.5996),
    "chinnaswamy": (12.9788, 77.5996),
    "bengaluru": (12.9788, 77.5996),
    "bangalore": (12.9788, 77.5996),
    "narendra modi stadium": (23.0916, 72.5950),
    "motera": (23.0916, 72.5950),
    "ahmedabad": (23.0916, 72.5950),
    "arun jaitley stadium": (28.6377, 77.2433),
    "feroz shah kotla": (28.6377, 77.2433),
    "delhi": (28.6377, 77.2433),
    "ma chidambaram stadium": (13.0627, 80.2792),
    "chepauk": (13.0627, 80.2792),
    "chennai": (13.0627, 80.2792),
    "rajiv gandhi international": (17.4065, 78.5506),
    "hyderabad": (17.4065, 78.5506),
    "is bindra stadium": (30.6880, 76.7379),
    "mohali": (30.6880, 76.7379),
    "barabati stadium": (20.4625, 85.8828),
    "cuttack": (20.4625, 85.8828),
    "greenfield international": (8.5330, 76.9108),
    "thiruvananthapuram": (8.5330, 76.9108),
    "brsabv ekana": (26.8470, 80.9485),
    "lucknow": (26.8470, 80.9485),
    "sawai mansingh stadium": (26.8949, 75.8034),
    "jaipur": (26.8949, 75.8034),
    "maharashtra cricket association": (18.6771, 73.8710),
    "pune": (18.6771, 73.8710),
    "holkar cricket stadium": (22.7238, 75.8636),
    "indore": (22.7238, 75.8636),
    "himachal pradesh cricket": (32.1179, 76.5382),
    "dharamsala": (32.1179, 76.5382),
    "aca stadium": (26.1550, 91.7682),
    "guwahati": (26.1550, 91.7682),
    # ── Australia ───────────────────────────────
    "melbourne cricket ground": (-37.8200, 144.9834),
    "mcg": (-37.8200, 144.9834),
    "melbourne": (-37.8200, 144.9834),
    "sydney cricket ground": (-33.8917, 151.2247),
    "scg": (-33.8917, 151.2247),
    "sydney": (-33.8917, 151.2247),
    "adelaide oval": (-34.9155, 138.5961),
    "adelaide": (-34.9155, 138.5961),
    "the gabba": (-27.4858, 153.0382),
    "gabba": (-27.4858, 153.0382),
    "brisbane": (-27.4858, 153.0382),
    "waca ground": (-31.9604, 115.8792),
    "perth stadium": (-31.9512, 115.8892),
    "optus stadium": (-31.9512, 115.8892),
    "perth": (-31.9604, 115.8792),
    "bellerive oval": (-42.8741, 147.3736),
    "hobart": (-42.8741, 147.3736),
    "manuka oval": (-35.3184, 149.1353),
    "canberra": (-35.3184, 149.1353),
    # ── England ─────────────────────────────────
    "lord's": (51.5294, -0.1727),
    "lords": (51.5294, -0.1727),
    "the oval": (51.4838, -0.1147),
    "kia oval": (51.4838, -0.1147),
    "oval": (51.4838, -0.1147),
    "edgbaston": (52.4559, -1.9025),
    "birmingham": (52.4559, -1.9025),
    "old trafford": (53.4569, -2.2873),
    "manchester": (53.4569, -2.2873),
    "headingley": (53.8178, -1.5822),
    "leeds": (53.8178, -1.5822),
    "trent bridge": (52.9369, -1.1322),
    "nottingham": (52.9369, -1.1322),
    "rose bowl": (50.9247, -1.3221),
    "southampton": (50.9247, -1.3221),
    "sophia gardens": (51.4723, -3.1876),
    "cardiff": (51.4723, -3.1876),
    "county ground": (51.3833, -2.3597),
    "bristol": (51.3833, -2.3597),
    # ── Pakistan ────────────────────────────────
    "gaddafi stadium": (31.5130, 74.3370),
    "lahore": (31.5130, 74.3370),
    "national stadium": (24.8920, 67.0652),
    "karachi": (24.8920, 67.0652),
    "rawalpindi cricket stadium": (33.5994, 73.0551),
    "rawalpindi": (33.5994, 73.0551),
    "multan cricket stadium": (30.1984, 71.4687),
    "multan": (30.1984, 71.4687),
    "faisalabad": (31.4180, 73.0750),
    # ── South Africa ────────────────────────────
    "wanderers stadium": (-26.1378, 28.0610),
    "wanderers": (-26.1378, 28.0610),
    "johannesburg": (-26.1378, 28.0610),
    "newlands": (-33.9274, 18.4383),
    "cape town": (-33.9274, 18.4383),
    "supersport park": (-25.7455, 28.2239),
    "centurion": (-25.7455, 28.2239),
    "kingsmead": (-29.8550, 31.0283),
    "durban": (-29.8550, 31.0283),
    "st george's park": (-33.9728, 25.6108),
    "port elizabeth": (-33.9728, 25.6108),
    "gqeberha": (-33.9728, 25.6108),
    "mangaung oval": (-29.1070, 26.2100),
    "bloemfontein": (-29.1070, 26.2100),
    # ── New Zealand ─────────────────────────────
    "basin reserve": (-41.2900, 174.7786),
    "wellington": (-41.2900, 174.7786),
    "hagley oval": (-43.5365, 172.6225),
    "christchurch": (-43.5365, 172.6225),
    "eden park": (-36.8749, 174.7449),
    "auckland": (-36.8749, 174.7449),
    "seddon park": (-37.7879, 175.2832),
    "hamilton": (-37.7879, 175.2832),
    "bay oval": (-37.6883, 176.2824),
    "mount maunganui": (-37.6883, 176.2824),
    # ── Sri Lanka ───────────────────────────────
    "r. premadasa stadium": (6.9181, 79.8683),
    "premadasa": (6.9181, 79.8683),
    "colombo": (6.9181, 79.8683),
    "pallekele": (7.2862, 80.6375),
    "kandy": (7.2862, 80.6375),
    "galle international": (6.0326, 80.2152),
    "galle": (6.0326, 80.2152),
    "dambulla": (7.8621, 80.6516),
    "rangiri dambulla": (7.8621, 80.6516),
    # ── Bangladesh ──────────────────────────────
    "sher-e-bangla": (23.7383, 90.3682),
    "mirpur": (23.7383, 90.3682),
    "dhaka": (23.7383, 90.3682),
    "zahur ahmed chowdhury": (22.3484, 91.7923),
    "chattogram": (22.3484, 91.7923),
    "chittagong": (22.3484, 91.7923),
    "sylhet international": (24.9003, 91.8625),
    "sylhet": (24.9003, 91.8625),
    # ── West Indies ─────────────────────────────
    "kensington oval": (13.1040, -59.6245),
    "bridgetown": (13.1040, -59.6245),
    "barbados": (13.1040, -59.6245),
    "sabina park": (18.0103, -76.7469),
    "kingston": (18.0103, -76.7469),
    "jamaica": (18.0103, -76.7469),
    "queen's park oval": (10.6685, -61.5117),
    "port of spain": (10.6685, -61.5117),
    "trinidad": (10.6685, -61.5117),
    "sir vivian richards stadium": (17.1127, -61.7911),
    "antigua": (17.1127, -61.7911),
    "providence stadium": (6.8094, -58.1445),
    "guyana": (6.8094, -58.1445),
    "daren sammy": (14.0667, -60.9500),
    "st lucia": (14.0667, -60.9500),
    "warner park": (17.2984, -62.7191),
    "st kitts": (17.2984, -62.7191),
    # ── Zimbabwe ────────────────────────────────
    "harare sports club": (-17.8037, 31.0418),
    "harare": (-17.8037, 31.0418),
    "queens sports club": (-20.1564, 28.5750),
    "bulawayo": (-20.1564, 28.5750),
    # ── Afghanistan ─────────────────────────────
    "greater noida": (28.4744, 77.5040),
    "lucknow (afghanistan)": (26.8470, 80.9485),
    "sharjah cricket stadium": (25.3361, 55.4103),
    "sharjah": (25.3361, 55.4103),
    "sheikh zayed stadium": (24.4539, 54.6100),
    "abu dhabi": (24.4539, 54.6100),
    "dubai international": (25.0601, 55.2114),
    "dubai": (25.0601, 55.2114),
    # ── Ireland ─────────────────────────────────
    "malahide": (53.4467, -6.1519),
    "clontarf": (53.3647, -6.2100),
    "dublin": (53.4467, -6.1519),
    "stormont": (54.6025, -5.8306),
    "belfast": (54.6025, -5.8306),
    # ── USA (MLC Venues) ────────────────────────
    "grand prairie stadium": (32.7456, -96.9956),
    "grand prairie": (32.7456, -96.9956),
    "dallas": (32.7456, -96.9956),
    "church street park": (36.5465, -82.5618),
    "morrisville": (35.8234, -78.8250),
    "nassau county": (40.7178, -73.5594),
    "new york": (40.7178, -73.5594),
    "central broward": (26.1328, -80.2068),
    "lauderhill": (26.1328, -80.2068),
    "florida": (26.1328, -80.2068),
    "prairie view cricket complex": (30.0916, -95.9858),
    "houston": (30.0916, -95.9858),
    "george r. brown": (29.7519, -95.3560),
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _find_coordinates(venue_name: str) -> tuple | None:
    """Look up GPS coordinates for a venue using fuzzy matching."""
    if not venue_name:
        return None

    venue_lower = venue_name.lower().strip()

    # Direct lookup
    if venue_lower in VENUE_COORDINATES:
        return VENUE_COORDINATES[venue_lower]

    # Substring match
    for key, coords in VENUE_COORDINATES.items():
        if key in venue_lower or venue_lower in key:
            return coords

    # Word-level match (check if any key word appears)
    venue_words = set(venue_lower.split())
    best_match = None
    best_score = 0
    for key, coords in VENUE_COORDINATES.items():
        key_words = set(key.split())
        overlap = len(venue_words & key_words)
        if overlap > best_score and overlap >= 1:
            best_score = overlap
            best_match = coords

    return best_match


def get_weather(venue_name: str, date_str: str) -> dict | None:
    """
    Get weather forecast for a cricket venue on a specific date.
    
    Args:
        venue_name: Name of the cricket venue/ground
        date_str: Date in YYYY-MM-DD format
    
    Returns:
        Dict with weather summary or None if unavailable
    """
    coords = _find_coordinates(venue_name)
    if not coords:
        log.warning(f"No coordinates found for venue: {venue_name}")
        return None

    lat, lon = coords

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            "hourly": "relative_humidity_2m",
            "start_date": date_str,
            "end_date": date_str,
            "timezone": "UTC",
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        hourly = data.get("hourly", {})

        temp_max = daily.get("temperature_2m_max", [None])[0]
        temp_min = daily.get("temperature_2m_min", [None])[0]
        rain_prob = daily.get("precipitation_probability_max", [0])[0] or 0
        rain_mm = daily.get("precipitation_sum", [0])[0] or 0

        # Get evening humidity (hours 15-21 UTC ~= typical match time window)
        humidity_vals = hourly.get("relative_humidity_2m", [])
        evening_humidity = 0
        if len(humidity_vals) >= 22:
            evening_slice = humidity_vals[15:22]
            evening_humidity = sum(evening_slice) / len(evening_slice) if evening_slice else 0
        elif humidity_vals:
            evening_humidity = sum(humidity_vals) / len(humidity_vals)

        dew_factor = evening_humidity > 80

        # Determine match risk
        if rain_prob >= 70 or rain_mm >= 10:
            match_risk = "HIGH — significant rain expected"
        elif rain_prob >= 40 or rain_mm >= 3:
            match_risk = "MODERATE — some rain possible"
        else:
            match_risk = "LOW — clear or minimal rain"

        # Build summary
        summary_parts = [f"Max {temp_max}°C"]
        if rain_prob > 20:
            summary_parts.append(f"{rain_prob}% rain chance ({rain_mm:.1f}mm)")
        else:
            summary_parts.append("dry conditions expected")
        if dew_factor:
            summary_parts.append("dew likely in evening")
        summary = ", ".join(summary_parts)

        result = {
            "temperature_max_c": temp_max,
            "temperature_min_c": temp_min,
            "rain_probability_pct": rain_prob,
            "rain_expected_mm": round(rain_mm, 1),
            "evening_humidity_pct": round(evening_humidity, 1),
            "dew_factor_likely": dew_factor,
            "match_risk": match_risk,
            "summary": summary,
        }

        log.debug(f"Weather for {venue_name}: {summary}")
        return result

    except httpx.TimeoutException:
        log.error(f"Weather API timed out for {venue_name}")
        return None
    except Exception as e:
        log.error(f"Weather fetch failed for {venue_name}: {e}")
        return None
