# -*- coding: utf-8 -*-
"""Made-up Plex replies and recordings for offline checks and renders.

FakePlex answers like plex.tv and a Plex server would. Set where = "home" for
a server on the same network, or "away" once it's somewhere else.
"""
import os
import struct

try:
	from urllib.parse import parse_qs, urlparse
except ImportError:
	from urlparse import parse_qs, urlparse

import sample_epg

NOW = int(sample_epg.NOW)
HOUR, DAY = 3600, 86400
LOCAL = "https://10-0-0-5.abc123.plex.direct:32400"
REMOTE = "https://81-2-3-4.abc123.plex.direct:32400"
RELAY = "https://81-2-3-4.abc123.plex.direct:8443"


class Refused(Exception):
	pass


class FakePlex(object):
	def __init__(self, where="home"):
		self.where = where
		self.pin_checks = 0
		self.calls = []

	def __call__(self, method, url, headers, timeout=10):
		from GullionTV.plex import client as plex
		self.calls.append((method, url, headers.get("X-Plex-Token")))
		path = url.split("?")[0]
		if path.endswith("/api/v2/pins") and method == "POST":
			return {"id": 111, "code": "GT4K"}
		if path.endswith("/api/v2/pins/111"):
			self.pin_checks += 1
			return {"authToken": "account-token" if self.pin_checks > 1 else None}
		if path.endswith("/api/v2/home/users"):
			return {"users": [
				{"id": 1, "uuid": "u-owner", "title": "Alex", "admin": True, "protected": False},
				{"id": 2, "uuid": "u-sam", "title": "Sam", "admin": False, "protected": True},
			]}
		if "/home/users/" in path and path.endswith("/switch"):
			if "u-sam" in path and "pin=1234" not in url:
				raise plex.PlexError("Plex said 401")
			return {"authToken": "sam-token" if "u-sam" in path else "owner-token"}
		if path.endswith("/api/v2/resources"):
			return [
				{"name": "Gullion Plex", "clientIdentifier": "srv1", "provides": "server", "accessToken": "server-token",
					"connections": [
						{"uri": RELAY, "local": False, "relay": True},
						{"uri": REMOTE, "local": False, "relay": False},
						{"uri": LOCAL, "local": True, "relay": False},
					]},
				{"name": "Alex's phone", "clientIdentifier": "phone", "provides": "player,controller", "connections": []},
			]
		if path.endswith("/identity"):
			if url.startswith(LOCAL) and self.where != "home":
				raise plex.PlexError("Can't reach Plex")
			return {"MediaContainer": {"machineIdentifier": "srv1"}}
		if path.endswith("/library/sections"):
			return {"MediaContainer": {"Directory": [
				{"key": "1", "title": "Films", "type": "movie"},
				{"key": "2", "title": "TV Programmes", "type": "show"},
				{"key": "3", "title": "Music", "type": "artist"},
			]}}
		if path.endswith("/hubs/continueWatching/items"):
			return {"MediaContainer": {"Metadata": CONTINUE}}
		if path.endswith("/library/sections/1/recentlyAdded"):
			return {"MediaContainer": {"Metadata": RECENT_FILMS}}
		if path.endswith("/library/sections/2/recentlyAdded"):
			return {"MediaContainer": {"Metadata": RECENT_TV}}
		for key, items in (("1", LIBRARY_FILMS), ("2", LIBRARY_TV)):
			if path.endswith("/library/sections/%s/all" % key):
				return {"MediaContainer": self.page(items, url)}
		raise plex.PlexError("Plex said 404")

	@staticmethod
	def page(items, url):
		"""Sort, filter and slice a library the way the server does."""
		query = dict((key, values[0]) for key, values in parse_qs(urlparse(url).query).items())
		if query.get("sort", "").startswith("addedAt"):
			items = sorted(items, key=lambda item: item["addedAt"], reverse=True)
		else:
			items = sorted(items, key=lambda item: item["title"].replace("The ", "", 1).lower())
		if query.get("unwatched") == "1":
			items = [item for item in items if not item.get("viewCount") and item.get("viewedLeafCount", 0) < item.get("leafCount", 1)]
		start, size = int(query.get("X-Plex-Container-Start", 0)), int(query.get("X-Plex-Container-Size", 50))
		return {"Metadata": items[start:start + size], "size": len(items[start:start + size]), "totalSize": len(items)}


