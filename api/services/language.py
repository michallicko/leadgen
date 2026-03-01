"""Language resolution cascade for namespace-level language settings.

Resolution order:
  campaign.generation_config.language  (if set)
    -> owner.default_language          (if set)
      -> tenant.settings.language      (if set)
        -> "en"                        (fallback)
"""

from ..display import LANGUAGE_NAMES

DEFAULT_LANGUAGE = "en"
VALID_LANGUAGE_CODES = set(LANGUAGE_NAMES.keys())


def get_effective_language(tenant, owner=None, campaign=None):
    """Resolve the effective language from the cascade.

    Args:
        tenant: Tenant model instance (has .settings JSONB).
        owner: Optional Owner model instance (has .default_language).
        campaign: Optional Campaign model instance (has .generation_config JSONB).

    Returns:
        str: Two-letter language code (e.g. "en", "de", "cs").
    """
    # Campaign override (highest priority)
    if campaign:
        gen_config = getattr(campaign, "generation_config", None)
        if isinstance(gen_config, dict):
            lang = gen_config.get("language")
            if lang and lang in VALID_LANGUAGE_CODES:
                return lang

    # Owner default
    if owner:
        lang = getattr(owner, "default_language", None)
        if lang and lang in VALID_LANGUAGE_CODES:
            return lang

    # Tenant (namespace) setting
    if tenant:
        settings = getattr(tenant, "settings", None) or {}
        lang = settings.get("language")
        if lang and lang in VALID_LANGUAGE_CODES:
            return lang

    return DEFAULT_LANGUAGE


def get_enrichment_language(tenant, owner=None):
    """Resolve the enrichment-specific language.

    Enrichment may use a different language than the workspace default
    (e.g., Czech UI but English enrichment research).

    Args:
        tenant: Tenant model instance.
        owner: Optional Owner model instance.

    Returns:
        str: Two-letter language code for enrichment output.
    """
    if tenant:
        settings = getattr(tenant, "settings", None) or {}
        enrichment_lang = settings.get("enrichment_language")
        if enrichment_lang and enrichment_lang in VALID_LANGUAGE_CODES:
            return enrichment_lang

    # Fall back to effective language
    return get_effective_language(tenant, owner=owner)


def get_language_name(code):
    """Get the full English name for a language code.

    Args:
        code: Two-letter language code (e.g. "de").

    Returns:
        str: Full name (e.g. "German"). Returns the code if unknown.
    """
    return LANGUAGE_NAMES.get(code, code)
