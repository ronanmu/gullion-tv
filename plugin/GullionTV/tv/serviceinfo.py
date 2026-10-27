# -*- coding: utf-8 -*-
"""Plain-language facts about a channel, worked out from its service reference.

A reference looks like 1:0:19:SID:TSID:ONID:NAMESPACE:0:0:0: — field 2 is the
service type and the top half of the namespace says where the signal comes from.
"""

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
