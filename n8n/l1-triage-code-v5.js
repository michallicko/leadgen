// ============================================================================
// STAGE A — TRIAGE: Research QC + Tier Requalification (v5 — Postgres)
// ============================================================================
// Mode:   Run Once for Each Item
// After:  Perplexity basic research
// Input:  Perplexity response ($('Basic Company Reseach'))
//         + Postgres record ($('Read Company'))
// Output: verdict + corrected tier + Postgres-ready fields
//         + research_directory scores
// Next:   Update Company → Save Research Asset
// ============================================================================

const original = $('Read Company').item.json;
const perplexity = $('Basic Company Reseach').item.json;
const rawContent = perplexity.choices?.[0]?.message?.content || '';
const researchCost = perplexity.usage?.cost?.total_cost || 0;
const model = perplexity.model || 'unknown';

// -----------------------------------------------------------------------
// 1. PARSE RESEARCH JSON
// -----------------------------------------------------------------------
let research = null;
let parseError = false;

try {
  let cleaned = rawContent.trim();
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '');
  }
  research = JSON.parse(cleaned);
} catch (e) {
  parseError = true;
}

if (parseError || !research) {
  return {
    record_id: original.id,
    company_name: original.name || 'Unknown',
    triage_verdict: 'manual_review',
    pg_status: 'triage_review',
    pg_triage_notes: `PARSE_ERROR: Failed to parse Perplexity response (${rawContent.length} chars). Manual research needed.`,
    pg_triage_score: 0,
    research_quality_score: 0,
    research_confidence_score: 0,
    pg_enrichment_cost: (parseFloat(original.enrichment_cost_usd) || 0) + researchCost,
    raw_research: rawContent
  };
}

// -----------------------------------------------------------------------
// 2. HELPERS
// -----------------------------------------------------------------------
function parseRevenue(raw) {
  if (!raw || raw === 'unverified' || raw === 'Unknown' || raw === 'N/A' || raw === 'null') return null;
  const str = String(raw).toLowerCase().replace(/[€$£,\s]/g, '');
  let match = str.match(/([\d.]+)\s*(b|billion)/i);
  if (match) return parseFloat(match[1]) * 1000;
  match = str.match(/([\d.]+)\s*(m|million)/i);
  if (match) return parseFloat(match[1]);
  match = str.match(/^([\d.]+)$/);
  if (match) {
    const val = parseFloat(match[1]);
    if (val > 1000000) return val / 1000000;
    return val;
  }
  return null;
}

function parseEmployees(raw) {
  if (!raw || raw === 'unverified' || raw === 'Unknown' || raw === 'N/A' || raw === 'null') return null;
  const str = String(raw).replace(/[,\s+]/g, '');
  let match = str.match(/(\d+)-(\d+)/);
  if (match) return Math.round((parseInt(match[1]) + parseInt(match[2])) / 2);
  match = str.match(/(\d+)\+?/);
  if (match) return parseInt(match[1]);
  return null;
}

// Parse PG revenue_range enum to numeric range
function parseLinkedInRevenue(raw) {
  if (!raw) return null;
  const str = String(raw);
  const ranges = {
    'micro':      { min: 0, max: 2 },
    'small':      { min: 2, max: 10 },
    'medium':     { min: 10, max: 50 },
    'mid_market': { min: 50, max: 500 },
    'enterprise': { min: 500, max: 50000 },
  };
  return ranges[str] || null;
}

// Parse PG company_size enum to numeric range
function parseLinkedInEmployees(raw) {
  if (!raw) return null;
  const str = String(raw);
  const ranges = {
    'micro':      { min: 1, max: 20 },
    'startup':    { min: 20, max: 49 },
    'smb':        { min: 50, max: 199 },
    'mid_market': { min: 200, max: 1999 },
    'enterprise': { min: 2000, max: 50000 },
  };
  return ranges[str] || null;
}

