# -*- coding: utf-8 -*-
"""A small Plex client: just what Gullion TV needs, for Python 2.7 on the box.

Every Plex address it uses is in the ENDPOINTS table, so a change on Plex's
side is a change here. All requests go through a request function
(request(method, url, headers) -> parsed JSON) so it can be checked offline.
"""
import json
import os
import uuid

try:
	from urllib import urlencode
except ImportError:
	from urllib.parse import urlencode

from ..webcams import sources

PRODUCT = "Gullion TV"
VERSION = "1.0"
SETTINGS_PATH = "/etc/enigma2/gulliontv/plex.json"
LINK_URL = "plex.tv/link"
PLEX_TV = "https://plex.tv"
MOVIE, SHOW = "movie", "show"
DEFAULT_REMOTE_KBPS = 8000

ENDPOINTS = {
	"pins": PLEX_TV + "/api/v2/pins",
	"pin": PLEX_TV + "/api/v2/pins/%s",
	"home_users": PLEX_TV + "/api/v2/home/users",
	"switch_user": PLEX_TV + "/api/v2/home/users/%s/switch",
	"resources": PLEX_TV + "/api/v2/resources?includeHttps=1&includeRelay=1",
	"identity": "/identity",
	"sections": "/library/sections",
	"continue_watching": "/hubs/continueWatching/items",
	"on_deck": "/library/onDeck",
	"recently_added": "/library/sections/%s/recentlyAdded",
	"library": "/library/sections/%s/all",
	"photo": "/photo/:/transcode",
}


class PlexError(Exception):
	pass


# Settings

def load_settings(path=SETTINGS_PATH):
	try:
		with open(path) as handle:
			settings = json.load(handle)
	except (IOError, OSError, ValueError):
		settings = {}
	settings.setdefault("client_id", str(uuid.uuid4()))
	settings.setdefault("remote_kbps", DEFAULT_REMOTE_KBPS)
	settings.setdefault("subtitles", False)
	settings.setdefault("sections", [])
	return settings


def save_settings(settings, path=SETTINGS_PATH):
	"""Written whole and readable only by root: it holds the Plex tokens."""
	folder = os.path.dirname(path)
	if not os.path.isdir(folder):
		os.makedirs(folder)
	temporary = path + ".new"
	descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
	with os.fdopen(descriptor, "w") as handle:
		json.dump(settings, handle, indent=1, sort_keys=True)
	os.rename(temporary, path)


def is_configured(settings):
	return bool(settings.get("user_token") and settings.get("server") and settings.get("sections"))


# Talking to Plex

def http_request(method, url, headers, timeout=10):
	try:
		from urllib2 import Request, urlopen, HTTPError, URLError
	except ImportError:
		from urllib.request import Request, urlopen
		from urllib.error import HTTPError, URLError
	request = Request(url, data=b"" if method == "POST" else None, headers=headers)
	request.get_method = lambda: method
	try:
		response = urlopen(request, timeout=timeout)
	except HTTPError as error:
		raise PlexError("Plex said %s" % error.code)
	except URLError as error:
		if "CERTIFICATE" not in str(error).upper():
			raise PlexError("Can't reach Plex")
		import ssl
		response = urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
	body = response.read()
	if not body:
		return {}
	try:
		return json.loads(sources._text(body))
	except ValueError:
		raise PlexError("Plex sent something unexpected")


