"""Credibility score computation for company legal profiles.

Pure function — no DB access, no side effects. Takes a unified profile dict
and returns a score (0-100) with factor breakdown.
"""

from datetime import date, datetime


def compute_credibility(profile_data):
    """Compute credibility score from unified legal profile data.

    Args:
        profile_data: dict with keys matching company_legal_profile columns:
            registration_id, match_confidence, registration_status,
            insolvency_flag, active_insolvency_count, date_established,
            official_name, legal_form, registered_address, nace_codes,
            registered_capital, directors

    Returns:
        {"score": int (0-100), "factors": dict of component scores}
    """
    factors = {}

    factors["registration_verified"] = _score_registration(
        profile_data.get("registration_id"),
        profile_data.get("match_confidence"),
    )

    factors["active_status"] = _score_status(
        profile_data.get("registration_status"),
    )

    factors["no_insolvency"] = _score_insolvency(
        profile_data.get("insolvency_flag", False),
        profile_data.get("active_insolvency_count", 0),
        profile_data.get("insolvency_details", []),
    )

    factors["business_history"] = _score_history(
        profile_data.get("date_established"),
    )

    factors["data_completeness"] = _score_completeness(profile_data)

    factors["directors_known"] = _score_directors(
        profile_data.get("directors", []),
    )

    score = sum(factors.values())
    return {"score": min(score, 100), "factors": factors}


def _score_registration(registration_id, confidence):
    """Registration verified: 0-25 points."""
    if not registration_id:
        return 0
    if confidence is None:
        return 10
    conf = float(confidence)
    if conf >= 0.95:
        return 25
    if conf >= 0.85:
        return 20
    if conf >= 0.60:
        return 10
    return 5


def _score_status(status):
    """Active status: 0-20 points."""
    if not status:
        return 5
    s = str(status).lower()
    if s == "active":
        return 20
    if s in ("unknown", ""):
        return 5
    # dissolved, liquidation, etc.
    return 0


def _score_insolvency(flag, active_count, details):
    """No insolvency: 0-20 points."""
    if not flag and active_count == 0:
        return 20
    # Has proceedings but none active — historical only
    if active_count == 0 and details:
        return 10
    # Active insolvency
    return 0


def _score_history(date_established):
    """Business history: 0-15 points."""
    if not date_established:
        return 0

    if isinstance(date_established, str):
        try:
            est = datetime.strptime(date_established[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return 0
    elif isinstance(date_established, datetime):
        est = date_established.date()
    elif isinstance(date_established, date):
        est = date_established
    else:
        return 0

    today = date.today()
    age_days = (today - est).days
    age_years = age_days / 365.25

    if age_years >= 10:
        return 15
    if age_years >= 5:
        return 12
    if age_years >= 2:
        return 8
    if age_years >= 1:
        return 5
    return 2


def _score_completeness(profile_data):
    """Data completeness: 0-10 points."""
    fields = [
        "official_name",
        "legal_form",
        "registered_address",
        "nace_codes",
        "registered_capital",
        "date_established",
    ]
    filled = 0
    for f in fields:
        val = profile_data.get(f)
        if val is not None and val != "" and val != []:
            filled += 1

    if len(fields) == 0:
        return 0
    ratio = filled / len(fields)
    return round(ratio * 10)


def _score_directors(directors):
    """Directors known: 0-10 points."""
    if not directors:
        return 0
    if isinstance(directors, list) and len(directors) > 0:
        return 10
    return 0