// Geo cluster from HQ only
function deriveGeoCluster(hq) {
  const text = (hq || '').toLowerCase();
  if (/czech|slovakia|poland|hungary|romania|bulgaria|croatia|slovenia|serbia|bosnia|albania|north macedonia|moldova|montenegro|kosovo|estonia|latvia|lithuania/i.test(text)) return 'cee';
  if (/germany|austria|switzerland|liechtenstein/i.test(text)) return 'dach';
  if (/sweden|norway|denmark|finland|iceland/i.test(text)) return 'nordics';
  if (/netherlands|belgium|luxembourg/i.test(text)) return 'benelux';
  if (/uk|united kingdom|england|scotland|wales|ireland/i.test(text)) return 'uk_ireland';
  if (/spain|italy|portugal|greece|malta|cyprus/i.test(text)) return 'southern_europe';
  if (/united states|usa|us\b|america/i.test(text)) return 'us';
  return 'other';
}

// Returns PG tier enum value
function formatTier(tier) {
  const map = {
    'Platinum':      'tier_1_platinum',
    'Gold':          'tier_2_gold',
    'Silver':        'tier_3_silver',
    'Bronze':        'tier_4_bronze',
    'Copper':        'tier_5_copper',
    'Deprioritized': 'deprioritize',
  };
  return map[tier] || null;
}

// Returns PG revenue_range enum value
function revenueToBucket(revM) {
  if (revM === null) return null;
  if (revM < 2) return 'micro';
  if (revM < 10) return 'small';
  if (revM < 50) return 'medium';
  if (revM < 500) return 'mid_market';
  return 'enterprise';
}

// Returns PG company_size enum value
function employeesToBucket(emp) {
  if (emp === null) return null;
  if (emp < 20) return 'micro';
  if (emp < 50) return 'startup';
  if (emp < 200) return 'smb';
  if (emp < 2000) return 'mid_market';
  return 'enterprise';
}

// Returns PG ownership_type enum value
function mapOwnership(raw) {
  if (!raw || raw.toLowerCase() === 'unknown') return null;
  const l = raw.toLowerCase();
  if (l.includes('family')) return 'family_owned';
  if (l.includes('pe') || l.includes('private equity') || l.includes('backed')) return 'pe_backed';
  if (l.includes('vc') || l.includes('venture')) return 'vc_backed';
  if (l.includes('public') || l.includes('listed')) return 'public';
  if (l.includes('state') || l.includes('government')) return 'state_owned';
  if (l.includes('founder') || l.includes('bootstrap')) return 'bootstrapped';
  if (l.includes('subsidiary')) return 'other';
  return 'other';
}

// Display-format tier for triage notes (human-readable)
function displayTier(pgTier) {
  const map = {
    'tier_1_platinum': 'Tier 1 - Platinum',
    'tier_2_gold':     'Tier 2 - Gold',
    'tier_3_silver':   'Tier 3 - Silver',
    'tier_4_bronze':   'Tier 4 - Bronze',
    'tier_5_copper':   'Tier 5 - Copper',
    'deprioritize':    'Deprioritize',
  };
  return map[pgTier] || pgTier;
}

// -----------------------------------------------------------------------
// 3. EXTRACT & NORMALIZE
// -----------------------------------------------------------------------
const flags = [];
const contradictions = [];

const researchRevenue = parseRevenue(research.revenue_eur_m);
const researchEmployees = parseEmployees(research.employees);
const researchConfidence = (research.confidence || 'low').toLowerCase();

const linkedinRevRange = parseLinkedInRevenue(original.revenue_range);
const linkedinEmpRange = parseLinkedInEmployees(original.company_size);

const isB2B = research.b2b === true;

// Import model-reported flags
if (Array.isArray(research.flags)) {
  for (const f of research.flags) {
    if (f && typeof f === 'string' && f.trim().length > 0) {
      flags.push('MODEL: ' + f.trim());
    }
  }
}

// -----------------------------------------------------------------------
// 4. CONTRADICTION DETECTION
// -----------------------------------------------------------------------

