# The Recherche d'entreprises plugin

Searches France's official, fully open company registry via
[`recherche-entreprises.api.gouv.fr`](https://recherche-entreprises.api.gouv.fr/docs)
([source](https://github.com/annuaire-entreprises-data-gouv-fr/search-api) —
confirmed by fetching the file the API's own OpenAPI docs link into from
that exact repo, not assumed) — genuinely zero authentication (verified
directly; INSEE's own Sirene API requires a self-service token, this newer
government API doesn't). Accepts a company name, SIREN, or SIRET as the
entity (the API's own full-text search handles all three) and returns one
`Finding` per matching company: SIREN, address, coordinates, legal form,
activity code, size, VAT number, true certification/label flags, and —
when the public record includes it — officers/directors (`dirigeants`).

A result being present always means `FOUND`, regardless of whether the
company is administratively active or closed (`etat_administratif`) —
closed is a fact about a real record, not the same thing as "no match,"
which is what `NOT_FOUND` (an empty `results` array) actually means.

The entity field can be left blank if at least one filter below is set —
verified directly against the API, e.g. `nom_personne` alone genuinely
finds companies by a director's name with no name/SIREN typed in. Exposed
options cover every meaningful search axis the API has: person
(`nom_personne`, `prenoms_personne`, `type_personne`, birth-date range),
location (`code_postal`, `code_commune`, `departement`, `region` — the
postal/commune filters match _any_ establishment, while the address shown
in results is always the headquarters, which can be a different one),
legal identity (`etat_administratif`, `categorie_entreprise`,
`nature_juridique`, `activite_principale`, `section_activite_principale`,
`tranche_effectif_salarie`), and financials (`ca_min`/`ca_max`,
`resultat_net_min`/`resultat_net_max`), plus `sort_by_size` and `per_page`
(the API's own hard cap is 25). The ~20 narrow certification/label filters
(`est_bio`, `est_qualiopi`, `egapro_renseignee`, ...) are deliberately left
out — a different search paradigm ("has label X") than what this tool is
for — but any that are `true` for a result still show up in its own
`labels` evidence.

Belgium, Switzerland, and Germany were investigated too — Switzerland's
Zefix needs free but self-registered API credentials (a new pattern this
project hasn't taken on yet), and no equivalent zero-auth, real-time API
was found for Belgium or Germany, so only France is covered for now.
