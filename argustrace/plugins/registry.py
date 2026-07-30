from argustrace.plugins.crtsh_plugin import CrtShPlugin
from argustrace.plugins.holehe_plugin import HolehePlugin
from argustrace.plugins.ignorant_plugin import IgnorantPlugin
from argustrace.plugins.maigret_plugin import MaigretPlugin
from argustrace.plugins.mock_plugin import MockPlugin
from argustrace.plugins.sherlock_plugin import SherlockPlugin
from argustrace.plugins.theharvester_plugin import BROAD_SOURCES, TheHarvesterPlugin

PLUGINS = {
    "mock": MockPlugin(),
    "sherlock": SherlockPlugin(),        # fast: curated site list (~10s)
    "sherlock-full": SherlockPlugin(sites=None),  # slow: full ~400+ site scan
    "holehe": HolehePlugin(),
    "ignorant": IgnorantPlugin(),
    "maigret": MaigretPlugin(),                # fast: top ~15 sites
    "maigret-full": MaigretPlugin(top_sites=None),  # slow: all ~3000+ sites
    "crtsh": CrtShPlugin(),
    "theharvester": TheHarvesterPlugin(),                      # single free source
    "theharvester-broad": TheHarvesterPlugin(sources=BROAD_SOURCES),  # several free sources combined
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
    "maigret": {
        "label": "Maigret",
        "entity_type": "username",
        "description": "Like Sherlock, but with a much larger site database and OSINT metadata extraction from claimed profiles.",
        "variants": {
            "maigret": {"variant_label": "Fast (top ~15 sites)", "speed": "~6s"},
            "maigret-full": {"variant_label": "Full scan (3000+ sites)", "speed": "several min"},
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
    "crtsh": {
        "label": "crt.sh",
        "entity_type": "domain",
        "description": "Lists subdomains found in public Certificate Transparency logs. Free service, sometimes flaky.",
        "variants": {
            "crtsh": {"variant_label": "Default", "speed": "~5s*"},
        },
    },
    "theharvester": {
        "label": "theHarvester",
        "entity_type": "domain",
        "description": "Aggregates subdomains/hosts for a domain from free passive-recon sources (no API keys).",
        "variants": {
            "theharvester": {"variant_label": "Single source (rapiddns)", "speed": "~10s"},
            "theharvester-broad": {"variant_label": "Broad (4 sources combined)", "speed": "~30-60s"},
        },
    },
}