if (researchRevenue !== null && linkedinRevRange) {
  if (researchRevenue > linkedinRevRange.max * 3) {
    contradictions.push({
      field: 'revenue', severity: 'critical',
      detail: `Research €${researchRevenue}M vs LinkedIn €${linkedinRevRange.min}-${linkedinRevRange.max}M (${Math.round(researchRevenue / linkedinRevRange.max)}x higher)`
    });
    flags.push('REVENUE_MISMATCH_HIGH');
  } else if (linkedinRevRange.min > 0 && researchRevenue < linkedinRevRange.min * 0.3) {
    contradictions.push({
      field: 'revenue', severity: 'critical',
      detail: `Research €${researchRevenue}M vs LinkedIn €${linkedinRevRange.min}-${linkedinRevRange.max}M (significantly lower)`
    });
    flags.push('REVENUE_MISMATCH_LOW');
  }
}

if (researchEmployees !== null && linkedinEmpRange) {
  if (researchEmployees > linkedinEmpRange.max * 3) {
    contradictions.push({
      field: 'employees', severity: 'warning',
      detail: `Research ${researchEmployees} vs LinkedIn ${linkedinEmpRange.min}-${linkedinEmpRange.max}`
    });
    flags.push('EMPLOYEE_MISMATCH_HIGH');
  } else if (researchEmployees < linkedinEmpRange.min * 0.3) {
    contradictions.push({
      field: 'employees', severity: 'warning',
      detail: `Research ${researchEmployees} vs LinkedIn ${linkedinEmpRange.min}-${linkedinEmpRange.max}`
    });
    flags.push('EMPLOYEE_MISMATCH_LOW');
  }
}

if (researchRevenue !== null && researchEmployees && researchEmployees > 0) {
  const ratioPerEmp = (researchRevenue * 1000000) / researchEmployees;
  if (ratioPerEmp > 500000) {
    flags.push('REV_EMP_RATIO_SUSPICIOUS');
    contradictions.push({
      field: 'ratio', severity: 'warning',
      detail: `€${Math.round(ratioPerEmp / 1000)}K/employee — possible parent data`
    });
  }
}

if (!isB2B) flags.push('NOT_B2B');
if (researchConfidence === 'low') flags.push('LOW_CONFIDENCE');

// -----------------------------------------------------------------------
// 5. RESEARCH QUALITY SCORE (0-10)
// -----------------------------------------------------------------------
let qualityScore = 0;

if (research.summary && research.summary.length > 30) qualityScore += 2;
else if (research.summary) qualityScore += 1;

if (isB2B) qualityScore += 1;
if (researchRevenue !== null) qualityScore += 2;
if (researchEmployees !== null) qualityScore += 1;

const ownership = (research.ownership || '').toLowerCase();
if (ownership && ownership !== 'unknown') qualityScore += 1;
if (research.business_model && research.business_model !== 'Other') qualityScore += 0.5;
if (research.markets && research.markets !== 'Unknown' && research.markets !== 'domestic only') qualityScore += 0.5;
if (research.revenue_source) qualityScore += 0.5;
if (research.employees_source) qualityScore += 0.5;

if (researchConfidence === 'high') qualityScore += 1;
else if (researchConfidence === 'medium') qualityScore += 0.5;

if (contradictions.some(c => c.severity === 'critical')) qualityScore -= 2;
if (flags.includes('REV_EMP_RATIO_SUSPICIOUS')) qualityScore -= 1;
if (flags.some(f => f.startsWith('MODEL:'))) qualityScore -= 0.5;

qualityScore = Math.max(0, Math.min(10, Math.round(qualityScore * 10) / 10));

// Confidence as numeric score for research_directory
const confidenceScore = researchConfidence === 'high' ? 0.9
  : researchConfidence === 'medium' ? 0.6
  : 0.3;

// -----------------------------------------------------------------------
// 6. TIER REQUALIFICATION
// -----------------------------------------------------------------------

const bestRevenue = researchRevenue;

let bestEmployees = researchEmployees;
let employeeSource = researchEmployees ? 'research' : 'none';
if (!researchEmployees && linkedinEmpRange) {
  bestEmployees = Math.round((linkedinEmpRange.min + linkedinEmpRange.max) / 2);
  employeeSource = 'linkedin';
  flags.push('EMPLOYEES_FROM_LINKEDIN');
}

const isPE = ownership.includes('pe') || ownership.includes('private equity')
  || ownership.includes('backed') || ownership.includes('venture');
const isSubsidiary = ownership.includes('subsidiary');

