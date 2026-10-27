# -*- coding: utf-8 -*-
"""A short weather report for Home: "7°  Light rain  ·  High 10°".

Comes from Met Éireann's open data forecast (no key, covers the whole island).
If that can't be reached, Open-Meteo is tried instead. Everything that touches
the network goes through a fetcher(url) function (sources.fetch by default), so
the reading can be checked offline.
"""
import calendar
import json
import os
import re
import time
import xml.etree.ElementTree as ET

from ..webcams import sources

MET_EIREANN = "http://openaccess.pf.api.met.ie/metno-wdb2ts/locationforecast?lat=%.4f;long=%.4f"
OPEN_METEO = ("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&current=temperature_2m,weather_code"
	",is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=2")
TOMORROW_FROM = 15  # from 3pm the day's warmest is past, so give tomorrow's high
ICONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "weather")

# Met Éireann symbol names, as plain words. Night-time words where they differ.
SYMBOLS = {
	"Sun": ("Sunny", "Clear"),
	"LightCloud": ("Mostly sunny", "Mostly clear"),
	"PartlyCloud": ("Partly cloudy", "Partly cloudy"),
	"Cloud": ("Cloudy", "Cloudy"),
	"Fog": ("Fog", "Fog"),
}

# Met Éireann symbols with an icon that isn't simply their name in Yr's naming.
ICON_NAMES = {"Sun": "clearsky", "LightCloud": "fair", "PartlyCloud": "partlycloudy", "Cloud": "cloudy",
	"Drizzle": "lightrain", "DrizzleSun": "lightrainshowers", "DrizzleThunder": "lightrainandthunder",
	"DrizzleThunderSun": "lightrainshowersandthunder"}

# Open-Meteo weather codes (WMO) as Yr icon names.
WMO_ICONS = [
	((0,), "clearsky"), ((1,), "fair"), ((2,), "partlycloudy"), ((3,), "cloudy"), ((45, 48), "fog"),
	((51, 53, 55, 56, 57, 61), "lightrain"), ((63, 66), "rain"), ((65, 67), "heavyrain"), ((71,), "lightsnow"),
	((73, 77), "snow"), ((75,), "heavysnow"), ((80,), "lightrainshowers"), ((81,), "rainshowers"),
	((82,), "heavyrainshowers"), ((85,), "snowshowers"), ((86,), "heavysnowshowers"), ((95,), "rainandthunder"),
	((96, 99), "heavyrainandthunder"),
]

# Open-Meteo weather codes (WMO), as plain words.
WMO = [
	((0,), "Sunny", "Clear"), ((1,), "Mostly sunny", "Mostly clear"), ((2,), "Partly cloudy", None), ((3,), "Cloudy", None),
	((45, 48), "Fog", None), ((51, 53, 55), "Drizzle", None), ((56, 57), "Freezing drizzle", None),
	((61,), "Light rain", None), ((63,), "Rain", None), ((65,), "Heavy rain", None), ((66, 67), "Freezing rain", None),
	((71,), "Light snow", None), ((73, 75, 77), "Snow", None), ((80,), "Light showers", None), ((81, 82), "Showers", None),
	((85, 86), "Snow showers", None), ((95, 96, 99), "Thunder", None),
]


class Report(object):
	def __init__(self, temperature, summary, high, day, source, fetched_at=None, icon=None):
		self.temperature = temperature
		self.summary = summary
		self.icon = icon  # path to a Yr weather icon, or None
		self.high = high
		self.day = day  # "today" or "tomorrow": which day the high is for
		self.source = source
		self.fetched_at = fetched_at if fetched_at is not None else time.time()

	@property
	def line(self):
		parts = ["%d°" % self.temperature]
		if self.summary:
			parts.append(self.summary)
		text = "  ".join(parts)
		if self.high is not None:
			text += "  ·  %s %d°" % ("High" if self.day == "today" else "Tomorrow", self.high)
		return text


REFRESH = 3600       # ask for a new forecast once an hour
TOO_OLD = 6 * 3600   # after this, stop showing a report rather than show a stale one
_latest = {"report": None, "location": None}


def latest(location):
	"""The last report for this location, unless it's too old to show."""
	saved = _latest["report"]
	if saved is None or _latest["location"] != location or time.time() - saved.fetched_at > TOO_OLD:
		return None
	return saved


def due(location):
	saved = _latest["report"]
	return saved is None or _latest["location"] != location or time.time() - saved.fetched_at > REFRESH


def remember(location, fresh):
	_latest["report"], _latest["location"] = fresh, location


def parse_location(text):
	"""(latitude, longitude) from "54.083, -6.450" as copied from a map, or None."""
	numbers = re.findall(r"-?\d+(?:\.\d+)?", text or "")
	if len(numbers) != 2:
		return None
	latitude, longitude = float(numbers[0]), float(numbers[1])
	if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
		return None
	return latitude, longitude


def report(latitude, longitude, fetcher=None, now=None):
	"""The current report: Met Éireann first, then Open-Meteo. Raises if neither answers."""
	fetcher = fetcher or sources.fetch
	now = time.time() if now is None else now
	try:
		return read_met_eireann(fetcher(MET_EIREANN % (latitude, longitude), binary=True), now)
	except Exception:
		return read_open_meteo(sources._text(fetcher(OPEN_METEO % (latitude, longitude))), now)