class Client(object):
	def __init__(self, settings, request=None):
		self.settings = settings
		self.request = request or http_request

	def headers(self, token=None):
		headers = {
			"Accept": "application/json",
			"X-Plex-Product": PRODUCT,
			"X-Plex-Version": VERSION,
			"X-Plex-Client-Identifier": self.settings["client_id"],
			"X-Plex-Platform": "Enigma2",
			"X-Plex-Device": "Formuler F1",
			"X-Plex-Device-Name": PRODUCT,
		}
		if token:
			headers["X-Plex-Token"] = token
		return headers

	# Linking an account

	def create_pin(self):
		"""(pin id, 4-character code to enter at plex.tv/link)."""
		reply = self.request("POST", ENDPOINTS["pins"], self.headers())
		return reply["id"], reply["code"]

	def check_pin(self, pin_id):
		"""The account token once the code has been entered, else None."""
		reply = self.request("GET", ENDPOINTS["pin"] % pin_id, self.headers())
		return reply.get("authToken") or None

	def home_users(self, account_token):
		"""[{id, uuid, title, admin, protected}] in the account's Plex Home."""
		reply = self.request("GET", ENDPOINTS["home_users"], self.headers(account_token))
		users = reply.get("users", reply) if isinstance(reply, dict) else reply
		return [{"id": user.get("id"), "uuid": user.get("uuid"), "title": _native(user.get("title") or user.get("username") or "Plex user"),
			"admin": bool(user.get("admin")), "protected": bool(user.get("protected"))} for user in users or []]

	def switch_user(self, account_token, user, pin=None):
		"""The chosen Home user's own token."""
		url = ENDPOINTS["switch_user"] % user["uuid"]
		if pin:
			url += "?" + urlencode({"pin": pin})
		reply = self.request("POST", url, self.headers(account_token))
		token = reply.get("authToken") or reply.get("authenticationToken")
		if not token:
			raise PlexError("Plex didn't accept that user")
		return token

	def servers(self, user_token):
		"""Servers the user can reach, each with its connections."""
		reply = self.request("GET", ENDPOINTS["resources"], self.headers(user_token))
		servers = []
		for resource in reply if isinstance(reply, list) else []:
			if "server" not in (resource.get("provides") or ""):
				continue
			servers.append({
				"name": _native(resource.get("name") or "Plex server"),
				"id": resource.get("clientIdentifier"),
				"token": resource.get("accessToken") or user_token,
				"connections": [{"uri": c["uri"], "local": bool(c.get("local")), "relay": bool(c.get("relay"))}
					for c in resource.get("connections") or [] if c.get("uri")],
			})
		return servers

	# Finding the best way to the server

	def connect(self, server=None):
		"""Try the last address that worked, then local, then remote, relay last.
		Returns the working connection and remembers it in the settings."""
		server = server or self.settings["server"]
		last = self.settings.get("last_uri")
		ordered = sorted(server["connections"], key=lambda c: (c["uri"] != last, c["relay"], not c["local"]))
		for connection in ordered:
			try:
				self.request("GET", connection["uri"] + ENDPOINTS["identity"], self.headers(server["token"]), timeout=3)
			except Exception:
				continue
			self.settings["last_uri"] = connection["uri"]
			return connection
		raise PlexError("Can't reach the Plex server")

	@staticmethod
	def describe(connection):
		if connection["relay"]:
			return "remote (relay)"
		return "local" if connection["local"] else "remote (direct)"

	def is_remote(self):
		server = self.settings.get("server") or {}
		for connection in server.get("connections", []):
			if connection["uri"] == self.settings.get("last_uri"):
				return not connection["local"]
		return True

	# Reading the libraries

	def get(self, path, **params):
		server = self.settings["server"]
		uri = self.settings.get("last_uri") or self.connect()["uri"]
		url = uri + path
		if params:
			url += ("&" if "?" in url else "?") + urlencode(params)
		reply = self.request("GET", url, self.headers(server["token"]))
		return reply.get("MediaContainer", {}) if isinstance(reply, dict) else {}

	def sections(self):
		"""Film and TV libraries only: [{key, title, type}]."""
		return [{"key": str(section["key"]), "title": _native(section.get("title", "")), "type": section["type"]}
			for section in self.get(ENDPOINTS["sections"]).get("Directory", []) if section.get("type") in (MOVIE, SHOW)]

	def continue_watching(self, limit=20):
		try:
			items = self.get(ENDPOINTS["continue_watching"]).get("Metadata", [])
		except PlexError:
			items = self.get(ENDPOINTS["on_deck"]).get("Metadata", [])  # older servers
		return self._chosen([Item(item) for item in items])[:limit]

	def recently_added(self, limit=20):
		items = []
		for key in self.settings["sections"]:
			container = self.get(ENDPOINTS["recently_added"] % key, **{"X-Plex-Container-Start": 0, "X-Plex-Container-Size": limit})
			items += [Item(item) for item in container.get("Metadata", [])]
		items.sort(key=lambda item: item.added_at, reverse=True)
		return items[:limit]

	def library(self, section, newest_first=False, unwatched_only=False, start=0, size=16):
		"""One page of a film or TV library: (items, how many there are in all)."""
		params = {"sort": "addedAt:desc" if newest_first else "titleSort:asc",
			"X-Plex-Container-Start": start, "X-Plex-Container-Size": size}
		if unwatched_only:
			params["unwatched"] = 1
		container = self.get(ENDPOINTS["library"] % section, **params)
		items = [Item(item) for item in container.get("Metadata", [])]
		return items, int(container.get("totalSize") or container.get("size") or len(items))

	def _chosen(self, items):
		"""Only items from the libraries Tech Support picked."""
		keys = set(self.settings["sections"])
		return [item for item in items if not item.section or item.section in keys]

	def image_url(self, path, width, height):
		"""The server scales pictures down before sending them, which saves the F1 the work."""
		if not path:
			return None
		uri = self.settings.get("last_uri")
		if not uri:
			return None
		# The server scales the picture down for the tile. Backgrounds and episode
		# stills are 16:9 like the tiles, so they fill them; posters are portrait.
		return "%s%s?%s" % (uri, ENDPOINTS["photo"], urlencode({
			"width": width, "height": height, "minSize": 1, "upscale": 1,
			"url": path, "X-Plex-Token": self.settings["server"]["token"],
		}))


