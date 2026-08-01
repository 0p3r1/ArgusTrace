from argustrace.plugins import maigret_plugin, theharvester_plugin
from argustrace.plugins.crtsh_plugin import CrtShPlugin
from argustrace.plugins.holehe_plugin import HolehePlugin
from argustrace.plugins.ignorant_plugin import IgnorantPlugin
from argustrace.plugins.ip_plugin import IPPlugin
from argustrace.plugins.maigret_plugin import MaigretPlugin
from argustrace.plugins.mock_plugin import MockPlugin
from argustrace.plugins.recherche_entreprises_plugin import RechercheEntreprisesPlugin
from argustrace.plugins.sherlock_plugin import SherlockPlugin
from argustrace.plugins.theharvester_plugin import BROAD_SOURCES, TheHarvesterPlugin

# Native report generation is a separate, optional capability from the
# Plugin protocol (see plugins/base.py) — a family only appears here if its
# module exports a `generate_report(entity, format) -> bytes` function.
# Always re-runs the tool fresh; nothing is cached.
NATIVE_REPORT_GENERATORS = {
    "maigret": maigret_plugin.generate_report,
    "theharvester": theharvester_plugin.generate_report,
}

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
    "ip": IPPlugin(),
    "recherche-entreprises": RechercheEntreprisesPlugin(),
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
        "native_reports": [],
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
        "native_reports": [
            {
                "format": "csv", "label": "CSV", "kind": "info", "available": True,
                "note": "Same data as our own CSV export below.",
            },
            {
                "format": "xlsx", "label": "XLSX (Excel)", "kind": "download", "available": False,
                "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "note": (
                    "Sherlock writes this to a relative path outside --folderoutput "
                    "(verified against the pinned image) — a quirk in Sherlock itself, "
                    "incompatible with how we mount the container's output directory."
                ),
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
        "native_reports": [
            {
                "format": "csv", "label": "CSV", "kind": "info", "available": True,
                "note": "Same data as our own CSV export below.",
            },
            {
                "format": "json", "label": "JSON (simple/ndjson)", "kind": "info", "available": False,
                "note": (
                    "The extracted profile fields (photo, full name, location, ...) are "
                    "already merged into our own JSON export below. Maigret's own JSON report "
                    "also completely omits NOT_FOUND/ERROR sites, which ours doesn't."
                ),
            },
            {
                "format": "html", "label": "HTML report", "kind": "download", "available": True,
                "mime": "text/html",
                "note": "Narrative report: brief summary, cross-referenced tags/interests, extracted data per site.",
            },
            {
                "format": "pdf", "label": "PDF report", "kind": "download", "available": False,
                "mime": "application/pdf",
                "note": "Needs Maigret's optional 'pdf' extra, not installed in the pinned image.",
            },
            {
                "format": "xmind", "label": "XMind mindmap", "kind": "download", "available": False,
                "mime": "application/octet-stream",
                "note": "Needs an XMind viewer most users won't have; the HTML report covers the same data.",
            },
            {
                "format": "graph", "label": "Graph report", "kind": "download", "available": False,
                "mime": "application/octet-stream",
                "note": "Niche/specialized output format, not currently generated.",
            },
            {
                "format": "neo4j", "label": "Neo4j Cypher script", "kind": "download", "available": False,
                "mime": "text/plain",
                "note": "Needs a Neo4j instance to be useful; not currently generated.",
            },
            {
                "format": "md", "label": "Markdown report", "kind": "download", "available": False,
                "mime": "text/markdown",
                "note": "Strictly less information than the HTML report above; not currently generated.",
            },
            {
                "format": "txt", "label": "TXT report", "kind": "download", "available": False,
                "mime": "text/plain",
                "note": "Just a list of found URLs — already in our results table; not currently generated.",
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
        "native_reports": [
            {
                "format": "csv", "label": "CSV", "kind": "info", "available": True,
                "note": (
                    "Same data as our own CSV export below — including the recovery-email/"
                    "phone hints and extracted profile fields (full name, creation date) "
                    "that Holehe's raw CSV carries, which we merge into each finding's evidence."
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
        "native_reports": [],  # no native CLI at all — we drive the library directly
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
        "native_reports": [
            {
                "format": "html", "label": "crt.sh search page", "kind": "link", "available": True,
                "url_template": "https://crt.sh/?q={entity}",
                "note": "crt.sh isn't a CLI — this is its own live, human-browsable search page.",
            },
        ],
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
        "native_reports": [
            {
                "format": "json", "label": "JSON", "kind": "info", "available": False,
                "note": (
                    "Same information already in our own JSON export below, which additionally "
                    "groups multiple DNS records per host instead of listing them as separate rows."
                ),
            },
            {
                "format": "xml", "label": "XML", "kind": "download", "available": True,
                "mime": "application/xml",
                "note": "theHarvester always writes this alongside its JSON — no extra flags needed.",
            },
        ],
        # Pinned by git tag in docker/theharvester/Dockerfile (--branch 4.11.1).
        "version_check": {"method": "github_releases", "repo": "laramies/theHarvester", "pinned_version": "4.11.1"},
    },
    "ip": {
        "label": "IP Lookup",
        "entity_type": "ip",
        "description": "Network ownership (RDAP) and geolocation for a public IPv4/IPv6 address, no API key.",
        "repo_url": None,
        "docs_url": "https://rdap.org/",
        "examples": [{"label": "Public DNS resolver", "entity": "8.8.8.8"}],
        "variants": {
            "ip": {"variant_label": "Default", "speed": "~2-5s", "fast": True},
        },
        "options": [
            {
                "name": "sources", "flag": "sources", "type": "enum_multi", "required": False,
                "default": ["rdap", "geolocation"],
                "choices": ["rdap", "geolocation"],
                "description": (
                    "Which sources to query: RDAP (network allocation/ownership, official "
                    "registries) and/or geolocation (ip-api.com, approximate city-level)."
                ),
            },
        ],
        "native_reports": [],
        "version_check": {"method": "none"},
    },
    "recherche-entreprises": {
        "label": "Recherche d'entreprises",
        "entity_type": "company",
        "description": (
            "Searches France's official open company registry — name, SIREN/SIRET, address, "
            "legal status, officers — via the api.gouv.fr open data API, no API key."
        ),
        "repo_url": "https://github.com/annuaire-entreprises-data-gouv-fr/search-api",
        "docs_url": "https://recherche-entreprises.api.gouv.fr/docs",
        "examples": [
            {"label": "Well-known French retailer", "entity": "carrefour"},
            {"label": "Direct SIREN lookup", "entity": "652014051"},
        ],
        "variants": {
            "recherche-entreprises": {"variant_label": "Default", "speed": "~2s", "fast": True},
        },
        "options": [
            {
                "name": "nom_personne", "flag": "nom_personne", "type": "str", "required": False, "default": None,
                "description": (
                    "Last name of a director/officer or elected official — finds companies "
                    "linked to that person. Can be used with the entity field left blank."
                ),
            },
            {
                "name": "prenoms_personne", "flag": "prenoms_personne", "type": "str", "required": False, "default": None,
                "description": "First name(s) of a director/officer or elected official, refines nom_personne.",
            },
            {
                "name": "type_personne", "flag": "type_personne", "type": "enum", "required": False, "default": None,
                "choices": ["dirigeant", "elu"],
                "description": "Restrict the person search above to company officers or elected officials.",
            },
            {
                "name": "date_naissance_personne_min", "flag": "date_naissance_personne_min", "type": "str",
                "required": False, "default": None,
                "description": "Earliest birth date (YYYY-MM-DD) for the person search above.",
            },
            {
                "name": "date_naissance_personne_max", "flag": "date_naissance_personne_max", "type": "str",
                "required": False, "default": None,
                "description": "Latest birth date (YYYY-MM-DD) for the person search above.",
            },
            {
                "name": "code_postal", "flag": "code_postal", "type": "str", "required": False, "default": None,
                "description": (
                    "5-digit postal code, comma-separated for several. Matches any of the "
                    "company's establishments, not just its headquarters — the address shown "
                    "in results is always the headquarters, which can be a different location."
                ),
            },
            {
                "name": "code_commune", "flag": "code_commune", "type": "str", "required": False, "default": None,
                "description": "5-character INSEE commune code. Same establishment-level scope as code_postal.",
            },
            {
                "name": "departement", "flag": "departement", "type": "str", "required": False, "default": None,
                "description": "French department code (2-3 digits), e.g. \"75\" for Paris.",
            },
            {
                "name": "region", "flag": "region", "type": "str", "required": False, "default": None,
                "description": "2-digit INSEE region code.",
            },
            {
                "name": "etat_administratif", "flag": "etat_administratif", "type": "enum", "required": False,
                "default": None,
                "choices": ["A", "C"],
                "description": "Filter to Active (A) or Cessée/closed (C) companies. Omit for both.",
            },
            {
                "name": "categorie_entreprise", "flag": "categorie_entreprise", "type": "enum", "required": False,
                "default": None,
                "choices": ["PME", "ETI", "GE"],
                "description": "Company size category: small/medium (PME), mid-size (ETI), or large (GE).",
            },
            {
                "name": "nature_juridique", "flag": "nature_juridique", "type": "str", "required": False, "default": None,
                "description": (
                    "INSEE legal-form code (e.g. \"5710\" for a SAS), comma-separated for "
                    "several — see the docs link above for the full list."
                ),
            },
            {
                "name": "activite_principale", "flag": "activite_principale", "type": "str", "required": False,
                "default": None,
                "description": "NAF/APE activity code (e.g. \"62.01Z\"), comma-separated for several.",
            },
            {
                "name": "section_activite_principale", "flag": "section_activite_principale", "type": "str",
                "required": False, "default": None,
                "description": "Broad activity sector, a single letter A-U (e.g. \"J\" for information/communication).",
            },
            {
                "name": "tranche_effectif_salarie", "flag": "tranche_effectif_salarie", "type": "str",
                "required": False, "default": None,
                "description": "INSEE employee-count bracket code, comma-separated for several.",
            },
            {
                "name": "ca_min", "flag": "ca_min", "type": "int", "required": False, "default": None,
                "description": "Minimum annual revenue (euros).",
            },
            {
                "name": "ca_max", "flag": "ca_max", "type": "int", "required": False, "default": None,
                "description": "Maximum annual revenue (euros).",
            },
            {
                "name": "resultat_net_min", "flag": "resultat_net_min", "type": "int", "required": False, "default": None,
                "description": "Minimum net income (euros).",
            },
            {
                "name": "resultat_net_max", "flag": "resultat_net_max", "type": "int", "required": False, "default": None,
                "description": "Maximum net income (euros).",
            },
            {
                "name": "sort_by_size", "flag": "sort_by_size", "type": "bool", "required": False, "default": False,
                "description": "Sort results by company size (number of establishments) instead of relevance.",
            },
            {
                "name": "per_page", "flag": "per_page", "type": "int", "required": False,
                "default": 10, "min": 1, "max": 25,
                "description": "Results per page (the API's own hard cap is 25).",
            },
        ],
        "native_reports": [],
        "version_check": {"method": "none"},
    },
}
