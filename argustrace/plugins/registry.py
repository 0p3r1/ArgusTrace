from argustrace.plugins.holehe_plugin import HolehePlugin
from argustrace.plugins.ignorant_plugin import IgnorantPlugin
from argustrace.plugins.mock_plugin import MockPlugin
from argustrace.plugins.sherlock_plugin import SherlockPlugin

PLUGINS = {
    "mock": MockPlugin(),
    "sherlock": SherlockPlugin(),  # fast: curated site list (~10s)
    "sherlock-full": SherlockPlugin(sites=None),  # slow: full ~400+ site scan
    "holehe": HolehePlugin(),
    "ignorant": IgnorantPlugin(),
}

# Human-facing metadata for the web UI. Kept separate from the Plugin
# protocol itself (name/supported_entities/run) so the protocol stays
# minimal — this is presentation, not part of the plugin contract.
PLUGIN_INFO = {
    "mock": {
        "label": "Demo",
        "entity_type": "any",
        "description": "Hardcoded sample results. No network access — proves the pipeline works.",
        "speed": "instant",
    },
    "sherlock": {
        "label": "Sherlock (fast)",
        "entity_type": "username",
        "description": "Checks a username against ~10 popular sites (GitHub, Reddit, Instagram, ...).",
        "speed": "~5s",
    },
    "sherlock-full": {
        "label": "Sherlock (full scan)",
        "entity_type": "username",
        "description": "Checks a username against 400+ sites Sherlock knows about.",
        "speed": "1-3 min",
    },
    "holehe": {
        "label": "Holehe",
        "entity_type": "email",
        "description": "Checks whether an email is registered on ~120 sites via their password-reset flow.",
        "speed": "~10s",
    },
    "ignorant": {
        "label": "Ignorant",
        "entity_type": "phone",
        "description": "Checks whether a phone number is registered on Amazon, Instagram, and Snapchat.",
        "speed": "~5s",
    },
}
