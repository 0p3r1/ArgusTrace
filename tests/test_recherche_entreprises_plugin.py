import json

from argustrace.core.models import Status
from argustrace.plugins.recherche_entreprises_plugin import RechercheEntreprisesPlugin


async def test_blank_entity_returns_error_without_touching_docker():
    plugin = RechercheEntreprisesPlugin()
    findings = await plugin.run("   ")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_blank_entity_with_no_filters_is_still_an_error():
    plugin = RechercheEntreprisesPlugin()
    findings = await plugin.run("", options={})

    assert findings[0].status == Status.ERROR


def test_has_any_filter_true_when_a_person_filter_is_set():
    plugin = RechercheEntreprisesPlugin()
    assert plugin._has_any_filter({"nom_personne": "Martin"}) is True


def test_has_any_filter_false_when_nothing_meaningful_is_set():
    plugin = RechercheEntreprisesPlugin()
    assert plugin._has_any_filter({}) is False
    assert plugin._has_any_filter({"nom_personne": "", "sort_by_size": False}) is False


def test_build_url_allows_blank_q_when_a_filter_is_present():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("", {"nom_personne": "Martin", "prenoms_personne": "Jean"})

    assert "q=" in url
    assert "nom_personne=Martin" in url
    assert "prenoms_personne=Jean" in url


def test_parse_response_empty_results_is_not_found():
    plugin = RechercheEntreprisesPlugin()
    stdout = json.dumps({"results": [], "total_results": 0})

    findings = plugin._parse_response("zzznonexistent", stdout)

    assert len(findings) == 1
    assert findings[0].status == Status.NOT_FOUND


def test_parse_response_non_json_is_error():
    plugin = RechercheEntreprisesPlugin()
    findings = plugin._parse_response("carrefour", "<html>not json</html>")

    assert findings[0].status == Status.ERROR


def test_to_finding_maps_fields_and_is_always_found_regardless_of_etat():
    plugin = RechercheEntreprisesPlugin()
    result = {
        "siren": "652014051",
        "nom_complet": "CARREFOUR",
        "siege": {"adresse": "93 AVENUE DE PARIS 91300 MASSY"},
        "activite_principale": "64.20Z",
        "categorie_entreprise": "GE",
        "date_creation": "1963-01-01",
        "etat_administratif": "C",  # closed — still a real, found record
        "dirigeants": [{"nom": "DUPONT", "prenoms": "JEAN", "qualite": "Président"}],
    }

    finding = plugin._to_finding("carrefour", result)

    assert finding.status == Status.FOUND
    assert finding.source == "recherche-entreprises:652014051"
    assert finding.url == "https://annuaire-entreprises.data.gouv.fr/entreprise/652014051"
    assert finding.evidence["etat_administratif"] == "C"
    assert finding.evidence["dirigeants"][0]["nom"] == "DUPONT"
    assert finding.evidence["headline"] == "CARREFOUR · 93 AVENUE DE PARIS 91300 MASSY"


def test_parse_response_builds_one_finding_per_result():
    plugin = RechercheEntreprisesPlugin()
    stdout = json.dumps({"results": [
        {"siren": "111", "nom_complet": "A", "siege": {}, "dirigeants": []},
        {"siren": "222", "nom_complet": "B", "siege": {}, "dirigeants": []},
    ]})

    findings = plugin._parse_response("test", stdout)

    assert len(findings) == 2
    assert {f.source for f in findings} == {"recherche-entreprises:111", "recherche-entreprises:222"}


def test_build_url_includes_valid_filters_only():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("carrefour", {"etat_administratif": "A", "departement": "75", "per_page": 5})

    assert "q=carrefour" in url
    assert "etat_administratif=A" in url
    assert "departement=75" in url
    assert "per_page=5" in url


def test_build_url_ignores_invalid_etat_administratif():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("carrefour", {"etat_administratif": "bogus"})

    assert "etat_administratif" not in url


def test_build_url_clamps_per_page_to_api_limit():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("carrefour", {"per_page": 999})

    assert "per_page=25" in url


def test_build_url_uses_default_per_page_when_absent():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("carrefour", {})

    assert "per_page=10" in url


def test_build_url_includes_person_and_location_filters():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("", {
        "nom_personne": "Martin", "prenoms_personne": "Jean", "type_personne": "dirigeant",
        "code_postal": "75001", "categorie_entreprise": "PME", "ca_min": 100000, "sort_by_size": True,
    })

    assert "nom_personne=Martin" in url
    assert "prenoms_personne=Jean" in url
    assert "type_personne=dirigeant" in url
    assert "code_postal=75001" in url
    assert "categorie_entreprise=PME" in url
    assert "ca_min=100000" in url
    assert "sort_by_size=true" in url


def test_build_url_ignores_invalid_enum_and_int_values():
    plugin = RechercheEntreprisesPlugin()
    url = plugin._build_url("carrefour", {"type_personne": "bogus", "ca_min": "not-a-number"})

    assert "type_personne" not in url
    assert "ca_min" not in url


def test_to_finding_includes_coordinates_and_true_labels_only():
    plugin = RechercheEntreprisesPlugin()
    result = {
        "siren": "652014051",
        "nom_complet": "CARREFOUR",
        "siege": {"adresse": "93 AVENUE DE PARIS 91300 MASSY", "latitude": "48.72", "longitude": "2.26"},
        "nombre_etablissements": 7,
        "nombre_etablissements_ouverts": 1,
        "complements": {"est_ess": True, "est_bio": False, "est_association": True},
        "dirigeants": [],
    }

    finding = plugin._to_finding("carrefour", result)

    assert finding.evidence["coordinates"] == "48.72,2.26"
    assert set(finding.evidence["labels"]) == {"est_ess", "est_association"}
    assert finding.evidence["nombre_etablissements"] == 7


def test_to_finding_omits_coordinates_when_siege_has_no_geolocation():
    plugin = RechercheEntreprisesPlugin()
    result = {"siren": "1", "nom_complet": "A", "siege": {"adresse": "somewhere"}, "dirigeants": []}

    finding = plugin._to_finding("a", result)

    assert "coordinates" not in finding.evidence
