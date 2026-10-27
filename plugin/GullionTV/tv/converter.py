"""Skin converter for the channel banner, registered as
Components.Converter.GullionServiceInfo by infobar.install().

	Delivery   (session.CurrentService) "Terrestrial", "Satellite · 28.2°E", ...
	Number     (session.CurrentService) channel number as the guide shows it
	IsHD       (session.CurrentService) boolean, for ConditionalShowHide
	Remaining  (session.Event_Now)      "18 min left"
"""
import time

from enigma import iPlayableService, iServiceInformation
from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

from . import epg, serviceinfo

_SERVICE_EVENTS = (iPlayableService.evStart, iPlayableService.evUpdatedInfo, iPlayableService.evVideoSizeChanged)
_numbers = {}


class GullionServiceInfo(Poll, Converter, object):
	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type
		if type == "Remaining":
			self.poll_interval = 30000
			self.poll_enabled = True

	def service_details(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return "", -1
		return info.getInfoString(iServiceInformation.sServiceref), info.getInfo(iServiceInformation.sVideoHeight)

	@cached
	def getText(self):
		if self.type == "Remaining":
			event = self.source.event
			if event is None:
				return ""
			return serviceinfo.remaining(event.getBeginTime() + event.getDuration() - time.time())
		ref, height = self.service_details()
		if self.type == "Delivery":
			return serviceinfo.delivery(ref)
		if self.type == "Number":
			if not _numbers:
				_numbers.update(serviceinfo.channel_numbers(epg.channel_lists()))
			number = _numbers.get(serviceinfo.key(ref))
			return str(number) if number else ""
		return ""

	text = property(getText)

	@cached
	def getBoolean(self):
		if self.type == "IsHD":
			ref, height = self.service_details()
			return serviceinfo.is_hd(ref, height)
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