def episode(key, show, season, number, title, offset_minutes=0, viewed_hours_ago=0, added_days_ago=0):
	return {"ratingKey": key, "type": "episode", "title": title, "grandparentTitle": show, "parentIndex": season, "index": number,
		"duration": 60 * 60000, "viewOffset": offset_minutes * 60000, "lastViewedAt": NOW - viewed_hours_ago * HOUR,
		"addedAt": NOW - added_days_ago * DAY, "librarySectionID": 2, "grandparentThumb": "/library/metadata/%s/thumb" % show.replace(" ", ""),
		"thumb": "/library/metadata/%s/still" % key, "grandparentArt": "/library/metadata/%s/art" % show.replace(" ", "")}


def film(key, title, year, minutes, offset_minutes=0, viewed_hours_ago=0, added_days_ago=0):
	return {"ratingKey": key, "type": "movie", "title": title, "year": year, "duration": minutes * 60000,
		"viewOffset": offset_minutes * 60000, "lastViewedAt": NOW - viewed_hours_ago * HOUR,
		"addedAt": NOW - added_days_ago * DAY, "librarySectionID": 1, "thumb": "/library/metadata/%s/thumb" % key,
		"art": "/library/metadata/%s/art" % key}


CONTINUE = [
	episode("501", "Line of Duty", 6, 3, "Episode 3", offset_minutes=22, viewed_hours_ago=2),
	film("601", "The Commitments", 1991, 118, offset_minutes=74, viewed_hours_ago=26),
	film("699", "Something from Music", 2001, 50, offset_minutes=5, viewed_hours_ago=1),
]
CONTINUE[2]["librarySectionID"] = 3  # not a chosen library, so it's left out
RECENT_FILMS = [
	film("602", "The Banshees of Inisherin", 2022, 114, added_days_ago=1),
	film("603", "Brooklyn", 2015, 117, added_days_ago=4),
]
RECENT_FILMS[1].pop("art")  # Brooklyn has only a poster
RECENT_TV = [
	episode("502", "Derry Girls", 3, 1, "The Night Before", added_days_ago=2),
	episode("503", "Normal People", 1, 1, "Episode 1", added_days_ago=6),
]


def configured_settings():
	"""Settings as they'd be once Tech Support has finished setup at home."""
	return {
		"client_id": "test-client", "account_token": "account-token", "user": {"title": "Sam", "uuid": "u-sam"},
		"user_token": "sam-token", "remote_kbps": 8000, "subtitles": False, "sections": ["1", "2"],
		"section_names": ["Films", "TV Programmes"], "last_uri": LOCAL,
		"server": {"name": "Gullion Plex", "id": "srv1", "token": "server-token", "connections": [
			{"uri": RELAY, "local": False, "relay": True},
			{"uri": REMOTE, "local": False, "relay": False},
			{"uri": LOCAL, "local": True, "relay": False},
		]},
	}


RECORDINGS = [
	# (file name, title, channel ref, description, hours ago, minutes long, minutes watched)
	("20261027 2000 - RTE One - Fair City.ts", "Fair City", "1:0:19:1:1:1:EEEE0000:0:0:0:", "Paul worries about the cafe.", 0.5, 30, 12),
	("20261026 2100 - BBC One NI - MasterChef.ts", "MasterChef", "1:0:19:5:1:1:11A0000:0:0:0:", "The quarter-final.", 22.7, 60, 0),
	("20261025 1930 - RTE One - Nationwide.ts", "Nationwide", "1:0:19:1:1:1:EEEE0000:0:0:0:", "A bakery in Dundalk.", 48.2, 30, 30),
	("20261024 2030 - TG4 - Ros na Run.ts", "Ros na Rún", "1:0:19:4:1:1:EEEE0000:0:0:0:", "", 71, 40, 0),
	("20261020 2100 - Channel 4 - Grand Designs.ts", "Grand Designs", "1:0:19:8:1:1:11A0000:0:0:0:", "A house in a quarry.", 165, 60, 0),
	("20261018 2000 - BBC Two NI - Gardeners World.ts", "Gardeners' World", "1:0:19:6:1:1:11A0000:0:0:0:", "", 214, 30, 0),
]


