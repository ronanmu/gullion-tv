# -*- coding: utf-8 -*-
"""Tech Support's Plex setup: link the account, choose the Home user the TV
always uses, choose the server, and choose the film and TV libraries.

Reached from Plugins > Gullion TV > BLUE (Plex). The first run walks through
every step in order; afterwards each step can be changed on its own.
"""
from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from . import client as plex
from .. import theme
from ..ui import tiles
from ..ui.background import Background
from ..ui.pin import PinEntry
from ..ui.popups import GullionChoice
from ..ui import scale

MAX_ROWS = 7
QUALITY_STEPS = (2000, 4000, 8000, 12000, 20000, 0)  # kbps; 0 means original quality
LINK_SECONDS = 15 * 60


def quality_text(kbps):
	return "Original quality" if not kbps else "%d Mbps" % (kbps // 1000)


class OptionList(Screen):
	"""A list to pick from, in the Gullion TV style. Closes with the chosen key.

	With toggles (a set of keys), OK ticks and unticks, and the last row, Done,
	closes with the set."""

	skin = """
	<screen name="GullionOptionList" position="center,center" size="1100,820" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame_1100_820)s
		<widget name="heading" position="60,46" size="980,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		<widget name="detail" position="60,108" size="980,80" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		%(rows)s
		<widget name="hint" position="60,760" size="980,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"card": theme.POPUP, "border": theme.POPUP_BORDER, "frame_1100_820": theme.frame(1100, 820), "text": theme.TEXT, "muted": theme.TEXT_MUTED,
		"rows": "".join(
			'<widget name="row%d_bg" position="60,%d" size="980,64" backgroundColor="%s" zPosition="1" />'
			'<widget name="row%d" position="88,%d" size="760,64" font="Regular;32" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
			'<widget name="row%d_value" position="840,%d" size="176,64" font="Regular;28" halign="right" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
			% (i, 206 + i * 76, theme.POPUP, i, 206 + i * 76, theme.TEXT, i, 206 + i * 76, theme.TEXT_MUTED)
			for i in range(MAX_ROWS)),
	}

	skin = scale.skin(skin)

	def __init__(self, session, heading, options, detail="", toggles=None):
		"""options: [(label, key)] or [(label, key, value text)]"""
		Screen.__init__(self, session)
		self.setTitle(heading)
		self.toggles = set(toggles) if toggles is not None else None
		self.options = [option if len(option) == 3 else (option[0], option[1], "") for option in options]
		if self.toggles is not None:
			self.options.append(("Done", None, ""))
		self.selected = 0
		self.top = 0
		self["heading"] = Label(heading)
		self["detail"] = Label(detail)
		self["hint"] = Label("OK to tick or untick   ·   BACK when done" if self.toggles is not None else "OK to choose   ·   BACK to go back")
		for i in range(MAX_ROWS):
			self["row%d_bg" % i] = Label()
			self["row%d" % i] = Label()
			self["row%d_value" % i] = Label()
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
			"ok": self.ok,
			"cancel": self.cancel,
			"up": lambda: self.move(-1),
			"down": lambda: self.move(1),
		}, -1)
		self.onLayoutFinish.append(self.paint)

	def move(self, step):
		self.selected = max(0, min(len(self.options) - 1, self.selected + step))
		self.top = max(min(self.top, self.selected), self.selected - MAX_ROWS + 1)
		self.paint()

	def ok(self):
		label, key, value = self.options[self.selected]
		if self.toggles is None:
			self.close(key)
		elif key is None:
			self.close(self.toggles)
		else:
			self.toggles.symmetric_difference_update([key])
			self.paint()

	def cancel(self):
		self.close(self.toggles if self.toggles is not None else None)

	def paint(self):
		for i in range(MAX_ROWS):
			index = self.top + i
			present = index < len(self.options)
			label, key, value = self.options[index] if present else ("", None, "")
			if self.toggles is not None and key is not None:
				value = "On" if key in self.toggles else "Off"
			self["row%d" % i].setText(label)
			self["row%d_value" % i].setText(value)
			chosen = present and index == self.selected
			tiles.colour(self["row%d_bg" % i], background=theme.CARD_SELECTED if chosen else theme.POPUP)
			tiles.colour(self["row%d" % i], foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT)
			tiles.colour(self["row%d_value" % i], foreground=theme.TEXT_ON_SELECTED_MUTED if chosen else theme.TEXT_MUTED)


class PlexLink(Screen):
	"""Shows a code to enter at plex.tv/link and waits for it. Closes with the account token."""

	skin = """
	<screen name="GullionPlexLink" position="center,center" size="1100,620" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame_1100_620)s
		<eLabel text="Link a Plex account" position="60,46" size="980,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		<eLabel text="On a phone or computer, go to" position="60,124" size="980,40" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		<widget name="address" position="60,170" size="980,60" font="Regular;46" foregroundColor="%(accent)s" transparent="1" />
		<eLabel text="sign in, and enter this code:" position="60,244" size="980,40" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		<widget name="code" position="60,300" size="980,150" font="Regular;120" halign="center" valign="center" foregroundColor="%(on_light)s" backgroundColor="%(light)s" />
		<widget name="message" position="60,476" size="980,80" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		<eLabel text="BACK to cancel" position="60,566" size="980,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"card": theme.POPUP, "border": theme.POPUP_BORDER, "frame_1100_620": theme.frame(1100, 620), "text": theme.TEXT, "muted": theme.TEXT_MUTED,
		"accent": theme.ACCENT, "light": theme.CARD_SELECTED, "on_light": theme.TEXT_ON_SELECTED,
	}

	POLL_SECONDS = 3

	skin = scale.skin(skin)

	def __init__(self, session, client):
		Screen.__init__(self, session)
		self.setTitle("Link a Plex account")
		self.client = client
		self.pin_id = None
		self.waited = 0
		self.waiting = False
		self["address"] = Label(plex.LINK_URL)
		self["code"] = Label("....")
		self["message"] = Label("Getting a code from Plex...")
		self.background = Background()
		self.poll = eTimer()
		self.poll.callback.append(self.check)
		self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.leave, "ok": self.retry}, -1)
		self.onLayoutFinish.append(self.new_code)

	def new_code(self):
		self.waited = 0
		self.background.run(self.client.create_pin, self.got_code)

	def got_code(self, reply, error):
		if error is not None:
			self["message"].setText("Can't reach Plex. Check the box's internet connection, then press OK to try again.")
			return
		self.pin_id, code = reply
		self["code"].setText(code)
		self["message"].setText("Waiting for the code to be entered...")
		self.waiting = True
		self.poll.start(self.POLL_SECONDS * 1000, False)

	def check(self):
		self.waited += self.POLL_SECONDS
		if self.waited > LINK_SECONDS:
			self.poll.stop()
			self.waiting = False
			self["message"].setText("The code has run out. Press OK for a new one.")
			return
		self.background.run(lambda: self.client.check_pin(self.pin_id), self.checked)

	def checked(self, token, error):
		if token:
			self.poll.stop()
			self.close(token)

	def retry(self):
		if not self.waiting:
			self.new_code()

	def leave(self):
		self.poll.stop()
		self.background.stop()
		self.close(None)


