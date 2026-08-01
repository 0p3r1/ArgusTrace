import json
from urllib.parse import urlencode

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-curl:1.0"
RUN_TIMEOUT_S = 25
BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"

DEFAULT_PER_PAGE = 10
PER_PAGE_MIN = 1
PER_PAGE_MAX = 25  # the API's own hard cap

# Free-text/code filters passed straight through when non-blank — each
# already accepts a single value or a comma-separated list on the API's
# side, so no local validation beyond "don't send blank values".
SIMPLE_STR_PARAMS = [
    "activite_principale", "code_postal", "code_commune", "departement", "region",
    "nature_juridique", "section_activite_principale", "tranche_effectif_salarie",
    "nom_personne", "prenoms_personne", "date_naissance_personne_min", "date_naissance_personne_max",
]

ENUM_PARAMS = {
    "etat_administratif": {"A", "C"},
    "categorie_entreprise": {"PME", "ETI", "GE"},
    "type_personne": {"dirigeant", "elu"},
}

INT_PARAMS = ["ca_min", "ca_max", "resultat_net_min", "resultat_net_max"]

BOOL_PARAMS = ["sort_by_size"]


class RechercheEntreprisesPlugin:
    name = "recherche-entreprises"
    supported_entities = ["company"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        options = options or {}
        # The API itself supports an empty q as long as at least one other
        # filter is set (verified directly) — e.g. nom_personne/prenoms_personne
        # alone genuinely finds companies. Only reject when there's truly
        # nothing to search on.
        if (not entity or not entity.strip()) and not self._has_any_filter(options):
            return [self._error(
                entity,
                "invalid entity: company name, SIREN, or SIRET must not be empty "
                "unless at least one option (e.g. nom_personne) is set",
            )]

        url = self._build_url(entity, options)
        result = await run_hardened(IMAGE, [url], timeout_s=RUN_TIMEOUT_S)
        if not result.ok:
            return [self._error(entity, result.error)]
        if result.returncode != 0:
            return [self._error(entity, f"curl failed: {result.stderr.decode(errors='replace')[:300]}")]

        return self._parse_response(entity, result.stdout.decode(errors="replace"))

    def _has_any_filter(self, options: dict) -> bool:
        all_param_names = [*SIMPLE_STR_PARAMS, *ENUM_PARAMS, *INT_PARAMS, *BOOL_PARAMS]
        return any(options.get(name) not in (None, "", False) for name in all_param_names)

    def _build_url(self, entity: str, options: dict) -> str:
        params = {"q": entity}

        for name in SIMPLE_STR_PARAMS:
            value = options.get(name)
            if isinstance(value, str) and value.strip():
                params[name] = value.strip()

        for name, choices in ENUM_PARAMS.items():
            value = options.get(name)
            if value in choices:
                params[name] = value

        for name in INT_PARAMS:
            value = options.get(name)
            if value is None or value == "":
                continue
            try:
                params[name] = int(value)
            except (TypeError, ValueError):
                pass

        for name in BOOL_PARAMS:
            if options.get(name):
                params[name] = "true"

        try:
            per_page = int(options.get("per_page", DEFAULT_PER_PAGE))
        except (TypeError, ValueError):
            per_page = DEFAULT_PER_PAGE
        params["per_page"] = max(PER_PAGE_MIN, min(PER_PAGE_MAX, per_page))

        return f"{BASE_URL}?{urlencode(params)}"

    def _parse_response(self, entity: str, stdout: str) -> list[Finding]:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return [self._error(entity, "recherche-entreprises returned a non-JSON response")]

        results = data.get("results")
        if results is None:
            return [self._error(entity, data.get("message") or data.get("detail") or "unexpected response shape")]

        if not results:
            return [Finding(
                entity=entity, entity_type="company", source="recherche-entreprises",
                status=Status.NOT_FOUND, evidence={"reason": "no company matches this query"},
            )]

        return [self._to_finding(entity, r) for r in results]

    def _to_finding(self, entity: str, r: dict) -> Finding:
        siege = r.get("siege") or {}
        dirigeants = r.get("dirigeants") or []
        complements = r.get("complements") or {}

        # Most "complements" fields are certification/label booleans that
        # are false for the overwhelming majority of companies — only worth
        # surfacing the ones that are actually true for this result.
        labels = [k for k, v in complements.items() if v is True]

        coordinates = None
        if siege.get("latitude") and siege.get("longitude"):
            coordinates = f"{siege['latitude']},{siege['longitude']}"

        nom_complet = r.get("nom_complet")
        adresse = siege.get("adresse")

        evidence = {
            "siren": r.get("siren"),
            "nom_complet": nom_complet,
            "headline": " · ".join(p for p in (nom_complet, adresse) if p) or None,
            "sigle": r.get("sigle"),
            "adresse": adresse,
            "coordinates": coordinates,
            "activite_principale": r.get("activite_principale"),
            "categorie_entreprise": r.get("categorie_entreprise"),
            "nature_juridique": r.get("nature_juridique"),
            "date_creation": r.get("date_creation"),
            "date_fermeture": r.get("date_fermeture"),
            "tranche_effectif_salarie": r.get("tranche_effectif_salarie"),
            "etat_administratif": r.get("etat_administratif"),
            "nombre_etablissements": r.get("nombre_etablissements"),
            "nombre_etablissements_ouverts": r.get("nombre_etablissements_ouverts"),
            "tva": r.get("tva"),
            "labels": labels,
            "dirigeants": dirigeants,
        }
        evidence = {k: v for k, v in evidence.items() if v not in (None, "", [])}

        # A result being present at all means the company record was found —
        # closed ("C") vs active ("A") is a fact about that record, not a
        # reason to call it NOT_FOUND (that's reserved for "no match at all").
        siren = r.get("siren")
        return Finding(
            entity=entity,
            entity_type="company",
            source=f"recherche-entreprises:{siren}",
            status=Status.FOUND,
            url=f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}" if siren else None,
            evidence=evidence,
        )

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity, entity_type="company", source="recherche-entreprises",
            status=Status.ERROR, evidence={"reason": reason},
        )
