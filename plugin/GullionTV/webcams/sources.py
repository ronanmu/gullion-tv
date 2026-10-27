# -*- coding: utf-8 -*-
"""Turn webcams.yaml entries into playable streams, with a picture and a status.

Everything that touches the network goes through a fetcher(url, binary=False)
function (fetch by default), so the page parsing can be checked offline.
"""
import hashlib
import json
import os
import re
import time

USER_AGENT = "Mozilla/5.0 (GullionTV; enigma2)"
THUMB_DIR = "/tmp/gulliontv/thumbs"
MAX_PAGE = 2 * 1024 * 1024

CHECKING, LIVE, OFFLINE, BROKEN, READY = "checking", "live", "offline", "broken", "ready"
SOURCE_LABELS = {"mcn": "mcn.live", "churchservices": "churchservices.tv", "stream": "Internet stream", "playlist": "Internet stream"}


class Webcam(object):
	def __init__(self, entry, name=None, url=None, image=None, group=None):
		self.entry = entry
		self.name = name or entry.name
		self.url = url or entry.url
		self.kind = entry.kind if url is None else "stream"
		self.image = image or entry.image
		self.group = group or entry.group
		self.player = entry.player
		self.stream = self.url if self.kind == "stream" else None
		self.status = CHECKING
		self.detail = ""
		self.thumbnail = None  # local file, once downloaded

	@property
	def source_label(self):
		return SOURCE_LABELS.get(self.entry.kind, "Internet stream")

	def service_ref(self):
		"""An enigma2 reference that plays the stream through the media framework."""
		return "%d:0:1:0:0:0:0:0:0:0:%s:%s" % (self.player, self.stream.replace(":", "%3a"), self.name.replace(":", " "))


# Fetching

def fetch(url, binary=False, timeout=8):
	try:
		from urllib2 import Request, urlopen, URLError
	except ImportError:
		from urllib.request import Request, urlopen
		from urllib.error import URLError
	request = Request(url, headers={"User-Agent": USER_AGENT})
	try:
		response = urlopen(request, timeout=timeout)
	except URLError as error:
		if "CERTIFICATE" not in str(error).upper():
			raise
		# Some boxes ship an out-of-date certificate store; these are public pages.
		import ssl
		response = urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
	data = response.read(MAX_PAGE)
	if binary or str is bytes:
		return data
	return data.decode("utf-8", "replace")


# Page parsing

_M3U8 = r"""https?://[^"'\s<>]+?\.m3u8[^"'\s<>]*"""


def parse_mcn(page):
	"""(stream, image) from an mcn.live camera page."""
	match = re.search(r"""<source[^>]+src=["'](%s)["']""" % _M3U8, page) or re.search("(%s)" % _M3U8, page)
	image = re.search(r"""(https?://[^"'\s]+/ProfileImages/[^"'\s]+\.(?:jpe?g|png))""", page, re.I)
	return (match and match.group(1)), (image and image.group(1))


def parse_churchservices(page):
	"""(stream, image, schedule) from a churchservices.tv church page.

	schedule is [(start, end, title)] for upcoming public services, soonest first.
	"""
	match = re.search(r"""data-src=["'](%s)["']""" % _M3U8, page) or re.search(r"(https?://[^\"'\s]*wowza[^\"'\s]*\.m3u8)", page)
	image = re.search(r"""<img[^>]+src=["']([^"']+)["'][^>]*class=["'][^"']*church-image""", page)
	titles = {}
	for row in re.finditer(r'schedule-(\d+)[^>]*>.*?playlist-title">.*?</span>\s*-\s*([^<]+?)\s*</div>', page, re.S):
		titles[row.group(1)] = _html_text(row.group(2))
	schedule = []
	found = re.search(r"todays_schedules\s*=\s*'(\[.*?\])'", page)
	if found:
		try:
			for item in json.loads(found.group(1)):
				if item.get("password"):
					continue
				schedule.append((int(item["start_time"]), int(item["end_time"]), titles.get(str(item["id"]), "Service")))
		except (ValueError, KeyError, TypeError):
			schedule = []
	schedule.sort()
	return (match and match.group(1)), (image and image.group(1)), schedule


def parse_playlist(text, base_url=""):
	"""[(name, url, logo, group)] from an M3U list of cameras."""
	cameras = []
	name = logo = group = None
	for line in text.splitlines():
		line = line.strip()
		if line.startswith("#EXTINF"):
			name = line.split(",", 1)[1].strip() if "," in line else None
			logo = _attribute(line, "tvg-logo")
			group = _attribute(line, "group-title")
		elif line and not line.startswith("#"):
			cameras.append((name or "Camera %d" % (len(cameras) + 1), _join(base_url, line), logo, group))
			name = logo = group = None
	return cameras


def hls_is_live(text):
	return "#EXTM3U" in text and ("#EXT-X-STREAM-INF" in text or "#EXTINF" in text)