class PlexSetup(Screen):
	"""What's set up, and the steps to change it."""

	skin = """
	<screen name="GullionPlexSetup" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="Plex" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<eLabel text="For Tech Support" position="1330,58" size="500,40" font="Regular;28" halign="right" foregroundColor="%(muted)s" transparent="1" />
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />
		%(facts)s
		%(rows)s
		<widget name="message" position="90,960" size="1740,40" font="Regular;28" foregroundColor="%(accent)s" transparent="1" />
		<eLabel text="OK to change   ·   BACK when done" position="90,1030" size="900,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER, "accent": theme.ACCENT,
		"facts": "".join(
			'<eLabel text="%s" position="90,%d" size="300,44" font="Regular;30" foregroundColor="%s" transparent="1" />'
			'<widget name="fact_%s" position="400,%d" size="1430,44" font="Regular;30" foregroundColor="%s" transparent="1" />'
			% (label, 170 + i * 56, theme.TEXT_MUTED, name, 170 + i * 56, theme.TEXT)
			for i, (name, label) in enumerate((("account", "Account"), ("user", "Watching as"), ("server", "Server"), ("libraries", "Libraries")))),
		"rows": "".join(
			'<widget name="row%d_bg" position="90,%d" size="1100,64" backgroundColor="%s" zPosition="1" />'
			'<widget name="row%d" position="118,%d" size="700,64" font="Regular;32" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
			'<widget name="row%d_value" position="820,%d" size="346,64" font="Regular;28" halign="right" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
			% (i, 420 + i * 76, theme.CARD, i, 420 + i * 76, theme.TEXT, i, 420 + i * 76, theme.TEXT_MUTED)
			for i in range(MAX_ROWS)),
	}

	skin = scale.skin(skin)

	def __init__(self, session, settings_path=plex.SETTINGS_PATH, request=None):
		Screen.__init__(self, session)
		self.setTitle("Plex")
		self.settings_path = settings_path
		self.settings = plex.load_settings(settings_path)
		self.client = plex.Client(self.settings, request)
		self.background = Background()
		self.selected = 0
		self.library_names = {}
		for name in ("account", "user", "server", "libraries"):
			self["fact_" + name] = Label()
		for i in range(MAX_ROWS):
			self["row%d_bg" % i] = Label()
			self["row%d" % i] = Label()
			self["row%d_value" % i] = Label()
		self["message"] = Label()
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "MenuActions"], {
			"ok": self.ok,
			"cancel": self.leave,
			"menu": self.leave,
			"up": lambda: self.move(-1),
			"down": lambda: self.move(1),
		}, -1)
		self.onLayoutFinish.append(self.paint)

	# What can be changed

	def rows(self):
		if not self.settings.get("account_token"):
			return [("Link a Plex account", "link", "")]
		return [
			("Choose who the TV watches as", "user", ""),
			("Choose the server", "server", ""),
			("Choose the libraries", "libraries", ""),
			("Quality away from home", "quality", quality_text(self.settings["remote_kbps"])),
			("Subtitles", "subtitles", "On" if self.settings["subtitles"] else "Off"),
			("Link a different account", "link", ""),
			("Unlink Plex", "unlink", ""),
		]

	def move(self, step):
		self.selected = max(0, min(len(self.rows()) - 1, self.selected + step))
		self.paint()

	def ok(self):
		action = self.rows()[self.selected][1]
		self["message"].setText("")
		getattr(self, "step_" + action)()

	def save(self, message=""):
		plex.save_settings(self.settings, self.settings_path)
		self["message"].setText(message)
		self.selected = min(self.selected, len(self.rows()) - 1)
		self.paint()

	def failed(self, what):
		self["message"].setText("%s. Check the internet connection and try again." % what)

	# Steps. Linking leads straight on to the user, the server and the libraries.

	def step_link(self):
		self.session.openWithCallback(self.linked, PlexLink, self.client)

	def linked(self, token=None):
		if not token:
			return
		for key in ("user", "user_token", "server", "last_uri"):
			self.settings.pop(key, None)
		self.settings["account_token"] = token
		self.settings["sections"] = []
		self.save("Plex account linked")
		self.step_user(then_continue=True)

	def step_user(self, then_continue=False):
		self["message"].setText("Asking Plex for the people in this account...")
		self.background.run(lambda: self.client.home_users(self.settings["account_token"]),
			lambda users, error: self.users_found(users, error, then_continue))

	def users_found(self, users, error, then_continue):
		if error is not None:
			return self.failed("Couldn't get the Plex users")
		self["message"].setText("")
		self.users = users or []
		if len(self.users) <= 1:
			# No Plex Home: the account itself is the only user.
			self.user_chosen({"title": "Account owner", "uuid": None}, None, then_continue)
			return
		options = [(user["title"], index, "Admin" if user["admin"] else ("PIN" if user["protected"] else ""))
			for index, user in enumerate(self.users)]
		self.session.openWithCallback(lambda index: self.user_picked(index, then_continue), OptionList,
			"Who does the TV watch as?", options, "The TV always uses this person's Plex: their films, programmes and what they've watched.")

	def user_picked(self, index, then_continue):
		if index is None:
			return
		user = self.users[index]
		if user["protected"]:
			self.session.openWithCallback(lambda pin: pin and self.user_chosen(user, pin, then_continue), PinEntry,
				"%s's Plex PIN" % user["title"], "Enter the PIN this person uses on Plex")
		else:
			self.user_chosen(user, None, then_continue)

	def user_chosen(self, user, pin, then_continue):
		def switch():
			if user["uuid"] is None:
				return self.settings["account_token"]
			return self.client.switch_user(self.settings["account_token"], user, pin)

		def done(token, error):
			if error is not None:
				return self.failed("Plex didn't accept %s" % ("that PIN" if pin else "that user"))
			self.settings["user"] = {"title": user["title"], "uuid": user["uuid"]}
			self.settings["user_token"] = token
			self.save("The TV now watches as %s" % user["title"])
			if then_continue:
				self.step_server(then_continue=True)

		self.background.run(switch, done)

	def step_server(self, then_continue=False):
		if not self.settings.get("user_token"):
			return self.step_user(then_continue=True)
		self["message"].setText("Looking for Plex servers...")
		self.background.run(lambda: self.client.servers(self.settings["user_token"]),
			lambda servers, error: self.servers_found(servers, error, then_continue))

	def servers_found(self, servers, error, then_continue):
		if error is not None:
			return self.failed("Couldn't get the Plex servers")
		self.servers = servers or []
		if not self.servers:
			self["message"].setText("This person can't see any Plex servers")
			return
		self["message"].setText("")
		options = [(server["name"], index, "%d ways in" % len(server["connections"])) for index, server in enumerate(self.servers)]
		self.session.openWithCallback(lambda index: self.server_picked(index, then_continue), OptionList, "Choose the server", options)

	def server_picked(self, index, then_continue):
		if index is None:
			return
		server = self.servers[index]
		self["message"].setText("Trying %s..." % server["name"])

		def done(connection, error):
			if error is not None:
				return self.failed("Can't reach %s" % server["name"])
			self.settings["server"] = server
			self.save("Connected to %s: %s" % (server["name"], plex.Client.describe(connection)))
			if then_continue:
				self.step_libraries(choose_all=True)

		self.background.run(lambda: self.client.connect(server), done)

	def step_libraries(self, choose_all=False):
		if not self.settings.get("server"):
			return self.step_server()
		self["message"].setText("Reading the libraries...")

		def done(sections, error):
			if error is not None:
				return self.failed("Couldn't read the libraries")
			self["message"].setText("")
			self.library_names = dict((section["key"], section["title"]) for section in sections)
			chosen = [section["key"] for section in sections] if choose_all or not self.settings["sections"] else self.settings["sections"]
			options = [(section["title"], section["key"], "") for section in sections]
			self.session.openWithCallback(self.libraries_chosen, OptionList, "Choose the libraries", options,
				"Only film and TV libraries are shown.", toggles=chosen)

		self.background.run(self.client.sections, done)

	def libraries_chosen(self, chosen):
		if chosen is None:
			return
		self.settings["sections"] = sorted(chosen)
		self.settings["section_names"] = [self.library_names.get(key, key) for key in self.settings["sections"]]
		self.save("Plex is ready in Recordings" if plex.is_configured(self.settings) else "Choose at least one library")

	def step_quality(self):
		current = self.settings["remote_kbps"]
		index = QUALITY_STEPS.index(current) if current in QUALITY_STEPS else 2
		self.settings["remote_kbps"] = QUALITY_STEPS[(index + 1) % len(QUALITY_STEPS)]
		self.save()

	def step_subtitles(self):
		self.settings["subtitles"] = not self.settings["subtitles"]
		self.save()

	def step_unlink(self):
		self.session.openWithCallback(self.unlink_chosen, GullionChoice, "Unlink Plex?",
			[("Unlink", "unlink"), ("Keep it", None)], "Films and TV from Plex will disappear from Recordings.")

	def unlink_chosen(self, choice=None):
		if choice != "unlink":
			return
		for key in ("account_token", "user", "user_token", "server", "last_uri", "section_names"):
			self.settings.pop(key, None)
		self.settings["sections"] = []
		self.selected = 0
		self.save("Plex unlinked")

	def leave(self):
		self.background.stop()
		self.close()

	# Drawing

	def paint(self):
		settings = self.settings
		self["fact_account"].setText("Linked" if settings.get("account_token") else "Not linked")
		self["fact_user"].setText((settings.get("user") or {}).get("title", "-"))
		server = settings.get("server")
		if server:
			connection = [c for c in server["connections"] if c["uri"] == settings.get("last_uri")]
			self["fact_server"].setText("%s  ·  %s" % (server["name"], plex.Client.describe(connection[0]) if connection else "not tried yet"))
		else:
			self["fact_server"].setText("-")
		self["fact_libraries"].setText(", ".join(settings.get("section_names") or []) or "-")
		rows = self.rows()
		for i in range(MAX_ROWS):
			present = i < len(rows)
			label, key, value = rows[i] if present else ("", None, "")
			self["row%d" % i].setText(label)
			self["row%d_value" % i].setText(value)
			if present:
				self["row%d_bg" % i].show()
			else:
				self["row%d_bg" % i].hide()
			chosen = present and i == self.selected
			tiles.colour(self["row%d_bg" % i], background=theme.CARD_SELECTED if chosen else theme.CARD)
			tiles.colour(self["row%d" % i], foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT)
			tiles.colour(self["row%d_value" % i], foreground=theme.TEXT_ON_SELECTED_MUTED if chosen else theme.TEXT_MUTED)
