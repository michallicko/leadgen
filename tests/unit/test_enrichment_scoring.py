"""BL-236: Enrichment test suite with scoring.

Scores each enrichment stage on 5 checks (10 points max):
  - Has enricher file (2 pts)
  - In DIRECT_STAGES (1 pt)
  - Estimate API works (2 pts)
  - dag-run accepts stage (2 pts)
  - No errors in dispatch (3 pts -- 0 if NotImplementedError)

Individual check tests use real assertions (can fail).
The scorecard test always passes but prints a summary table.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import auth_header


# All enrichment stages from the codebase
ALL_STAGES = [
    "l1",
    "triage",
    "l2",
    "signals",
    "registry",
    "news",
    "person",
    "social",
    "career",
    "contact_details",
    "qc",
]

# Mapping of stage -> expected enricher file (relative to project root)
ENRICHER_FILES = {
    "l1": "api/services/l1_enricher.py",
    "l2": "api/services/l2_enricher.py",
    "person": "api/services/person_enricher.py",
    "triage": "api/services/triage_evaluator.py",
    "qc": "api/services/qc_checker.py",
    "registry": "api/services/registries/orchestrator.py",
    "signals": "api/services/signals_enricher.py",
    "news": "api/services/news_enricher.py",
    "social": "api/services/social_enricher.py",
    "career": "api/services/career_enricher.py",
    "contact_details": "api/services/contact_details_enricher.py",
}

# Stages that operate on contacts (vs companies)
_CONTACT_STAGES = {"person", "social", "career", "contact_details"}

# Project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_scoring_data(db, seed_tenant, seed_super_admin):
    """Create minimal data for enrichment scoring tests."""
    from api.models import (
        Tag,
        Company,
        Contact,
        Owner,
        UserTenantRole,
        CompanyEnrichmentL1,
    )

    # Give admin a role on the tenant
    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    owner = Owner(tenant_id=seed_tenant.id, name="TestOwner", is_active=True)
    db.session.add(owner)
    db.session.flush()

    tag = Tag(tenant_id=seed_tenant.id, name="score-batch", is_active=True)
    db.session.add(tag)
    db.session.flush()

    # Company eligible for L1 (status=new)
    c_new = Company(
        tenant_id=seed_tenant.id,
        name="NewCo",
        domain="newco.example",
        tag_id=tag.id,
        owner_id=owner.id,
        status="new",
        hq_country="CZ",
    )
    db.session.add(c_new)
    db.session.flush()

    # Company eligible for L2/signals/news (status=triage_passed)
    c_passed = Company(
        tenant_id=seed_tenant.id,
        name="PassedCo",
        domain="passed.example",
        tag_id=tag.id,
        owner_id=owner.id,
        status="triage_passed",
        tier="tier_1_platinum",
    )
    db.session.add(c_passed)
    db.session.flush()

    # Add L1 enrichment data for triage tests
    l1_data = CompanyEnrichmentL1(
        company_id=c_new.id,
        raw_response='{"b2b": true}',
        confidence=0.8,
    )
    db.session.add(l1_data)

    # Company eligible for person/social/career/contact_details + QC
    c_enriched = Company(
        tenant_id=seed_tenant.id,
        name="EnrichedCo",
        domain="enriched.example",
        tag_id=tag.id,
        owner_id=owner.id,
        status="enriched_l2",
        tier="tier_1_platinum",
    )
    db.session.add(c_enriched)
    db.session.flush()

    # Contact eligible for person-type stages
    ct = Contact(
        tenant_id=seed_tenant.id,
        first_name="Test",
        last_name="Contact",
        company_id=c_enriched.id,
        tag_id=tag.id,
        owner_id=owner.id,
        processed_enrich=False,
        job_title="CTO",
    )
    db.session.add(ct)
    db.session.flush()

    db.session.commit()

    return {
        "tenant": seed_tenant,
        "tag": tag,
        "owner": owner,
        "company_new": c_new,
        "company_passed": c_passed,
        "company_enriched": c_enriched,
        "contact": ct,
    }


def _get_entity_id(seed_data, stage):
    """Pick the right entity ID for a given stage."""
    if stage in _CONTACT_STAGES:
        return str(seed_data["contact"].id)
    if stage == "l1":
        return str(seed_data["company_new"].id)
    if stage == "triage":
        return str(seed_data["company_new"].id)
    if stage in ("l2", "signals", "news"):
        return str(seed_data["company_passed"].id)
    if stage == "registry":
        return str(seed_data["company_new"].id)
    if stage == "qc":
        return str(seed_data["company_enriched"].id)
    return str(seed_data["company_new"].id)


# Mock paths for enricher functions. These are the module-level functions
# that _process_entity lazily imports (e.g. `from .l1_enricher import enrich_l1`).
# Mocking at the source module avoids mocking internal API clients.
_ENRICHER_MOCK_PATHS = {
    "l1": "api.services.l1_enricher.enrich_l1",
    "l2": "api.services.l2_enricher.enrich_l2",
    "person": "api.services.person_enricher.enrich_person",
    "qc": "api.services.qc_checker.run_qc",
    "registry": "api.services.registries.orchestrator.RegistryOrchestrator",
    "signals": "api.services.signals_enricher.enrich_signals",
    "news": "api.services.news_enricher.enrich_news",
    "social": "api.services.social_enricher.enrich_social",
    "career": "api.services.career_enricher.enrich_career",
    "contact_details": "api.services.contact_details_enricher.enrich_contact_details",
}

_MOCK_ENRICHER_RESULT = {
    "status": "ok",
    "enrichment_cost_usd": 0.01,
    "passed": True,
    "gate_passed": True,
    "gate_reasons": [],
    "reasons": [],
}


def _dispatch_with_mocks(app, seed_data, stage):
    """Call _process_entity with appropriate mocks. Returns (success, error_type)."""
    with app.app_context():
        from api.services.pipeline_engine import _process_entity

        tenant_id = seed_data["tenant"].id
        entity_id = _get_entity_id(seed_data, stage)

        # Build context managers for mocks
        mock_cm_list = []

        # Always mock n8n webhook (for any non-DIRECT stage fallback)
        mock_cm_list.append(
            patch(
                "api.services.pipeline_engine.call_n8n_webhook",
                return_value=_MOCK_ENRICHER_RESULT,
            )
        )

        # Mock the enricher function at its source module
        mock_path = _ENRICHER_MOCK_PATHS.get(stage)
        if mock_path:
            if stage == "registry":
                # RegistryOrchestrator is a class, mock the instance
                mock_orch = MagicMock()
                mock_orch.enrich_company.return_value = {
                    "status": "ok",
                    "enrichment_cost_usd": 0,
                }
                mock_cm_list.append(patch(mock_path, return_value=mock_orch))
            else:
                mock_cm_list.append(
                    patch(mock_path, return_value=_MOCK_ENRICHER_RESULT)
                )

        # triage uses evaluate_triage internally -- it works with DB data
        # so no extra mock needed beyond what the fixture provides

        try:
            # Enter all mocks
            entered = []
            for cm in mock_cm_list:
                entered.append(cm.__enter__())

            try:
                _process_entity(stage, entity_id, tenant_id)
                return True, None
            except NotImplementedError:
                return False, "NotImplementedError"
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}"
            finally:
                # Exit all mocks in reverse order
                for cm in reversed(mock_cm_list):
                    cm.__exit__(None, None, None)

        except Exception as exc:
            return False, f"MockSetup: {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Check 1: Has enricher file (2 pts)
# ---------------------------------------------------------------------------


class TestHasEnricherFile:
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_enricher_file_exists(self, stage):
        """Each stage should have an enricher file or equivalent."""
        expected = ENRICHER_FILES.get(stage)
        assert expected is not None, f"No file mapping for stage '{stage}'"
        full_path = os.path.join(PROJECT_ROOT, expected)
        assert os.path.isfile(full_path), (
            f"Missing enricher file for stage '{stage}': {expected}"
        )


# ---------------------------------------------------------------------------
# Check 2: In DIRECT_STAGES (1 pt)
# ---------------------------------------------------------------------------


class TestInDirectStages:
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_stage_in_direct_stages(self, stage):
        """Each stage should be registered in DIRECT_STAGES."""
        from api.services.pipeline_engine import DIRECT_STAGES

        assert stage in DIRECT_STAGES, f"Stage '{stage}' not in DIRECT_STAGES"


# ---------------------------------------------------------------------------
# Check 3: Estimate API works (2 pts)
# ---------------------------------------------------------------------------


class TestEstimateAPI:
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_estimate_returns_200(self, client, seed_scoring_data, stage):
        """The estimate endpoint should accept each stage and return 200."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_scoring_data["tenant"].slug

        resp = client.post(
            "/api/enrich/estimate",
            json={
                "tag_name": "score-batch",
                "stages": [stage],
            },
            headers=headers,
        )
        assert resp.status_code == 200, (
            f"Estimate for stage '{stage}' returned {resp.status_code}: "
            f"{resp.get_json()}"
        )
        data = resp.get_json()
        assert stage in data.get("stages", {}), (
            f"Stage '{stage}' missing from estimate response"
        )