const summary = (research.summary || '').toLowerCase();
const industry = (research.industry || '').toLowerCase();

const isPEFund = industry.includes('private equity') || industry.includes('venture capital')
  || industry.includes('fund management') || industry.includes('investment management')
  || summary.includes('private equity firm') || summary.includes('venture capital firm')
  || summary.includes('investment fund');

const originalTier = original.tier || null;

let newTier = null;
let tierReason = '';
const tierSignals = [];

if (isPEFund) {
  newTier = 'Bronze';
  tierReason = 'PE/VC fund — portfolio multiplier opportunity';
  tierSignals.push('pe_fund_detected');

} else if (bestRevenue !== null) {
  if (bestRevenue >= 200) {
    newTier = 'Platinum';
    tierReason = `Verified €${Math.round(bestRevenue)}M → Platinum (€200M+)`;
    tierSignals.push('revenue_platinum');
  } else if (bestRevenue >= 50) {
    newTier = 'Gold';
    tierReason = `Verified €${Math.round(bestRevenue)}M → Gold (€50-200M)`;
    tierSignals.push('revenue_gold');
  } else if (bestRevenue >= 20) {
    newTier = 'Silver';
    tierReason = `Verified €${Math.round(bestRevenue)}M → Silver (€20-100M)`;
    tierSignals.push('revenue_silver');
    if (bestEmployees !== null && bestEmployees < 50) {
      newTier = 'Copper';
      tierReason = `Verified €${Math.round(bestRevenue)}M but ~${Math.round(bestEmployees)} emp → Copper`;
      tierSignals.push('low_headcount_downgrade');
    }
  } else if (bestRevenue >= 10) {
    if (bestEmployees !== null && bestEmployees <= 50) {
      newTier = 'Copper';
      tierReason = `Verified €${Math.round(bestRevenue)}M, ~${Math.round(bestEmployees)} emp → Copper`;
      tierSignals.push('revenue_copper', 'lean_headcount');
    } else {
      newTier = 'Bronze';
      tierReason = `Verified €${Math.round(bestRevenue)}M → Bronze`;
      tierSignals.push('revenue_bronze');
    }
  } else if (bestRevenue >= 8) {
    if (bestEmployees !== null && bestEmployees <= 50) {
      newTier = 'Copper';
      tierReason = `Verified €${Math.round(bestRevenue)}M, ~${Math.round(bestEmployees)} emp → Copper (borderline)`;
      tierSignals.push('revenue_borderline_copper');
    } else {
      newTier = 'Deprioritized';
      tierReason = `Verified €${Math.round(bestRevenue)}M — below Silver, above Copper emp max`;
      tierSignals.push('revenue_below_threshold');
    }
  } else {
    newTier = 'Deprioritized';
    tierReason = `Verified €${Math.round(bestRevenue)}M — below €8M minimum`;
    tierSignals.push('revenue_too_low');
  }

} else if (bestEmployees !== null) {
  flags.push('TIER_FROM_EMPLOYEE_PROXY');
  if (bestEmployees >= 500) {
    newTier = 'Gold';
    tierReason = `No verified revenue, ~${Math.round(bestEmployees)} emp → Gold (conservative proxy)`;
    tierSignals.push('employee_proxy_gold');
  } else if (bestEmployees >= 100) {
    newTier = 'Silver';
    tierReason = `No verified revenue, ~${Math.round(bestEmployees)} emp → Silver (proxy)`;
    tierSignals.push('employee_proxy_silver');
  } else if (bestEmployees >= 50) {
    newTier = 'Bronze';
    tierReason = `No verified revenue, ~${Math.round(bestEmployees)} emp → Bronze (proxy)`;
    tierSignals.push('employee_proxy_bronze');
  } else if (bestEmployees >= 2) {
    newTier = 'Copper';
    tierReason = `No verified revenue, ~${Math.round(bestEmployees)} emp → Copper (proxy)`;
    tierSignals.push('employee_proxy_copper');
  } else {
    newTier = 'Deprioritized';
    tierReason = 'No verified revenue, employee count too low';
    tierSignals.push('insufficient_data');
  }

} else {
  newTier = 'Unclassified';
  tierReason = 'No verified revenue or employee count';
  tierSignals.push('no_sizing_data');
  flags.push('NO_SIZING_DATA');
}