def make_recordings(folder):
	"""Write .ts, .ts.meta and .ts.cuts files the way the box does."""
	if not os.path.isdir(folder):
		os.makedirs(folder)
	for name, title, ref, description, hours_ago, minutes, watched in RECORDINGS:
		path = os.path.join(folder, name)
		open(path, "wb").close()
		begin = NOW - int(hours_ago * HOUR)
		with open(path + ".meta", "wb") as handle:
			handle.write(("%s\n%s\n%s\n%d\n\n%d\n0\n" % (ref, title, description, begin, minutes * 60 * 90000)).encode("utf-8"))
		if watched:
			with open(path + ".cuts", "wb") as handle:
				handle.write(struct.pack(">QI", 0, 0) + struct.pack(">QI", watched * 60 * 90000, 3))
			os.utime(path + ".cuts", (begin + HOUR, begin + HOUR))
	return folder


FILM_TITLES = [
	("The Banshees of Inisherin", 2022), ("Brooklyn", 2015), ("The Commitments", 1991), ("Once", 2007),
	("The Quiet Girl", 2022), ("Belfast", 2021), ("In Bruges", 2008), ("The Guard", 2011), ("Calvary", 2014),
	("Philomena", 2013), ("Sing Street", 2016), ("The Wind That Shakes the Barley", 2006), ("Michael Collins", 1996),
	("My Left Foot", 1989), ("The Field", 1990), ("Waking Ned", 1998), ("The Snapper", 1993), ("Song of the Sea", 2014),
	("The Secret of Kells", 2009), ("Wolfwalkers", 2020), ("Room", 2015), ("Kneecap", 2024), ("An Cailin Ciuin", 2022),
	("The Magdalene Sisters", 2002), ("Hunger", 2008), ("Into the West", 1992), ("The Van", 1996), ("Intermission", 2003),
	("Garage", 2007), ("Small Things Like These", 2024), ("The Lobster", 2015), ("Adam and Paul", 2004),
	("Leap Year", 2010), ("P.S. I Love You", 2007), ("The Wonder", 2022), ("Ordinary Love", 2019),
]
SHOW_TITLES = [
	("Derry Girls", 3, 19, 19), ("Line of Duty", 6, 36, 34), ("Normal People", 1, 12, 0), ("Fair City", 1, 40, 12),
	("The Young Offenders", 3, 22, 22), ("Bad Sisters", 2, 18, 10), ("Mrs Brown's Boys", 3, 21, 21), ("Love/Hate", 5, 28, 0),
	("Father Ted", 3, 25, 25), ("Ballykissangel", 6, 58, 3), ("Hidden Assets", 1, 6, 6), ("The Fall", 3, 17, 17),
	("Blue Lights", 2, 12, 8), ("Kin", 2, 16, 0), ("Hope Street", 3, 30, 12), ("Can't Cope, Won't Cope", 2, 12, 12),
	("The Dry", 2, 16, 4), ("Holding", 1, 4, 0), ("Say Nothing", 1, 9, 0), ("Granite Harbour", 2, 6, 6),
]


def _library():
	films, shows = [], []
	for index, (title, year) in enumerate(FILM_TITLES):
		item = film(str(700 + index), title, year, 100 + index, added_days_ago=index * 3)
		item["viewCount"] = 1 if index % 4 == 2 else 0
		item["viewOffset"] = 35 * 60000 if index == 5 else 0
		films.append(item)
	for index, (title, seasons, episodes, watched) in enumerate(SHOW_TITLES):
		shows.append({"ratingKey": str(800 + index), "type": "show", "title": title, "childCount": seasons,
			"leafCount": episodes, "viewedLeafCount": watched, "year": 2000 + index, "addedAt": NOW - index * 5 * DAY,
			"librarySectionID": 2, "thumb": "/library/metadata/%d/thumb" % (800 + index)})
	return films, shows


LIBRARY_FILMS, LIBRARY_TV = _library()
