"""Thin wrappers over enigma2's channel lists, EPG cache, record timers and zapping.

Kept apart from the screens so tools/check.py and tools/preview.py can swap in
sample data.
"""
from enigma import eEPGCache, eServiceCenter, eServiceReference

TV_BOUQUETS = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
# Service flags for entries that aren't playable channels (markers, folders).
_NOT_PLAYABLE = eServiceReference.isMarker | eServiceReference.isDirectory


class Channel(object):
	def __init__(self, ref, name, number):
		self.ref = ref
		self.name = name
		self.number = number


class Event(object):
	def __init__(self, eid, begin, duration, title, short="", extended=""):
		self.eid = eid
		self.begin = begin
		self.duration = duration
		self.end = begin + duration
		self.title = title
		self.short = short
		self.extended = extended

	def airing(self, now):
		return self.begin <= now < self.end

	@property
	def description(self):
		if self.short and self.extended and not self.extended.startswith(self.short):
			return "%s %s" % (self.short, self.extended)
		return self.extended or self.short


def tv_bouquets():
	"""[(bouquet ref string, name)] in the order the box numbers them."""
	content = eServiceCenter.getInstance().list(eServiceReference(TV_BOUQUETS))
	return content and content.getContent("SN", True) or []


def channel_lists():
	"""[(bouquet ref, name, [Channel])] with enigma2's default running numbering."""
	lists = []
	number = 0
	for ref, name in tv_bouquets():
		channels = []
		content = eServiceCenter.getInstance().list(eServiceReference(ref))
		for service in content and content.getContent("R", True) or []:
			if service.flags & _NOT_PLAYABLE:
				continue
			number += 1
			channels.append(Channel(service.toString(), _clean(eServiceCenter.getInstance().info(service).getName(service)), number))
		if channels:
			lists.append((ref, _clean(name), channels))
	return lists


def events(ref, begin, minutes):
	"""Events on a channel overlapping [begin, begin + minutes], in time order."""
	found = eEPGCache.getInstance().lookupEvent(["IBDTSE", (ref, 0, int(begin), int(minutes))]) or []
	result = []
	for eid, start, duration, title, short, extended in found:
		if start is None or not duration:
			continue
		result.append(Event(eid, start, duration, title or "", short or "", extended or ""))
	result.sort(key=lambda event: event.begin)
	return result


def find_timer(session, ref, event):
	compare = eServiceReference(ref).toCompareString()
	for timer in session.nav.RecordTimer.timer_list:
		if timer.service_ref.ref.toCompareString() != compare:
			continue
		if timer.eit == event.eid or (timer.begin <= event.begin and timer.end >= event.end):
			return timer
	return None


def add_timer(session, ref, event):
	"""Schedule a recording with the box's usual margins. Returns True if it was added."""
	from RecordTimer import AFTEREVENT, RecordTimerEntry, parseEvent
	from ServiceReference import ServiceReference

	service_event = eEPGCache.getInstance().lookupEventId(eServiceReference(ref), event.eid)
	if service_event is None:
		return False
	begin, end, name, description, eit = parseEvent(service_event)
	timer = RecordTimerEntry(ServiceReference(ref), begin, end, name, description, eit, afterEvent=AFTEREVENT.AUTO)
	conflicts = session.nav.RecordTimer.record(timer)
	return not conflicts


def remove_timer(session, timer):
	session.nav.RecordTimer.removeEntry(timer)


def current_ref(session):
	ref = session.nav.getCurrentlyPlayingServiceReference()
	return ref and ref.toString() or None


def zap(session, ref, bouquet_ref):
	"""Switch to a channel through the channel list so CH+/- carries on from it."""
	from Screens.InfoBar import InfoBar

	service = eServiceReference(ref)
	servicelist = InfoBar.instance and getattr(InfoBar.instance, "servicelist", None)
	if servicelist is None:
		session.nav.playService(service)
		return
	bouquet = eServiceReference(bouquet_ref)
	if servicelist.getRoot() != bouquet:
		servicelist.clearPath()
		if servicelist.bouquet_root != bouquet:
			servicelist.enterPath(servicelist.bouquet_root)
		servicelist.enterPath(bouquet)
	servicelist.setCurrentSelection(service)
	servicelist.zap()


def _clean(name):
	# Strip the DVB emphasis control characters some channels use.
	return (name or "").replace("\xc2\x86", "").replace("\xc2\x87", "")
