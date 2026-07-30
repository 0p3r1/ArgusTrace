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

# Human-facing metadata for the web UI, grouped by tool "family" so
# variants of the same underlying tool (e.g. Sherlock fast/full) show up
# as one card with a variant picker instead of separate entries. Kept
# separate from the Plugin protocol itself — this is presentation, not
# part of the plugin contract.
TOOL_FAMILIES = {
    "mock": {
        "label": "Demo",
        "entity_type": "any",
        "description": "Hardcoded sample results. No network access — proves the pipeline works.",
        "variants": {
            "mock": {"variant_label": "Default", "speed": "instant"},
        },
    },
    "sherlock": {
        "label": "Sherlock",
        "entity_type": "username",
        "description": "Checks a username for an existing account across many sites.",
        "variants": {
            "sherlock": {"variant_label": "Fast (~10 sites)", "speed": "~5s"},
            "sherlock-full": {"variant_label": "Full scan (400+ sites)", "speed": "1-3 min"},
        },
    },
    "holehe": {
        "label": "Holehe",
        "entity_type": "email",
        "description": "Checks whether an email is registered on ~120 sites via their password-reset flow.",
        "variants": {
            "holehe": {"variant_label": "Default", "speed": "~10s"},
        },
    },
    "ignorant": {
        "label": "Ignorant",
        "entity_type": "phone",
        "description": "Checks whether a phone number is registered on Amazon, Instagram, and Snapchat.",
        "variants": {
            "ignorant": {"variant_label": "Default", "speed": "~5s"},
        },
    },
}