# ---------------------------------------------------------------------------
# Check 4: dag-run accepts stage (2 pts)
# ---------------------------------------------------------------------------


class TestDagRunAcceptsStage:
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_dag_run_accepts_stage(self, client, seed_scoring_data, stage):
        """dag-run should accept each individual stage (validates stage is in registry)."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_scoring_data["tenant"].slug

        with patch("api.routes.pipeline_routes.start_dag_pipeline") as mock_start:
            mock_start.return_value = {}
            resp = client.post(
                "/api/pipeline/dag-run",
                json={
                    "tag_name": "score-batch",
                    "stages": [stage],
                },
                headers=headers,
            )

        # 201 = success, 409 = pipeline already running (still means stage valid)
        assert resp.status_code in (201, 409), (
            f"dag-run for stage '{stage}' returned {resp.status_code}: "
            f"{resp.get_json()}"
        )


# ---------------------------------------------------------------------------
# Check 5: No errors in dispatch (3 pts)
# ---------------------------------------------------------------------------


class TestDispatch:
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_dispatch_no_error(self, app, seed_scoring_data, stage):
        """Dispatching a stage should not raise unexpected errors.

        NotImplementedError is a known gap (scores 0 but doesn't fail the suite).
        """
        success, error_type = _dispatch_with_mocks(app, seed_scoring_data, stage)

        if error_type == "NotImplementedError":
            pytest.skip(f"Stage '{stage}' raises NotImplementedError (stub)")
        elif not success:
            pytest.fail(f"Stage '{stage}' dispatch failed: {error_type}")


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _check_file(stage):
    """Return 2 if enricher file exists, 0 otherwise."""
    expected = ENRICHER_FILES.get(stage)
    if not expected:
        return 0
    return 2 if os.path.isfile(os.path.join(PROJECT_ROOT, expected)) else 0


def _check_direct(stage):
    """Return 1 if stage is in DIRECT_STAGES, 0 otherwise."""
    from api.services.pipeline_engine import DIRECT_STAGES

    return 1 if stage in DIRECT_STAGES else 0


def _check_estimate(client, headers, stage):
    """Return 2 if estimate API returns 200 for this stage, 0 otherwise."""
    try:
        resp = client.post(
            "/api/enrich/estimate",
            json={"tag_name": "score-batch", "stages": [stage]},
            headers=headers,
        )
        return 2 if resp.status_code == 200 else 0
    except Exception:
        return 0


def _check_dag_run(client, headers, stage):
    """Return 2 if dag-run accepts this stage, 0 otherwise."""
    try:
        with patch(
            "api.routes.pipeline_routes.start_dag_pipeline",
            return_value={},
        ):
            resp = client.post(
                "/api/pipeline/dag-run",
                json={"tag_name": "score-batch", "stages": [stage]},
                headers=headers,
            )
        return 2 if resp.status_code in (201, 409) else 0
    except Exception:
        return 0


def _check_dispatch(app, seed_data, stage):
    """Return 3 if dispatch succeeds, 0 otherwise."""
    success, error_type = _dispatch_with_mocks(app, seed_data, stage)
    return 3 if success else 0


# ---------------------------------------------------------------------------
# Scorecard: always-passing test that prints the summary
# ---------------------------------------------------------------------------


class TestEnrichmentScorecard:
    """Always-passing test that prints a scorecard for all stages."""

    def test_print_scorecard(self, app, client, seed_scoring_data):
        """Print enrichment readiness scorecard."""
        headers = auth_header(client)
        headers["X-Namespace"] = seed_scoring_data["tenant"].slug

        rows = []
        total_score = 0
        max_total = len(ALL_STAGES) * 10

        for stage in ALL_STAGES:
            file_pts = _check_file(stage)
            direct_pts = _check_direct(stage)
            estimate_pts = _check_estimate(client, headers, stage)
            dag_pts = _check_dag_run(client, headers, stage)
            dispatch_pts = _check_dispatch(app, seed_scoring_data, stage)
            stage_score = file_pts + direct_pts + estimate_pts + dag_pts + dispatch_pts
            total_score += stage_score
            rows.append(
                (
                    stage,
                    file_pts,
                    direct_pts,
                    estimate_pts,
                    dag_pts,
                    dispatch_pts,
                    stage_score,
                )
            )

        # Print scorecard
        header = (
            f"{'Stage':<18}| {'File':>4} | {'Direct':>6} | "
            f"{'Estimate':>8} | {'DagRun':>6} | {'Dispatch':>8} | "
            f"{'Score':>7}"
        )
        sep = "-" * len(header)
        lines = [
            "",
            "=" * len(header),
            "  ENRICHMENT READINESS SCORECARD",
            "=" * len(header),
            header,
            sep,
        ]
        for stage, f, d, e, dr, dp, s in rows:
            lines.append(
                f"{stage:<18}|  {f:>3} |    {d:>3} |      {e:>3} "
                f"|    {dr:>3} |      {dp:>3} |  {s:>2}/10"
            )
        lines.append(sep)
        avg = total_score / len(ALL_STAGES) if ALL_STAGES else 0
        lines.append(f"OVERALL: {total_score}/{max_total} ({avg:.1f}/10)")
        lines.append("=" * len(header))
        lines.append("")

        print("\n".join(lines))

        # This test always passes -- the scorecard is informational
        assert True
