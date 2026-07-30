from argustrace.plugins.holehe_plugin import HolehePlugin
from argustrace.plugins.ignorant_plugin import IgnorantPlugin
from argustrace.plugins.mock_plugin import MockPlugin
from argustrace.plugins.sherlock_plugin import SherlockPlugin

PLUGINS = {
    "mock": MockPlugin(),
    "sherlock": SherlockPlugin(),        # fast: curated site list (~10s)
    "sherlock-full": SherlockPlugin(sites=None),  # slow: full ~400+ site scan
    "holehe": HolehePlugin(),
    "ignorant": IgnorantPlugin(),
}
