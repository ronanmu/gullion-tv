# -*- coding: utf-8 -*-
"""Skin converter for the channel banner, registered as
Components.Converter.GullionServiceInfo by infobar.install().

	Number     (session.CurrentService) channel number as the guide shows it
	Name       (session.CurrentService) channel name alone: OpenATV 7.x's ServiceName
	                                    Name puts the channel number in front
	NumberAndName (session.CurrentService) "101   BBC One NI HD"
	IsRecording (session.CurrentService) boolean: this channel is being recorded now
	Remaining  (session.Event_Now)      "18 min left"
	Icon:N     (session.Event_Now)      the Nth icon from the right of the programme's
	                                    row (access codes, hd/uhd, delivery), for the
	                                    GullionIcon renderer; "" when there are fewer
"""
import time

from enigma import iPlayableService, iServiceInformation
from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

from . import epg, serviceinfo

_SERVICE_EVENTS = (iPlayableService.evStart, iPlayableService.evUpdatedInfo, iPlayableService.evVideoSizeChanged)
_numbers = {}


def _playing():
	"""(reference, picture height) of what's on, for converters whose source is an event."""
	try:
		import NavigationInstance
		service = NavigationInstance.instance.getCurrentService()
	except Exception:
		return "", -1
	info = service and service.info()
	if not info:
		return "", -1
	return info.getInfoString(iServiceInformation.sServiceref), info.getInfo(iServiceInformation.sVideoHeight)


def recording_now(ref, timers=None):
	"""Is a recording running on this channel? (Not just anywhere on the box.)"""
	if not ref:
		return False
	if timers is None:
		try:
			import NavigationInstance
			timers = NavigationInstance.instance.RecordTimer.timer_list
		except Exception:
			return False
	from enigma import eServiceReference
	wanted = eServiceReference(ref).toCompareString()
	for timer in timers:
		if getattr(timer, "state", None) == _RUNNING and timer.service_ref.ref.toCompareString() == wanted:
			return True
	return False


_RUNNING = 2  # TimerEntry.StateRunning


class GullionServiceInfo(Poll, Converter, object):
	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		if type == "Remaining":
			self.poll_interval = 30000
			self.poll_enabled = True
		elif type == "IsRecording":
			# Recordings start and stop without the channel changing.
			self.poll_interval = 5000
			self.poll_enabled = True
		elif type.startswith("Icon:"):
			# HD is only certain once the picture is decoding, a moment after the event arrives.
			self.poll_interval = 5000
			self.poll_enabled = True

	def icon(self):
		"""Icon:1 is the rightmost, Icon:2 the one before, so the row packs to the right."""
		event = self.source.event
		text = ""
		if event is not None:
			text = "%s %s" % (event.getShortDescription() or "", event.getExtendedDescription() or "")
		ref, height = _playing()
		names = serviceinfo.icon_row(ref, height, text.strip())
		position = int(self.type.split(":")[1])
		return names[-position] if position <= len(names) else ""

	def service_details(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return "", -1
		return info.getInfoString(iServiceInformation.sServiceref), info.getInfo(iServiceInformation.sVideoHeight)

	@cached
	def getText(self):
		if self.type.startswith("Icon:"):
			return self.icon()
		if self.type == "Remaining":
			event = self.source.event
			if event is None:
				return ""
			return serviceinfo.remaining(event.getBeginTime() + event.getDuration() - time.time())
		if self.type == "Name":
			return self.name()
		ref, height = self.service_details()
		if self.type == "NumberAndName":
			number = self.number(ref)
			return "%s   %s" % (number, self.name()) if number else self.name()
		if self.type == "Number":
			return self.number(ref)
		return ""

	def name(self):
		service = self.source.service
		info = service and service.info()
		name = info and info.getName() or ""
		# Drop the emphasis markers some broadcasters put in names, as ServiceName does.
		return name.replace("\xc2\x86", "").replace("\xc2\x87", "")

	def number(self, ref):
		if not _numbers:
			_numbers.update(serviceinfo.channel_numbers(epg.channel_lists()))
		number = _numbers.get(serviceinfo.key(ref))
		return str(number) if number else ""

	text = property(getText)

	@cached
	def getBoolean(self):
		if self.type == "IsRecording":
			return recording_now(self.service_details()[0])
		return False

	boolean = property(getBoolean)

	def changed(self, what):
		if what[0] == self.CHANGED_SPECIFIC:
			if what[1] not in _SERVICE_EVENTS:
				return
			if what[1] == iPlayableService.evStart:
				# Bouquets may have been edited since the numbers were worked out.
				_numbers.clear()
		Converter.changed(self, what)
