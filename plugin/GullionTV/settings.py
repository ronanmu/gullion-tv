from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigPIN

config.plugins.gulliontv = ConfigSubsection()
# When off, MENU opens the stock OpenATV menu as normal.
config.plugins.gulliontv.enabled = ConfigYesNo(default=True)
# Large channel banner over live TV. Read at start-up, so changes need a restart.
config.plugins.gulliontv.infobar = ConfigYesNo(default=True)
# Tech Support PIN guarding the stock menu. There's no default: the first time
# Settings is opened, Gullion TV asks for one to be chosen.
config.plugins.gulliontv.pin = ConfigPIN(default=0, len=4)
config.plugins.gulliontv.pin_set = ConfigYesNo(default=False)
