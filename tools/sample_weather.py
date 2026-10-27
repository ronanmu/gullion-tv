# -*- coding: utf-8 -*-
"""Made-up forecasts in the shape Met Éireann and Open-Meteo send them."""
import calendar
import json
import time

import sample_epg

NOW = sample_epg.NOW  # Tuesday 27 October 2026, 19:42


def _stamp(timestamp):
	return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


def met_eireann(now=NOW, hours=36, symbol="LightRain"):
	"""Hourly temperatures peaking at 14° at 3pm and 5° overnight, sunlight only by day,
	and the same weather symbol every hour."""
	hour = int(now) // 3600 * 3600
	blocks = []
	for i in range(hours):
		start = hour + i * 3600
		local = time.localtime(start).tm_hour
		temperature = 14 - abs(local - 15) * 0.6 if 7 <= local <= 21 else 5.0
		radiation = 120.0 if 8 <= local < 17 else 0.0
		blocks.append('<time datatype="forecast" from="%s" to="%s"><location altitude="74" latitude="54.0830" longitude="-6.4500">'
			'<temperature id="TTT" unit="celsius" value="%.1f"/><globalRadiation value="%.1f" unit="W/m^2"/></location></time>'
			% (_stamp(start), _stamp(start), temperature, radiation))
		blocks.append('<time datatype="forecast" from="%s" to="%s"><location altitude="74" latitude="54.0830" longitude="-6.4500">'
			'<precipitation unit="mm" value="0.4"/><symbol id="%s" number="9"/></location></time>'
			% (_stamp(start - 3600), _stamp(start), symbol))
	return ('<?xml version="1.0" encoding="UTF-8"?><weatherdata><product class="pointData">%s</product></weatherdata>'
		% "".join(blocks)).encode("utf-8")


def open_meteo(temperature=7.6, code=61, is_day=0, highs=(9.8, 13.6)):
	return json.dumps({"current": {"temperature_2m": temperature, "weather_code": code, "is_day": is_day},
		"daily": {"temperature_2m_max": list(highs), "temperature_2m_min": [4.1, 5.0], "weather_code": [61, 3]}})


def fetcher(met_up=True):
	def fetch(url, binary=False, timeout=8):
		if "met.ie" in url:
			if not met_up:
				raise IOError("Met Éireann can't be reached")
			return met_eireann()
		if "open-meteo" in url:
			return open_meteo()
		raise IOError("unexpected %s" % url)
	return fetch