class Item(object):
	"""A film, a TV programme or an episode, from the server's metadata."""

	def __init__(self, data):
		self.key = str(data.get("ratingKey", ""))
		self.kind = data.get("type", "")
		self.title = _native(data.get("title", ""))
		self.show = _native(data.get("grandparentTitle") or data.get("parentTitle") or "")
		self.season = data.get("parentIndex")
		self.episode = data.get("index")
		self.year = data.get("year")
		self.summary = _native(data.get("summary", ""))
		self.duration = int(data.get("duration") or 0) // 1000
		self.position = int(data.get("viewOffset") or 0) // 1000
		self.watched = bool(data.get("viewCount"))
		self.added_at = int(data.get("addedAt") or 0)
		self.viewed_at = int(data.get("lastViewedAt") or 0)
		self.section = str(data.get("librarySectionID", "")) or None
		# Landscape pictures suit the Watch again rows: an episode's own still, else
		# the programme's background; a film's background. Posters are portrait.
		if self.kind == "episode":
			self.landscape = data.get("thumb") or data.get("grandparentArt") or data.get("art")
			self.poster = data.get("grandparentThumb") or data.get("parentThumb")
		else:
			self.landscape = data.get("art")
			self.poster = data.get("thumb")
		self.episodes = int(data.get("leafCount") or 0)
		self.episodes_watched = int(data.get("viewedLeafCount") or 0)
		self.seasons = int(data.get("childCount") or 0)

	@property
	def heading(self):
		return self.show if self.kind == "episode" and self.show else self.title

	@property
	def subheading(self):
		if self.kind == "episode":
			parts = []
			if self.season is not None and self.episode is not None:
				parts.append("S%s E%s" % (self.season, self.episode))
			parts.append(self.title)
			return "  ·  ".join(parts)
		if self.kind == SHOW and self.seasons:
			return "%d series" % self.seasons if self.seasons > 1 else (str(self.year) if self.year else "1 series")
		return str(self.year) if self.year else ("TV programme" if self.kind == SHOW else "Film")

	@property
	def to_watch(self):
		"""Episodes of a programme not seen yet."""
		return max(0, self.episodes - self.episodes_watched)

	@property
	def progress(self):
		if not self.position or not self.duration:
			return None
		return min(1.0, float(self.position) / self.duration)


def _native(text):
	if str is bytes and isinstance(text, type(u"")):
		return text.encode("utf-8")
	return text