def describe_schedule(schedule, now):
	"""'Daily Mass on now', 'Daily Mass today 18:00', 'tomorrow 10:00', 'Thu 10:00'."""
	for start, end, title in schedule:
		if start <= now < end:
			return "%s on now" % title
		if start > now:
			return "%s %s" % (title, _when(start, now))
	return ""


def status_line(webcam):
	"""The one line under a webcam's name."""
	words = {
		CHECKING: "Checking...",
		LIVE: "Live now",
		OFFLINE: "Not live right now",
		BROKEN: "Can't reach this camera",
		READY: "Ready to watch",
	}[webcam.status]
	if webcam.detail and webcam.status in (LIVE, OFFLINE):
		return "%s  ·  %s" % (words, webcam.detail)
	return words


# Checking

def expand(entries, fetcher=None):
	"""Webcams from config entries; playlist entries become one webcam per camera."""
	fetcher = fetcher or fetch
	webcams = []
	for entry in entries:
		if entry.kind != "playlist":
			webcams.append(Webcam(entry))
			continue
		try:
			cameras = parse_playlist(_text(fetcher(entry.url)), entry.url)
		except Exception:
			cameras = []
		if not cameras:
			broken = Webcam(entry)
			broken.status = BROKEN
			webcams.append(broken)
		for name, url, logo, group in cameras:
			webcams.append(Webcam(entry, name=name, url=url, image=logo, group=group))
	return webcams


def check(webcam, fetcher=None, now=None):
	"""Find the stream and whether it's live. Updates the webcam in place."""
	fetcher = fetcher or fetch
	now = time.time() if now is None else now
	try:
		if webcam.kind == "mcn":
			webcam.stream, found_image = parse_mcn(_text(fetcher(webcam.url)))
			webcam.image = webcam.image or found_image
		elif webcam.kind == "churchservices":
			webcam.stream, found_image, schedule = parse_churchservices(_text(fetcher(webcam.url)))
			webcam.image = webcam.image or found_image
			webcam.detail = describe_schedule(schedule, now)
	except Exception:
		webcam.status = BROKEN
		return webcam
	if not webcam.stream:
		webcam.status = BROKEN
		return webcam
	if not webcam.stream.lower().split("?")[0].endswith(".m3u8"):
		webcam.status = READY  # RTSP, MP4 and the like: nothing cheap to check
		return webcam
	try:
		webcam.status = LIVE if hls_is_live(_text(fetcher(webcam.stream))) else OFFLINE
	except Exception:
		webcam.status = OFFLINE
	return webcam


def download_thumbnail(webcam, fetcher=None, folder=None):
	"""Fetch the webcam's picture to a local file. Local paths are used as they are."""
	fetcher = fetcher or fetch
	folder = folder or THUMB_DIR
	if not webcam.image:
		return None
	if not webcam.image.startswith(("http://", "https://")):
		webcam.thumbnail = webcam.image if os.path.isfile(webcam.image) else None
		return webcam.thumbnail
	webcam.thumbnail = download(webcam.image, folder, fetcher)
	return webcam.thumbnail


def download(url, folder, fetcher=None):
	"""Save a picture from the web into folder, once. Returns the local path or None."""
	fetcher = fetcher or fetch
	extension = ".png" if url.lower().split("?")[0].endswith(".png") else ".jpg"
	path = os.path.join(folder, hashlib.md5(url.encode("utf-8") if not isinstance(url, bytes) else url).hexdigest() + extension)
	if not os.path.isfile(path):
		try:
			data = fetcher(url, binary=True)
			if not os.path.isdir(folder):
				os.makedirs(folder)
			with open(path, "wb") as handle:
				handle.write(data)
		except Exception:
			return None
	return path


# Helpers

def _text(data):
	if isinstance(data, bytes) and str is not bytes:
		return data.decode("utf-8", "replace")
	return data


def _html_text(value):
	return re.sub(r"\s+", " ", value.replace("&amp;", "&").replace("&#039;", "'").replace("&#39;", "'")).strip()


def _attribute(line, name):
	found = re.search(r'%s="([^"]*)"' % name, line)
	return found and found.group(1) or None


def _join(base, url):
	if re.match(r"^[a-z]+://", url, re.I) or not base:
		return url
	return base.rsplit("/", 1)[0] + "/" + url


def _when(start, now):
	day = time.localtime(start)
	clock = time.strftime("%H:%M", day)
	days = (_midnight(start) - _midnight(now)) // 86400
	if days == 0:
		return "today %s" % clock
	if days == 1:
		return "tomorrow %s" % clock
	if days < 7:
		return "%s %s" % (time.strftime("%a", day), clock)
	return "%d %s %s" % (day.tm_mday, time.strftime("%b", day), clock)


def _midnight(timestamp):
	day = time.localtime(timestamp)
	return int(time.mktime((day.tm_year, day.tm_mon, day.tm_mday, 0, 0, 0, 0, 0, -1)))
