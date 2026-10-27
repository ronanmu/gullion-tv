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
DAY_BAR = "#00181b20"

KEY_RED = "#00e24b4a"
KEY_GREEN = "#00639922"
KEY_YELLOW = "#00ef9f27"
KEY_BLUE = "#00378add"


def rgb(colour):
	"""Skin colour string to the int gRGB() expects."""
	return int(colour[1:], 16)
