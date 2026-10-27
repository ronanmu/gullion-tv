"""Find the picon (channel logo) file for any channel, not just the one playing."""
import os

from . import serviceinfo

SEARCH_DIRS = (
	"/usr/share/enigma2/picon",
	"/media/hdd/picon",
	"/media/usb/picon",
	"/media/mmc/picon",
	"/picon",
)
_found = {}


def picon_path(ref):
	"""Path to the channel's picon, or None. Results are remembered per channel."""
	channel = serviceinfo.key(ref)
	if channel not in _found:
		_found[channel] = _system_lookup(channel) or _search(channel)
	return _found[channel]


def _system_lookup(channel):
	# OpenATV's own lookup also knows its configured picon folder and fallbacks.
	try:
		from Components.Renderer.Picon import getPiconName
		return getPiconName(channel) or None
	except Exception:
		return None


def _search(channel):
	parts = channel.split(":")
	names = ["_".join(parts).strip("_")]
	if len(parts) > 2 and parts[2] != "1":
		# Picon packs often only ship the SD (service type 1) file name.
		names.append("_".join(parts[:2] + ["1"] + parts[3:]).strip("_"))
	for folder in SEARCH_DIRS:
		for name in names:
			path = os.path.join(folder, name + ".png")
			if os.path.isfile(path):
				return path
	return None
