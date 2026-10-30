# -*- coding: utf-8 -*-
"""Small AutoTimer bridge used by the TV Guide's Record series action."""

_manager = None


def _load():
	from Plugins.Extensions.AutoTimer.plugin import autotimer
	from Plugins.Extensions.AutoTimer.AutoTimerComponent import preferredAutoTimerComponent
	return autotimer, preferredAutoTimerComponent


def available():
	"""Whether this image has the AutoTimer extension needed for series rules."""
	try:
		_load()
		return True
	except Exception:
		return False


def _service(ref):
	value = ref.toString() if hasattr(ref, "toString") else str(ref)
	return value


def _rules(manager):
	manager.readXml()
	return manager.getTimerList()


def _same(rule, title, ref):
	return bool(getattr(rule, "enabled", False)
		and getattr(rule, "match", None) == title
		and getattr(rule, "searchType", None) == "exact"
		and getattr(rule, "searchCase", None) == "sensitive"
		and _service(ref) in (getattr(rule, "services", None) or []))


def matches(title, ref):
	"""Whether an enabled exact-title AutoTimer rule covers this channel."""
	global _manager
	try:
		if _manager is None:
			_manager = _load()[0]
		return any(_same(rule, title, ref) for rule in _rules(_manager))
	except Exception:
		return False


def add(title, ref):
	"""Create one exact, case-sensitive AutoTimer rule on one channel."""
	global _manager
	manager, component = _load()
	_manager = manager
	rules = _rules(manager)
	if any(_same(rule, title, ref) for rule in rules):
		return False
	rule = component(manager.getUniqueId(), title, title, True)
	rule.searchType = "exact"
	rule.searchCase = "sensitive"
	rule.services = [_service(ref)]
	# None means use Enigma2's standard recording margins.
	rule.offset = None
	manager.add(rule)
	manager.writeXml()
	manager.parseEPGAsync()
	return True