def read_met_eireann(data, now):
	"""Instant entries carry the temperature; hour-long ones the weather symbol.
	Takes the raw bytes: the XML parser reads the file's own encoding."""
	temperatures, symbols, light = [], [], {}
	for entry in ET.fromstring(data).iter("time"):
		start, end = _utc(entry.get("from")), _utc(entry.get("to"))
		location = entry.find("location")
		if location is None:
			continue
		temperature = location.find("temperature")
		symbol = location.find("symbol")
		if start == end and temperature is not None:
			temperatures.append((start, float(temperature.get("value"))))
			radiation = location.find("globalRadiation")
			if radiation is not None:
				light[start] = float(radiation.get("value") or 0)
		elif symbol is not None:
			symbols.append((start, end, symbol.get("id")))
	if not temperatures:
		raise ValueError("no temperatures in the forecast")
	temperatures.sort()
	nearest, current = min(temperatures, key=lambda pair: abs(pair[0] - now))
	# No sunlight reaching the ground means it's dark: say "Clear", not "Sunny".
	daytime = light[nearest] > 0 if nearest in light else _daytime(now)
	summary, icon = "", None
	for start, end, name in sorted(symbols):
		if start <= now < end or start >= now:
			summary, icon = symbol_words(name, daytime), symbol_icon(name, daytime)
			break
	day, (first, last) = _high_window(now)
	highs = [value for moment, value in temperatures if first <= moment < last]
	return Report(int(round(current)), summary, int(round(max(highs))) if highs else None, day, "Met Éireann", icon=icon)


def read_open_meteo(text, now):
	data = json.loads(text)
	current = data["current"]
	daily = data["daily"]
	day, _ = _high_window(now)
	index = 0 if day == "today" else 1
	highs = daily.get("temperature_2m_max") or []
	high = highs[index] if index < len(highs) else None
	daytime = bool(current["is_day"]) if "is_day" in current else _daytime(now)
	return Report(int(round(current["temperature_2m"])), wmo_words(current.get("weather_code"), daytime),
		int(round(high)) if high is not None else None, day, "Open-Meteo", icon=wmo_icon(current.get("weather_code"), daytime))


def symbol_words(name, daytime=True):
	"""Met Éireann's symbol names (Sun, LightRainSun, HeavySnowThunder...) as plain words."""
	name = (name or "").replace("Dark_", "")
	if name in SYMBOLS:
		return SYMBOLS[name][0 if daytime else 1]
	if "Thunder" in name:
		return "Thunder"
	strength = "Light " if name.startswith("Light") else ("Heavy " if name.startswith("Heavy") else "")
	for kind, word in (("Snow", "snow"), ("Sleet", "sleet"), ("Drizzle", "drizzle"), ("Rain", "rain")):
		if kind in name:
			if name.endswith("Sun"):
				return (strength + word + " showers").capitalize() if word != "drizzle" else "Drizzle"
			return (strength + word).capitalize()
	return ""


def symbol_icon(name, daytime=True):
	"""Met Éireann's symbol (LightRainSun, HeavySnowThunder...) as a Yr icon file, or None.

	Yr names it by strength, kind, showers ("Sun" in Met Éireann's name) and
	thunder: LightRainSun is lightrainshowers_day, HeavySnowThunder heavysnowandthunder.
	"""
	name = (name or "").replace("Dark_", "")
	if name in ICON_NAMES:
		return icon_path(ICON_NAMES[name], daytime)
	strength = "light" if name.startswith("Light") else ("heavy" if name.startswith("Heavy") else "")
	kind = next((word for word in ("Snow", "Sleet", "Rain") if word in name), None)
	if name == "Fog" or kind is None:
		return icon_path("fog", daytime) if name == "Fog" else None
	stem = strength + kind.lower() + ("showers" if "Sun" in name else "") + ("andthunder" if "Thunder" in name else "")
	return icon_path(stem, daytime)


def wmo_icon(code, daytime=True):
	for codes, stem in WMO_ICONS:
		if code in codes:
			return icon_path(stem, daytime)
	return None


def icon_path(stem, daytime=True):
	"""The file for a Yr icon name, trying its day or night version first. Yr spells
	two of its thundery shower icons "lights..."; those are tried too."""
	candidates = [stem + ("_day" if daytime else "_night"), stem]
	if stem.startswith("light"):
		candidates += [candidate.replace("light", "lights", 1) for candidate in candidates]
	for candidate in candidates:
		path = os.path.join(ICONS, candidate + ".png")
		if os.path.isfile(path):
			return path
	return None


def wmo_words(code, daytime=True):
	for codes, day_words, night_words in WMO:
		if code in codes:
			return day_words if daytime or not night_words else night_words
	return ""


def _high_window(now):
	"""Which day's high to give, and its span: the rest of today, or tomorrow from mid-afternoon."""
	local = time.localtime(now)
	next_midnight = time.mktime((local.tm_year, local.tm_mon, local.tm_mday + 1, 0, 0, 0, 0, 0, -1))
	if local.tm_hour < TOMORROW_FROM:
		return "today", (now - 3600, next_midnight)
	return "tomorrow", (next_midnight, time.mktime((local.tm_year, local.tm_mon, local.tm_mday + 2, 0, 0, 0, 0, 0, -1)))


def _daytime(now):
	"""Only used if the forecast doesn't say: a rough guess from the clock."""
	return 8 <= time.localtime(now).tm_hour < 17


def _utc(stamp):
	return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