// --- Tier adjustments ---
if (isPE && !isPEFund && newTier === 'Silver') {
  flags.push('PE_BACKED_SILVER_COULD_BE_GOLD');
}

if (isSubsidiary) {
  flags.push('SUBSIDIARY_CHECK_REVENUE');
  if (researchRevenue !== null && researchRevenue >= 200) {
    contradictions.push({
      field: 'revenue', severity: 'critical',
      detail: 'Subsidiary — revenue figure may belong to parent company'
    });
  }
}

const pgNewTier = formatTier(newTier);

let tierChanged = false;
let tierDirection = 'none';
if (originalTier && pgNewTier) {
  if (pgNewTier !== originalTier) {
    tierChanged = true;
    const tierOrder = ['deprioritize', 'tier_5_copper', 'tier_4_bronze', 'tier_3_silver', 'tier_2_gold', 'tier_1_platinum'];
    const oldIdx = tierOrder.indexOf(originalTier);
    const newIdx = tierOrder.indexOf(pgNewTier);
    if (oldIdx >= 0 && newIdx >= 0) {
      tierDirection = newIdx > oldIdx ? 'upgraded' : 'downgraded';
    } else {
      tierDirection = 'reclassified';
    }
    flags.push(`TIER_${tierDirection.toUpperCase()}`);
  }
}

// -----------------------------------------------------------------------
// 7. GEOGRAPHY & INDUSTRY
// -----------------------------------------------------------------------
const hq = research.hq || '';
const hqLower = hq.toLowerCase();

const europeanCountries = [
  'czech', 'slovakia', 'germany', 'austria', 'switzerland', 'netherlands',
  'belgium', 'luxembourg', 'denmark', 'sweden', 'norway', 'finland', 'iceland',
  'poland', 'hungary', 'romania', 'bulgaria', 'croatia', 'slovenia', 'serbia',
  'france', 'spain', 'italy', 'portugal', 'ireland', 'uk', 'united kingdom',
  'great britain', 'england', 'scotland', 'estonia', 'latvia', 'lithuania',
  'greece', 'cyprus', 'malta'
];
const isEuropean = europeanCountries.some(c => hqLower.includes(c));
if (!isEuropean && hq && hqLower !== 'unknown') flags.push('NON_EUROPEAN_HQ');

const targetIndustries = [
  'manufacturing', 'logistics', 'distribution', 'retail', 'pharma',
  'pharmaceutical', 'financial', 'fintech', 'banking', 'insurance',
  'energy', 'healthcare', 'professional services', 'construction',
  'industrial', 'automotive', 'food', 'chemical', 'engineering',
  'solar', 'renewable'
];
const isTargetIndustry = targetIndustries.some(ind =>
  industry.includes(ind) || summary.includes(ind)
);
if (!isTargetIndustry && industry && industry !== 'confirmed') {
  flags.push('NON_TARGET_INDUSTRY');
}

const geoCluster = deriveGeoCluster(hq);

// -----------------------------------------------------------------------
// 8. TRIAGE VERDICT
// -----------------------------------------------------------------------
let verdict = 'pass';
const verdictReason = [];

// Hard disqualifiers
if (!isB2B) {
  verdict = 'disqualify';
  verdictReason.push('Not B2B');
}
if (newTier === 'Deprioritized') {
  verdict = 'disqualify';
  verdictReason.push('Below minimum revenue/size threshold');
}

