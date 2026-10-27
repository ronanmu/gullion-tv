# -*- coding: utf-8 -*-
"""Sample channel lists, schedules and recordings for offline checks and renders.

install() replaces GullionTV.tv.epg's box-facing functions with these.
"""
import time

# Tuesday 27 October 2026, 19:42.
NOW = time.mktime((2026, 10, 27, 19, 42, 0, 0, 0, -1))

MY_CHANNELS = [
	("RTÉ One", [
		("18:00", 60, "Six One News", "The day's news, sport and weather."),
		("19:00", 60, "Nationwide", "A trip to a family-run bakery in Dundalk, and the volunteers keeping a "
			"Sligo lighthouse open to visitors through the winter months."),
		("20:00", 30, "Fair City", "Paul worries about the café's future, and Carrie gets some unexpected news."),
		("20:30", 60, "Prime Time", "Current affairs and investigations."),
		("21:30", 60, "Nine O'Clock News", "News and weather."),
	]),
	("RTÉ2", [
		("18:30", 45, "The Simpsons", ""),
		("19:15", 30, "Home and Away", ""),
		("19:45", 75, "Champions League Highlights", "Goals and talking points from tonight's games."),
		("21:00", 60, "Film: The Commitments", ""),
	]),
	("Virgin Media One", [
		("18:30", 30, "Virgin Media News", ""),
		("19:00", 30, "Emmerdale", ""),
		("19:30", 60, "Coronation Street", ""),
		("20:30", 60, "The Tonight Show", ""),
	]),
	("TG4", [
		("19:00", 20, "Nuacht TG4", ""),
		("19:20", 40, "Ros na Rún", ""),
		("20:00", 60, "Seó Spóirt", ""),
		("21:00", 60, "Scannán", ""),
	]),
	("BBC One NI", [
		("18:30", 30, "BBC Newsline", ""),
		("19:00", 30, "The One Show", ""),
		("19:30", 30, "EastEnders", ""),
		("20:00", 60, "MasterChef", ""),
		("21:00", 30, "BBC News at Nine", ""),
	]),
	("BBC Two NI", [
		("19:00", 30, "Mastermind", ""),
		("19:30", 30, "Gardeners' World", ""),
		("20:00", 60, "Great British Railway Journeys", ""),
		("21:00", 60, "Documentary", ""),
	]),
	("UTV", [
		("18:00", 60, "UTV Live", ""),
		("19:00", 30, "Emmerdale", ""),
		("19:30", 60, "Coronation Street", ""),
		("20:30", 60, "Drama", ""),
	]),
	("Channel 4", [
		("18:30", 30, "Hollyoaks", ""),
		("19:00", 60, "Channel 4 News", ""),
		("20:00", 60, "Grand Designs", ""),
		("21:00", 60, "Gogglebox", ""),
	]),
]
RECORDING = {("RTÉ One", "Fair City"), ("BBC One NI", "MasterChef")}
PLAYING = "RTÉ One"


def _at(clock):
	day = time.localtime(NOW)
	hour, minute = [int(part) for part in clock.split(":")]
	return time.mktime((day.tm_year, day.tm_mon, day.tm_mday, hour, minute, 0, 0, 0, -1))


def install():
	from GullionTV.tv import epg

	channels = []
	schedule = {}
	eid = 1000
	for number, (name, shows) in enumerate(MY_CHANNELS, 1):
		# Saorview channels are terrestrial; the rest come from Freesat at 28.2°E.
		namespace = "EEEE0000" if number <= 4 else "11A0000"
		ref = "1:0:19:%X:1:1:%s:0:0:0:" % (number, namespace)
		channels.append(epg.Channel(ref, name, number))
		schedule[ref] = []
		for clock, minutes, title, description in shows:
			eid += 1
			schedule[ref].append(epg.Event(eid, _at(clock), minutes * 60, title, description))
	names = dict((channel.ref, channel.name) for channel in channels)
	timers = set((ref, event.eid) for ref, events in schedule.items() for event in events
		if (names[ref], event.title) in RECORDING)
	playing = [channel.ref for channel in channels if channel.name == PLAYING][0]

	lists = [
		("my", "My channels", channels),
		("saorview", "Saorview", [channel for channel in channels if channel.name in ("RTÉ One", "RTÉ2", "Virgin Media One", "TG4")]),
		("freesat-ent", "Freesat · Entertainment", [channel for channel in channels if "BBC" in channel.name or channel.name in ("UTV", "Channel 4")]),
	]

	epg.channel_lists = lambda: lists
	epg.events = lambda ref, begin, minutes: [event for event in schedule.get(ref, [])
		if event.end > begin and event.begin < begin + minutes * 60]
	epg.find_timer = lambda session, ref, event: (ref, event.eid) if (ref, event.eid) in timers else None
	epg.add_timer = lambda session, ref, event: timers.add((ref, event.eid)) or True
	epg.remove_timer = lambda session, timer: timers.discard(timer)
	epg.current_ref = lambda session: playing
	epg.zap = lambda session, ref, bouquet: session.zapped.append(ref)
	return timers
