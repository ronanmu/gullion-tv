# -*- coding: utf-8 -*-
"""Plain-language facts about a channel, worked out from its service reference.

A reference looks like 1:0:19:SID:TSID:ONID:NAMESPACE:0:0:0: — field 2 is the
service type and the top half of the namespace says where the signal comes from.
"""
import re

# DVB service types that carry HD video: MPEG-2 HD, H.264 HD, HEVC.
HD_TYPES = (0x11, 0x19, 0x1F, 0x20)
STREAM_TYPES = ("4097", "5001", "5002", "8193")
TERRESTRIAL = 0xEEEE
CABLE = 0xFFFF


def key(ref):
	"""The part of a reference that identifies the channel, without name or URL."""
	return ":".join((ref or "").split(":")[:10])


def delivery(ref):
	parts = (ref or "").split(":")
	if len(parts) < 10:
		return ""
	if parts[0] in STREAM_TYPES or "%3a//" in ref.lower():
		return "Internet stream"
	try:
		position = int(parts[6], 16) >> 16
	except ValueError:
		return ""
	if position == TERRESTRIAL:
		return "Terrestrial"
	if position == CABLE:
		return "Cable"
	if position > 1800:
		return "Satellite  ·  %.1f°W" % ((3600 - position) / 10.0)
	return "Satellite  ·  %.1f°E" % (position / 10.0)


def is_uhd(video_height=-1):
	return video_height >= 1800


def is_hd(ref, video_height=-1):
	"""Trust the decoded picture height once it's known, else the service type."""
	if video_height and video_height > 0:
		return video_height >= 720
	try:
		return int((ref or "").split(":")[2], 16) in HD_TYPES
	except (IndexError, ValueError):
		return False


def remaining(seconds):
	minutes = max(0, int(seconds) // 60)
	if minutes >= 60:
		return "%d hr %d min left" % (minutes // 60, minutes % 60)
	return "%d min left" % minutes


def channel_numbers(lists):
	"""{channel key: number} from epg.channel_lists()."""
	numbers = {}
	for bouquet, name, channels in lists:
		for channel in channels:
			numbers.setdefault(key(channel.ref), channel.number)
	return numbers


# The access codes broadcasters put at the end of a description: "... (HD, S, AD, R)"
# on Saorview, "... [S,AD] [HD]" on Freesat.
CODES = ("HD", "UHD", "W", "S", "AD", "SL", "R")
# The ones shown as icons, and the icon for each. HD comes from the channel itself.
BADGES = ("S", "AD", "SL", "R")
BADGE_ICONS = {"S": "subtitles", "AD": "audio_description", "SL": "sign_language", "R": "repeat"}
_GROUP_AT_END = re.compile(r"\s*[\(\[]\s*([A-Z]{1,3}(?:\s*,\s*[A-Z]{1,3})*)\s*[\)\]]\s*$")


def split_codes(text):
	"""(description without the codes, [codes]). Brackets with anything else, like (USA), are kept."""
	text = text or ""
	codes = []
	while True:
		match = _GROUP_AT_END.search(text)
		if not match:
			break
		group = [code.strip() for code in match.group(1).split(",")]
		if not all(code in CODES for code in group):
			break
		codes = group + codes
		text = text[:match.start()].rstrip()
	return text, codes


def badges(text):
	"""The access badges a description ends with, in its own order: ["S", "AD"]."""
	return [code for code in split_codes(text)[1] if code in BADGES]


def delivery_kind(ref):
	"""satellite, terrestrial, cable or internet, for the matching icon; "" if unknown."""
	text = delivery(ref)
	if text.startswith("Satellite"):
		return "satellite"
	return {"Terrestrial": "terrestrial", "Cable": "cable", "Internet stream": "internet"}.get(text, "")


def icon_row(ref, video_height, description):
	"""The icons for a programme, left to right: its access codes, then hd or uhd when the
	picture is (nothing for SD), then how the channel arrives."""
	names = [BADGE_ICONS[code] for code in badges(description)]
	if is_uhd(video_height):
		names.append("uhd")
	elif is_hd(ref, video_height):
		names.append("hd")
	kind = delivery_kind(ref)
	if kind:
		names.append(kind)
	return names


_POLARISATION = {0: "H", 1: "V", 2: "L", 3: "R"}


def _percent(value):
	return "%d%%" % round(value * 100 / 65535.0) if value is not None and value >= 0 else ""


def signal_details(status, transponder):
	"""[(label, value)] from a tuner's frontend status and transponder data, for the INFO
	panel. Anything the tuner doesn't report is left out."""
	status, transponder = status or {}, transponder or {}
	lines = []
	quality = _percent(status.get("tuner_signal_quality"))
	if quality:
		lines.append(("Quality", quality))
	snr_db = status.get("tuner_signal_quality_db")
	if snr_db is not None and snr_db > 0:
		lines.append(("SNR", "%.1f dB" % (snr_db / 100.0)))
	power = _percent(status.get("tuner_signal_power"))
	if power:
		lines.append(("Power", power))
	errors = status.get("tuner_bit_error_rate")
	if errors is not None and errors >= 0:
		lines.append(("Errors", str(errors)))
	tuner = status.get("tuner_number", transponder.get("tuner_number"))
	if tuner is not None and tuner >= 0:
		lines.append(("Tuner", chr(ord("A") + int(tuner))))
	kind = str(transponder.get("tuner_type", ""))
	frequency = transponder.get("frequency")
	if frequency:
		if "S" in kind and "T" not in kind:
			# Satellite: kHz, with polarisation and symbol rate, as Freesat lists them.
			text = "%d %s" % (round(frequency / 1000.0), _POLARISATION.get(transponder.get("polarization"), ""))
			lines.append(("Frequency", text.strip()))
			symbol_rate = transponder.get("symbol_rate")
			if symbol_rate:
				lines.append(("Symbol rate", "%d" % round(symbol_rate / 1000.0)))
		else:
			# Terrestrial frequencies come in Hz, cable in kHz.
			lines.append(("Frequency", "%d MHz" % round(frequency / (1000000.0 if frequency > 10000000 else 1000.0))))
	return lines