// Manual review triggers
if (verdict !== 'disqualify') {

  if (contradictions.some(c => c.severity === 'critical')) {
    verdict = 'manual_review';
    verdictReason.push('Critical data contradictions');
  }

  if (newTier === 'Unclassified') {
    verdict = 'manual_review';
    verdictReason.push('No sizing data — cannot assign tier');
  }

  if (flags.includes('SUBSIDIARY_CHECK_REVENUE') && researchRevenue !== null && researchRevenue >= 200) {
    verdict = 'manual_review';
    verdictReason.push('Subsidiary with high revenue — verify entity');
  }

  if (tierChanged) {
    const tierOrder = ['deprioritize', 'tier_5_copper', 'tier_4_bronze', 'tier_3_silver', 'tier_2_gold', 'tier_1_platinum'];
    const oldIdx = tierOrder.indexOf(originalTier);
    const newIdx = tierOrder.indexOf(pgNewTier);
    if (oldIdx >= 0 && newIdx >= 0 && Math.abs(newIdx - oldIdx) >= 2) {
      verdict = 'manual_review';
      verdictReason.push(`Large tier shift: ${displayTier(originalTier)} → ${displayTier(pgNewTier)}`);
    }
  }

  if (qualityScore <= 3) {
    verdict = 'manual_review';
    verdictReason.push('Low research quality score');
  }
}

// PG enum status values
const statusMap = {
  'pass': 'triage_passed',
  'manual_review': 'triage_review',
  'disqualify': 'triage_disqualified'
};

// -----------------------------------------------------------------------
// 9. COMPOSE TRIAGE NOTES
// -----------------------------------------------------------------------
const triageNoteLines = [];
triageNoteLines.push(`VERDICT: ${verdict.toUpperCase()}${verdictReason.length ? ' — ' + verdictReason.join('; ') : ''}`);
triageNoteLines.push(`TIER: ${displayTier(pgNewTier) || newTier}${tierChanged ? ` (was: ${displayTier(originalTier)}, ${tierDirection})` : ''}`);
triageNoteLines.push(`REASON: ${tierReason}`);
triageNoteLines.push(`SCORE: ${qualityScore}/10 | CONFIDENCE: ${researchConfidence}`);
triageNoteLines.push(`SIZING: Revenue ${researchRevenue !== null ? '€' + researchRevenue + 'M' : 'unverified'} (${researchRevenue !== null ? research.revenue_source || 'research' : '-'}) | Employees ${researchEmployees || 'unverified'} (${employeeSource})`);
if (flags.length) triageNoteLines.push(`FLAGS: ${flags.join(', ')}`);
if (contradictions.length) triageNoteLines.push(`CONTRADICTIONS: ${contradictions.map(c => `[${c.severity}] ${c.detail}`).join(' | ')}`);
triageNoteLines.push(`COST: $${researchCost.toFixed(4)} (${model})`);

const triageNotes = triageNoteLines.join('\n');

// -----------------------------------------------------------------------
// 10. RETURN (Postgres-ready values)
// -----------------------------------------------------------------------
return {
  // --- Routing ---
  record_id: original.id,
  triage_verdict: verdict,

  // --- Postgres: companies table (pg_ prefix = ready to write) ---
  pg_status: statusMap[verdict],
  pg_tier: pgNewTier,
  pg_summary: research.summary || null,
  pg_hq_city: hq.split(',')[0]?.trim() || null,
  pg_hq_country: hq.split(',')[1]?.trim() || null,
  pg_geo_cluster: geoCluster,
  pg_ownership_type: mapOwnership(research.ownership),
  pg_business_model: isB2B ? 'b2b' : null,
  pg_industry: (research.industry && research.industry !== 'confirmed') ? research.industry : null,

  // --- Verified data ---
  pg_verified_revenue_m: researchRevenue,
  pg_verified_employees: researchEmployees,
  pg_triage_score: qualityScore,
  pg_triage_notes: triageNotes,
  pg_business_type: research.business_model || null,

  // --- Bucket updates ---
  pg_revenue_bucket: revenueToBucket(researchRevenue),
  pg_company_size_bucket: employeesToBucket(researchEmployees),

  // --- Accumulate cost ---
  pg_enrichment_cost: (parseFloat(original.enrichment_cost_usd) || 0) + researchCost,

  // --- research_assets scores ---
  research_quality_score: qualityScore,
  research_confidence_score: confidenceScore,

  // --- Metadata (not stored in companies) ---
  tier_changed: tierChanged,
  tier_direction: tierDirection,
  is_european: isEuropean,
  is_target_industry: isTargetIndustry,
  employee_source: employeeSource,
  raw_research: JSON.stringify(research),

  // --- Return enrichment cost for Python orchestrator ---
  enrichment_cost_usd: researchCost
};
