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
# as one entry with a variant picker instead of separate entries. Kept
# separate from the Plugin protocol itself — this is presentation, not
# part of the plugin contract.
#
# `options` describes real, safe CLI flags worth exposing per family (not
# every flag the underlying tool has — report-format flags, proxy/Tor
# settings, and anything requiring an API key we don't provision are
# deliberately left out). Empty means the tool has nothing meaningful to
# add beyond entity+variant, which is legitimate, not a gap.
#
# `version_check` describes how to detect whether our pinned version is
# current: "pypi" (package name), "dockerhub" (repository), "github_releases"
# (repo), or "none" for things that aren't a versioned tool at all (a live
# web service, or our own demo code).
TOOL_FAMILIES = {
    "mock": {
        "label": "Demo",
        "entity_type": "any",
        "hidden": True,  # dev/testing tool, never shown in the web catalog
        "description": "Hardcoded sample results. No network access — proves the pipeline works.",
        "repo_url": None,
        "docs_url": None,
        "examples": [{"label": "Any text works", "entity": "alice"}],
        "variants": {
            "mock": {"variant_label": "Default", "speed": "instant", "fast": True},
        },
        "options": [],
        "version_check": {"method": "none"},
    },
    "sherlock": {
        "label": "Sherlock",
        "entity_type": "username",
        "description": "Checks a username for an existing account across many sites.",
        "repo_url": "https://github.com/sherlock-project/sherlock",
        "docs_url": "https://github.com/sherlock-project/sherlock#usage",
        "examples": [{"label": "Well-known GitHub user", "entity": "torvalds"}],
        "variants": {
            "sherlock": {"variant_label": "Fast (~10 sites)", "speed": "~5s", "fast": True},
            "sherlock-full": {"variant_label": "Full scan (400+ sites)", "speed": "1-3 min", "fast": False},
        },
        "options": [
            {
                "name": "timeout", "flag": "--timeout", "type": "int", "required": False,
                "default": 15, "min": 5, "max": 30,
                "description": "Per-site HTTP timeout in seconds before a site is marked Unknown (ERROR).",
            },
            {
                "name": "nsfw", "flag": "--nsfw", "type": "bool", "required": False,
                "default": False,
                "description": "Also check NSFW sites, excluded from the default site list.",
            },
        ],
        # Pinned by image digest (see sherlock_plugin.IMAGE) at Sherlock v0.16.0.
        # Bumping the digest must also bump this constant.
        "version_check": {"method": "dockerhub", "repository": "sherlock/sherlock", "pinned_version": "0.16.0"},
    },
    "maigret": {
        "label": "Maigret",
        "entity_type": "username",
        "description": "Like Sherlock, but with a much larger site database and OSINT metadata extraction from claimed profiles.",
        "repo_url": "https://github.com/soxoj/maigret",
        "docs_url": "https://maigret.readthedocs.io/",
        "examples": [{"label": "Well-known GitHub user", "entity": "torvalds"}],
        "variants": {
            "maigret": {"variant_label": "Fast (top ~15 sites)", "speed": "~6s", "fast": True},
            "maigret-full": {"variant_label": "Full scan (3000+ sites)", "speed": "several min", "fast": False},
        },
        "options": [
            {
                "name": "timeout", "flag": "--timeout", "type": "int", "required": False,
                "default": 30, "min": 5, "max": 60,
                "description": "Per-site HTTP timeout in seconds (Maigret's own default is 30).",
            },
            {
                "name": "retries", "flag": "--retries", "type": "int", "required": False,
                "default": 0, "min": 0, "max": 3,
                "description": "Attempts to restart temporarily failed requests.",
            },
            {
                "name": "tags", "flag": "--tags", "type": "str", "required": False,
                "default": None,
                "description": (
                    "Comma-separated site tags to limit the scan to (e.g. \"photo,gaming\"). "
                    "Free text, not a fixed choice — Maigret's site database also grows over "
                    "time. Most common (from `--stats` on the pinned 0.6.3 database): forum, "
                    "social, gaming, tech, discussion, education, business, coding, hobby, "
                    "apps, music, blog, news, art, sharing, auto, shopping, photo, design, "
                    "crypto. Two-letter country codes (e.g. \"us\", \"fr\") work too."
                ),
            },
            {
                "name": "exclude_tags", "flag": "--exclude-tags", "type": "str", "required": False,
                "default": None,
                "description": "Comma-separated site tags to exclude (blacklist) — same vocabulary as tags.",
            },
            {
                "name": "enrich", "flag": "--enrich", "type": "bool", "required": False,
                "default": False,
                "description": (
                    "Fetch secondary API endpoints derived from claimed profile URLs for "
                    "extra extracted fields. More requests per found site, so noticeably slower."
                ),
            },
        ],
        # Pinned by image digest (see maigret_plugin.IMAGE) at Maigret v0.6.3.
        # Bumping the digest must also bump this constant. Checked via PyPI,
        # not Docker Hub: soxoj/maigret's Docker tags are git-commit SHAs
        # (e.g. "c2e24f3", "web-b186b77"), not semantic versions — there is
        # no tag to match "0.6.3" against. The PyPI package uses clean
        # semver releases that line up with the Docker image's version.
        "version_check": {"method": "pypi", "package": "maigret", "pinned_version": "0.6.3"},
    },
    "holehe": {
        "label": "Holehe",
        "entity_type": "email",
        "description": "Checks whether an email is registered on ~120 sites via their password-reset flow.",
        "repo_url": "https://github.com/megadose/holehe",
        "docs_url": "https://github.com/megadose/holehe#-usage",
        "examples": [{"label": "Format check", "entity": "test@gmail.com"}],
        "variants": {
            "holehe": {"variant_label": "Default", "speed": "~10s", "fast": True},
        },
        "options": [
            {
                "name": "no_password_recovery", "flag": "-NP", "type": "bool", "required": False,
                "default": False,
                "description": (
                    "Skip the 4 modules (Adobe, Mail.ru, Odnoklassniki, Samsung) that trigger "
                    "a real password-reset email/notification on the target account. Slightly "
                    "less coverage in exchange for a quieter, less detectable check."
                ),
            },
        ],
        "version_check": {"method": "pypi", "package": "holehe", "pinned_version": "1.61"},
    },
    "ignorant": {
        "label": "Ignorant",
        "entity_type": "phone",
        "description": "Checks whether a phone number is registered on Amazon, Instagram, and Snapchat.",
        "repo_url": "https://github.com/megadose/ignorant",
        "docs_url": "https://github.com/megadose/ignorant#-usage",
        "examples": [{"label": "E164 format", "entity": "+16502530000"}],
        "variants": {
            "ignorant": {"variant_label": "Default", "speed": "~5s", "fast": True},
        },
        "options": [
            {
                "name": "timeout", "flag": "--timeout", "type": "int", "required": False,
                "default": 10, "min": 5, "max": 30,
                "description": "Per-site HTTP timeout in seconds.",
            },
        ],
        "version_check": {"method": "pypi", "package": "ignorant", "pinned_version": "1.2"},
    },
    "crtsh": {
        "label": "crt.sh",
        "entity_type": "domain",
        "description": "Lists subdomains found in public Certificate Transparency logs. Free service, sometimes flaky.",
        "repo_url": "https://crt.sh",
        "docs_url": None,
        "examples": [{"label": "Public domain", "entity": "anthropic.com"}],
        "variants": {
            "crtsh": {"variant_label": "Default", "speed": "~5s*", "fast": True},
        },
        "options": [],
        "version_check": {"method": "none"},
    },
    "theharvester": {
        "label": "theHarvester",
        "entity_type": "domain",
        "description": "Aggregates subdomains/hosts for a domain from free passive-recon sources (no API keys).",
        "repo_url": "https://github.com/laramies/theHarvester",
        "docs_url": "https://github.com/laramies/theHarvester#usage",
        "examples": [{"label": "Public domain", "entity": "tesla.com"}],
        "variants": {
            "theharvester": {"variant_label": "Single source (rapiddns)", "speed": "~10s", "fast": True},
            "theharvester-broad": {"variant_label": "Broad (4 sources combined)", "speed": "~30-60s", "fast": False},
        },
        "options": [
            {
                "name": "limit", "flag": "-l", "type": "int", "required": False,
                "default": 500, "min": 100, "max": 1000,
                "description": "Maximum number of results requested per source.",
            },
            {
                "name": "sources", "flag": "-b", "type": "enum_multi", "required": False,
                "default": ["rapiddns"],
                "choices": ["rapiddns", "otx", "hackertarget", "crtsh"],
                "description": (
                    "Which free, no-API-key sources to query, overriding the "
                    "single-source/broad presets."
                ),
            },
            {
                "name": "dns_lookup", "flag": "-n", "type": "bool", "required": False,
                "default": False,
                "description": (
                    "Actively resolve hosts found by the passive sources above that don't "
                    "already come with a resolved address."
                ),
            },
        ],
        # Pinned by git tag in docker/theharvester/Dockerfile (--branch 4.11.1).
        "version_check": {"method": "github_releases", "repo": "laramies/theHarvester", "pinned_version": "4.11.1"},
    },
}
