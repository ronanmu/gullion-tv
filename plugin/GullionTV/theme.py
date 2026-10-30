"""Shared colours and fonts for the Gullion TV screens (1920x1080).

Skin colours are #AARRGGBB where AA=00 is opaque. RGB ints are for gRGB().
"""

BACKGROUND = "#00111316"
CARD = "#001c1f24"
CARD_SELECTED = "#00eceae4"
DIVIDER = "#002c2f35"
POPUP = "#00252a31"
POPUP_BORDER = "#00454b55"
TEXT = "#00eceae4"
TEXT_MUTED = "#00a8a59d"
TEXT_ON_SELECTED = "#00111316"
TEXT_ON_SELECTED_MUTED = "#005f5e5a"
LIVE = "#009fe1cb"
LIVE_ON_LIGHT = "#000f6e56"
ACCENT = "#0085b7eb"

# TV guide grid
ROW_SELECTED = "#0023272e"
CELL_PAST = "#00171a1f"
CELL_ELAPSED_SELECTED = "#00d5d3cd"
DAY_BAR = "#00181b20"

KEY_RED = "#00e24b4a"
KEY_GREEN = "#00639922"
KEY_YELLOW = "#00ef9f27"
KEY_BLUE = "#00378add"


def rgb(colour):
	"""Skin colour string to the int gRGB() expects."""
	return int(colour[1:], 16)


def opaque(colour):
	"""A skin colour for ePicLoad, which counts alpha the other way round: FF is solid."""
	return "#ff" + colour[3:]


def frame(width, height, colour=POPUP_BORDER, thickness=3):
	"""A pop-up's border as four thin edges, at the design size.

	The card colour is the pop-up's own background, not a box under its text:
	enigma2 6.4 draws plain boxes (eLabel) after a screen's widgets, so a card box
	would cover the heading, the options and the PIN digits.
	"""
	edges = ((0, 0, width, thickness), (0, height - thickness, width, thickness),
		(0, 0, thickness, height), (width - thickness, 0, thickness, height))
	return "".join('<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" />' % (x, y, w, h, colour)
		for x, y, w, h in edges)
