"""Unit tests for the France recherche-entreprises registry adapter."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.registries.recherche import RechercheAdapter, _parse_recherche_response


# --- Fixtures (real recherche-entreprises API format) ---

RECHERCHE_RESULT = {
    "siren": "941953458",
    "nom_complet": "ALAN",
    "nom_raison_sociale": "ALAN",
    "nature_juridique": "5710",
    "etat_administratif": "A",
    "activite_principale": "65.12Z",
    "section_activite_principale": "K",
    "categorie_entreprise": "ETI",
    "tranche_effectif_salarie": "31",
    "date_mise_a_jour": "2025-01-15",
    "siege": {
        "adresse": "44 Rue Alexandre Dumas",
        "code_postal": "75011",
        "libelle_commune": "PARIS 11",
        "date_creation": "2016-02-23",
        "activite_principale": "65.12Z",
        "etat_administratif": "A",
    },
    "dirigeants": [
        {
            "nom": "HASCOET",
            "prenoms": "Jean-Charles",
            "qualite": "Président",
            "type_dirigeant": "personne physique",
        },
        {
            "siren": "123456789",
            "denomination": "Some Holding SAS",
            "qualite": "Directeur général",
            "type_dirigeant": "personne morale",
        },
    ],
}

RECHERCHE_SEARCH_RESPONSE = {
    "results": [RECHERCHE_RESULT],
    "total_results": 1,
    "page": 1,
    "per_page": 5,
    "total_pages": 1,
}


# --- Parser tests ---

class TestParseRechercheResponse:
    def test_full_response(self):
        result = _parse_recherche_response(RECHERCHE_RESULT)
        assert result["ico"] == "941953458"
        assert result["official_name"] == "ALAN"
        assert result["legal_form"] == "5710"
        assert result["legal_form_name"] == "SAS"
        assert result["date_established"] == "2016-02-23"
        assert result["address_city"] == "PARIS 11"
        assert result["address_postal_code"] == "75011"
        assert "44 Rue Alexandre Dumas" in result["registered_address"]
        assert result["registration_status"] == "active"
        assert len(result["nace_codes"]) == 1
        assert result["nace_codes"][0]["code"] == "65.12Z"
        # Only physical persons as directors
        assert len(result["directors"]) == 1
        assert result["directors"][0]["name"] == "Jean-Charles HASCOET"
        assert result["directors"][0]["role"] == "Président"
        assert result["_raw"] is RECHERCHE_RESULT

    def test_ceased_company(self):
        data = dict(RECHERCHE_RESULT)
        data["etat_administratif"] = "C"
        result = _parse_recherche_response(data)
        assert result["registration_status"] == "dissolved"

    def test_empty_response(self):
        result = _parse_recherche_response({})
        assert result["ico"] is None
        assert result["official_name"] is None
        assert result["nace_codes"] == []
        assert result["directors"] == []
        assert result["registration_status"] == "unknown"

    def test_no_directors(self):
        data = dict(RECHERCHE_RESULT)
        data["dirigeants"] = []
        result = _parse_recherche_response(data)
        assert result["directors"] == []

    def test_unknown_legal_form(self):
        data = dict(RECHERCHE_RESULT)
        data["nature_juridique"] = "9999"
        result = _parse_recherche_response(data)
        assert result["legal_form"] == "9999"
        assert result["legal_form_name"] == ""


# --- Adapter tests ---

class TestRechercheAdapter:
    def test_matches_france(self):
        adapter = RechercheAdapter()
        assert adapter.matches_company("France", None) is True
        assert adapter.matches_company("FR", None) is True
        assert adapter.matches_company(None, "alan.fr") is True
        assert adapter.matches_company("Germany", "firma.de") is False
        assert adapter.matches_company(None, None) is False

    def test_name_similarity_suffix_stripping(self):
        adapter = RechercheAdapter()
        assert adapter.name_similarity("Alan", "ALAN") == 1.0
        sim = adapter.name_similarity("Societe Generale", "SOCIETE GENERALE SA")
        assert sim == 1.0

    @patch("api.services.registries.recherche.requests.get")
    def test_lookup_by_id_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = RECHERCHE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        result = adapter.lookup_by_id("941953458")
        assert result["ico"] == "941953458"
        assert result["official_name"] == "ALAN"

    @patch("api.services.registries.recherche.requests.get")
    def test_lookup_no_match(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [], "total_results": 0}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        assert adapter.lookup_by_id("000000000") is None

    @patch("api.services.registries.recherche.requests.get")
    def test_lookup_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network error")

        adapter = RechercheAdapter()
        assert adapter.lookup_by_id("941953458") is None

    @patch("api.services.registries.recherche.requests.get")
    def test_search_by_name(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = RECHERCHE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        results = adapter.search_by_name("Alan")
        assert len(results) == 1
        assert results[0]["ico"] == "941953458"
        assert "similarity" in results[0]

    @patch("api.services.registries.recherche.requests.get")
    def test_search_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [], "total_results": 0}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = RechercheAdapter()
        assert adapter.search_by_name("XYZNONEXISTENT") == []
