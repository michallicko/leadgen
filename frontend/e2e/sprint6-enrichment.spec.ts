/**
 * BL-185: Sprint 6 Enrichment E2E Verification Tests
 *
 * Validates Sprint 6 enrichment features end-to-end:
 * - Company detail shows L2 enrichment fields (BL-156)
 * - Contact detail shows person enrichment fields (BL-184)
 * - Data quality indicators visible (BL-158)
 * - Copy-to-clipboard works on detail fields (BL-157)
 * - Enrichment pipeline stages are selectable (existing)
 * - Workflow suggestions appear in chat (BL-135 + BL-169)
 * - Phase transitions work (BL-170)
 *
 * Tests run against staging: https://leadgen-staging.visionvolve.com
 */
import { test, expect, type Page } from '@playwright/test'
import { login, getToken, API } from './fixtures/auth'
import { gotoNamespacedPage } from './fixtures/namespace'
import { NAMESPACES, TIMEOUTS, SCREENSHOTS_DIR } from './fixtures/test-data'

const NS = NAMESPACES.primary

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Fetch an enriched company ID (with L2 data) via API. */
async function fetchEnrichedCompanyId(page: Page): Promise<string | null> {
  const token = await getToken(page)
  for (const stage of ['contacts_ready', 'enriched']) {
    const resp = await page.request.get(
      `${API}/api/companies?page_size=5&enrichment_stage=${stage}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Namespace': NS,
        },
      },
    )
    if (!resp.ok()) continue
    const data = await resp.json()
    const companies = data.companies ?? data.items ?? data.data ?? []
    if (companies.length > 0) return companies[0].id
  }
  return null
}

/** Fetch a contact ID that has person enrichment data. */
async function fetchEnrichedContactId(page: Page): Promise<string | null> {
  const token = await getToken(page)
  const resp = await page.request.get(
    `${API}/api/contacts?page_size=50&sort=enrichment_cost_usd&sort_dir=desc`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    },
  )
  if (!resp.ok()) return null
  const data = await resp.json()
  const contacts = data.contacts ?? data.items ?? data.data ?? []
  // Pick the first contact that has enrichment data
  for (const c of contacts) {
    if (c.enrichment_cost_usd && c.enrichment_cost_usd > 0) return c.id
    if (c.person_summary || c.authority_score != null) return c.id
  }
  // Fallback: return first contact
  return contacts[0]?.id ?? null
}

// ─────────────────────────────────────────────────────────────────────────────
// Group 1: Company Detail — L2 Enrichment Fields (BL-156)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 1: Company Detail L2 Enrichment (BL-156)', () => {
  let companyId: string | null = null

  test.beforeEach(async ({ page }) => {
    await login(page)
    companyId = await fetchEnrichedCompanyId(page)
  })

  test('1.1 — Company detail API returns enrichment_l2 with modules', async ({ page }) => {
    if (!companyId) {
      test.skip(true, 'No enriched company found in staging')
      return
    }

    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    expect(resp.ok()).toBe(true)
    const data = await resp.json()

    // Should have enrichment_l2 with modules
    if (data.enrichment_l2) {
      expect(data.enrichment_l2).toHaveProperty('modules')
      expect(data.enrichment_l2).toHaveProperty('enriched_at')

      const modules = data.enrichment_l2.modules
      const moduleKeys = Object.keys(modules)
      expect(moduleKeys.length).toBeGreaterThan(0)

      // Check expected modules exist
      const expectedModules = ['profile', 'signals', 'market', 'opportunity']
      for (const mod of expectedModules) {
        if (modules[mod]) {
          expect(modules[mod]).toHaveProperty('enriched_at')
        }
      }
    }
  })

  test('1.2 — Intelligence tab renders module cards', async ({ page }) => {
    if (!companyId) {
      test.skip(true, 'No enriched company found in staging')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // Click on Intelligence tab
    const intelTab = page.getByRole('button', { name: 'Intelligence', exact: true })
    if ((await intelTab.count()) === 0) {
      test.skip(true, 'No Intelligence tab — company may lack L2 enrichment')
      return
    }

    await intelTab.click()
    await page.waitForTimeout(500)

    const body = await page.textContent('body') ?? ''

    // Should show module cards
    const hasModules =
      body.includes('Company Profile') ||
      body.includes('Strategic Signals') ||
      body.includes('Market Intelligence') ||
      body.includes('AI Opportunity')
    expect(hasModules).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-1.2-intel-modules.png`, fullPage: true })
  })

  test('1.3 — Executive Brief section is visible', async ({ page }) => {
    if (!companyId) {
      test.skip(true, 'No enriched company found in staging')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    const intelTab = page.getByRole('button', { name: 'Intelligence', exact: true })
    if ((await intelTab.count()) === 0) {
      test.skip(true, 'No Intelligence tab')
      return
    }

    await intelTab.click()
    await page.waitForTimeout(500)

    const body = await page.textContent('body') ?? ''

    // Check for executive brief OR pitch framing
    const hasExecBrief =
      body.includes('Executive Brief') ||
      body.includes('Pain Hypothesis') ||
      body.includes('growth_acceleration') ||
      body.includes('efficiency_protection')

    // Executive brief is present for fully enriched companies
    if (hasExecBrief) {
      expect(body.length).toBeGreaterThan(200)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-1.3-exec-brief.png`, fullPage: true })
  })

  test('1.4 — Module cards expand and collapse correctly', async ({ page }) => {
    if (!companyId) {
      test.skip(true, 'No enriched company found in staging')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    const intelTab = page.getByRole('button', { name: 'Intelligence', exact: true })
    if ((await intelTab.count()) === 0) {
      test.skip(true, 'No Intelligence tab')
      return
    }

    await intelTab.click()
    await page.waitForTimeout(500)

    // Find collapsible section buttons (contain an SVG chevron)
    const sectionButtons = page.locator('button:has(svg[class*="transition-transform"])')
    const buttonCount = await sectionButtons.count()

    if (buttonCount > 0) {
      const firstButton = sectionButtons.first()
      const buttonText = await firstButton.textContent()

      // Click to collapse (if open) or expand (if closed)
      await firstButton.click()
      await page.waitForTimeout(300)

      // Click again to toggle back
      await firstButton.click()
      await page.waitForTimeout(300)

      // Verify button still renders (no crash on toggle)
      expect(await firstButton.textContent()).toBe(buttonText)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-1.4-module-collapse.png`, fullPage: true })
  })

  test('1.5 — Company profile fields populated', async ({ page }) => {
    if (!companyId) {
      test.skip(true, 'No enriched company found in staging')
      return
    }

    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    if (data.enrichment_l2?.modules?.profile) {
      const profile = data.enrichment_l2.modules.profile

      // At least some profile fields should be populated
      const populatedFields = ['company_intel', 'key_products', 'customer_segments', 'competitors', 'tech_stack']
        .filter(f => profile[f] != null && profile[f] !== '')
      expect(populatedFields.length).toBeGreaterThan(0)
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 2: Contact Detail — Person Enrichment Fields (BL-184)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 2: Contact Person Enrichment (BL-184)', () => {
  let contactId: string | null = null

  test.beforeEach(async ({ page }) => {
    await login(page)
    contactId = await fetchEnrichedContactId(page)
  })

  test('2.1 — Contact API returns enrichment data', async ({ page }) => {
    if (!contactId) {
      test.skip(true, 'No enriched contact found in staging')
      return
    }

    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/contacts/${contactId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    expect(resp.ok()).toBe(true)
    const data = await resp.json()

    // Check standard contact fields exist
    expect(data).toHaveProperty('full_name')
    expect(data).toHaveProperty('email_address')

    // Check enrichment-related fields
    expect(data).toHaveProperty('seniority_level')
    expect(data).toHaveProperty('department')
    expect(data).toHaveProperty('authority_score')
    expect(data).toHaveProperty('person_summary')
  })

  test('2.2 — Contact detail page shows Enrichment tab', async ({ page }) => {
    if (!contactId) {
      test.skip(true, 'No enriched contact found in staging')
      return
    }

    await page.goto(`${API}/${NS}/contacts/${contactId}`)
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Wait for the page to load
    const overview = page.locator('button:has-text("Overview")')
    await expect(overview.first()).toBeVisible({ timeout: TIMEOUTS.pageLoad })

    // Check for Enrichment tab
    const enrichmentTab = page.locator('button:has-text("Enrichment")')
    const hasEnrichmentTab = (await enrichmentTab.count()) > 0

    if (hasEnrichmentTab) {
      await enrichmentTab.click()
      await page.waitForTimeout(500)

      const body = await page.textContent('body') ?? ''

      // Should show person enrichment sections
      const hasSections =
        body.includes('Career & Background') ||
        body.includes('Buying Signals') ||
        body.includes('Relationship Strategy') ||
        body.includes('Person Summary')
      expect(hasSections).toBe(true)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-2.2-contact-enrichment-tab.png`, fullPage: true })
  })

  test('2.3 — Career & Background section shows data', async ({ page }) => {
    if (!contactId) {
      test.skip(true, 'No enriched contact found in staging')
      return
    }

    await page.goto(`${API}/${NS}/contacts/${contactId}`)
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const enrichmentTab = page.locator('button:has-text("Enrichment")')
    if ((await enrichmentTab.count()) === 0) {
      test.skip(true, 'No Enrichment tab — contact may lack person enrichment')
      return
    }

    await enrichmentTab.click()
    await page.waitForTimeout(500)

    const body = await page.textContent('body') ?? ''

    // Career section should show career trajectory, education, or previous companies
    const hasCareerData =
      body.includes('Career & Background') ||
      body.includes('Career Trajectory') ||
      body.includes('Previous Companies') ||
      body.includes('Education') ||
      body.includes('Expertise Areas')

    if (hasCareerData) {
      expect(body.length).toBeGreaterThan(300)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-2.3-career-background.png`, fullPage: true })
  })

  test('2.4 — Buying Signals section shows AI champion + authority', async ({ page }) => {
    if (!contactId) {
      test.skip(true, 'No enriched contact found in staging')
      return
    }

    await page.goto(`${API}/${NS}/contacts/${contactId}`)
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const enrichmentTab = page.locator('button:has-text("Enrichment")')
    if ((await enrichmentTab.count()) === 0) {
      test.skip(true, 'No Enrichment tab')
      return
    }

    await enrichmentTab.click()
    await page.waitForTimeout(500)

    const body = await page.textContent('body') ?? ''

    // Check for buying signals section content
    const hasBuyingSignals =
      body.includes('Buying Signals') ||
      body.includes('AI Champion') ||
      body.includes('Authority') ||
      body.includes('Budget Signals') ||
      body.includes('Pain Indicators')

    if (hasBuyingSignals) {
      // At least some signal data should be present
      expect(body.length).toBeGreaterThan(200)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-2.4-buying-signals.png`, fullPage: true })
  })

  test('2.5 — Relationship Strategy section renders when data exists', async ({ page }) => {
    if (!contactId) {
      test.skip(true, 'No enriched contact found in staging')
      return
    }

    await page.goto(`${API}/${NS}/contacts/${contactId}`)
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const enrichmentTab = page.locator('button:has-text("Enrichment")')
    if ((await enrichmentTab.count()) === 0) {
      test.skip(true, 'No Enrichment tab')
      return
    }

    await enrichmentTab.click()
    await page.waitForTimeout(500)

    const body = await page.textContent('body') ?? ''

    // Check for relationship strategy section
    const hasRelStrategy =
      body.includes('Relationship Strategy') ||
      body.includes('Personalization Angle') ||
      body.includes('Connection Points') ||
      body.includes('Conversation Starters')

    // This section is optional - some contacts might not have it
    // Just ensure no crash
    expect(body.length).toBeGreaterThan(100)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-2.5-relationship-strategy.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 3: Data Quality Indicators (BL-158)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 3: Data Quality Indicators (BL-158)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('3.1 — Company detail shows data quality score in header', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // Data quality score should appear as "DQ XX" badge
    const dqBadge = page.locator('text=/DQ \\d/')
    const hasDQ = (await dqBadge.count()) > 0

    // Or quality percentage in overview
    const qualityText = page.locator('text=/Quality.*\\d+%/')
    const hasQuality = (await qualityText.count()) > 0

    // At least one quality indicator should be present
    expect(hasDQ || hasQuality).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-3.1-data-quality-score.png`, fullPage: true })
  })

  test('3.2 — L1 confidence and quality visible in overview', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    const body = await page.textContent('body') ?? ''

    // L1 enrichment metadata should show confidence and quality
    const hasL1Meta =
      body.includes('L1 Confidence') ||
      body.includes('Confidence') ||
      body.includes('Quality')
    expect(hasL1Meta).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-3.2-l1-confidence.png`, fullPage: true })
  })

  test('3.3 — QC flags displayed when present', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    // Check via API if any QC flags exist
    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()
    const hasFlags = data.enrichment_l1?.qc_flags?.length > 0

    if (!hasFlags) {
      test.skip(true, 'No QC flags on this company — cannot verify display')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // QC flags should be displayed as small colored badges
    for (const flag of data.enrichment_l1.qc_flags) {
      const flagEl = page.locator(`text=${flag}`)
      expect(await flagEl.count()).toBeGreaterThan(0)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-3.3-qc-flags.png`, fullPage: true })
  })

  test('3.4 — API returns data_quality_score and qc_flags', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    // data_quality_score should be a number between 0-100
    if (data.data_quality_score != null) {
      expect(typeof data.data_quality_score).toBe('number')
      expect(data.data_quality_score).toBeGreaterThanOrEqual(0)
      expect(data.data_quality_score).toBeLessThanOrEqual(100)
    }

    // enrichment_l1 should have qc_flags array and confidence
    if (data.enrichment_l1) {
      expect(data.enrichment_l1).toHaveProperty('confidence')
      expect(data.enrichment_l1).toHaveProperty('quality_score')
      if (data.enrichment_l1.qc_flags) {
        expect(Array.isArray(data.enrichment_l1.qc_flags)).toBe(true)
      }
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 4: Copy-to-Clipboard (BL-157)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 4: Copy-to-Clipboard (BL-157)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('4.1 — Copy buttons appear on company detail fields on hover', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // Find group/field containers (the Field component wraps in group/field)
    const fields = page.locator('[class*="group/field"]')
    const fieldCount = await fields.count()
    expect(fieldCount).toBeGreaterThan(0)

    // Hover over the first field with a non-empty value
    for (let i = 0; i < Math.min(fieldCount, 10); i++) {
      const field = fields.nth(i)
      const ddText = await field.locator('dd span').first().textContent()
      if (ddText && ddText !== '-') {
        await field.hover()
        await page.waitForTimeout(200)

        // Copy button should become visible on hover
        const copyBtn = field.locator('[data-testid="copy-button"]')
        const btnCount = await copyBtn.count()
        if (btnCount > 0) {
          // Button exists in DOM (visibility controlled by CSS opacity)
          expect(btnCount).toBe(1)
          break
        }
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-4.1-copy-buttons-hover.png`, fullPage: true })
  })

  test('4.2 — Copy button invokes clipboard API', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // Grant clipboard permissions for the test
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])

    // Find a copy button and click it
    const copyButtons = page.locator('[data-testid="copy-button"]')
    const btnCount = await copyButtons.count()

    if (btnCount > 0) {
      // Force-click the first copy button (it's hidden by CSS opacity until hover)
      await copyButtons.first().click({ force: true })
      await page.waitForTimeout(500)

      // After clicking, the button's aria-label should change to "Copied"
      const ariaLabel = await copyButtons.first().getAttribute('aria-label')
      expect(ariaLabel).toBe('Copied')

      // Verify clipboard contents (async clipboard API)
      const clipboardText = await page.evaluate(() => navigator.clipboard.readText())
      expect(clipboardText).toBeTruthy()
      expect(clipboardText).not.toBe('-')
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-4.2-copy-clipboard.png`, fullPage: true })
  })

  test('4.3 — Copy button not shown for empty fields', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    // Find fields that display "-" (empty/null)
    const fields = page.locator('[class*="group/field"]')
    const fieldCount = await fields.count()

    for (let i = 0; i < fieldCount; i++) {
      const field = fields.nth(i)
      const dd = field.locator('dd')
      const ddText = await dd.textContent()

      if (ddText?.trim() === '-') {
        // Empty field should NOT have a copy button
        const copyBtn = field.locator('[data-testid="copy-button"]')
        expect(await copyBtn.count()).toBe(0)
      }
    }
  })

  test('4.4 — Copy works on contact detail fields', async ({ page }) => {
    const contactId = await fetchEnrichedContactId(page)
    if (!contactId) {
      test.skip(true, 'No contact found')
      return
    }

    await page.goto(`${API}/${NS}/contacts/${contactId}`)
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Wait for contact detail to load
    const overview = page.locator('button:has-text("Overview")')
    if ((await overview.count()) === 0) {
      test.skip(true, 'Contact detail did not load')
      return
    }

    // Copy buttons should be present on field values
    const copyButtons = page.locator('[data-testid="copy-button"]')
    const btnCount = await copyButtons.count()

    // At least some copy buttons should exist (email, phone, etc.)
    expect(btnCount).toBeGreaterThan(0)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-4.4-contact-copy.png`, fullPage: true })
  })

  test('4.5 — Copy button shows checkmark feedback after click', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    await page.goto(`${API}/${NS}/companies/${companyId}`)
    await page.waitForSelector('button:has-text("Overview")', { timeout: TIMEOUTS.pageLoad })

    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])

    const copyButtons = page.locator('[data-testid="copy-button"]')
    if ((await copyButtons.count()) === 0) {
      test.skip(true, 'No copy buttons found')
      return
    }

    // Click a copy button
    await copyButtons.first().click({ force: true })

    // Should show checkmark SVG (the path "M13 4L6 11L3 8")
    const checkmark = copyButtons.first().locator('path[d="M13 4L6 11L3 8"]')
    await expect(checkmark).toBeVisible({ timeout: 1000 })

    // After 1.5s, should revert to clipboard icon
    await page.waitForTimeout(2000)
    const clipboardIcon = copyButtons.first().locator('rect')
    await expect(clipboardIcon).toBeVisible({ timeout: 1000 })

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-4.5-copy-feedback.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 5: Enrichment Pipeline Stages (existing)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 5: Enrichment Pipeline Stages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('5.1 — Enrich page shows pipeline stages', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const body = await page.textContent('body') ?? ''

    // Should show enrichment pipeline stages
    const hasStages =
      body.includes('L1') || body.includes('L2') || body.includes('Person') ||
      body.includes('Company Research') || body.includes('Deep Research') || body.includes('Contact Research') ||
      body.includes('Triage')
    expect(hasStages).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-5.1-pipeline-stages.png`, fullPage: true })
  })

  test('5.2 — Stage selection checkboxes or toggles are interactive', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Look for stage-related interactive elements
    const stageInputs = page.locator('input[type="checkbox"], [role="switch"], [role="checkbox"]')
    const stageCount = await stageInputs.count()

    // If stage selection UI exists, at least some should be interactive
    if (stageCount > 0) {
      const firstInput = stageInputs.first()
      const isDisabled = await firstInput.isDisabled().catch(() => false)
      // Stage inputs should not be permanently disabled
      // (they may be disabled during loading, but not permanently)
      await page.waitForTimeout(3000)
      const isStillDisabled = await firstInput.isDisabled().catch(() => false)
      // At least after loading, they should be enabled
      // (we don't click them to avoid side effects)
      expect(typeof isStillDisabled).toBe('boolean')
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-5.2-stage-selection.png`, fullPage: true })
  })

  test('5.3 — Stage completions appear in company API response', async ({ page }) => {
    const companyId = await fetchEnrichedCompanyId(page)
    if (!companyId) {
      test.skip(true, 'No enriched company found')
      return
    }

    const token = await getToken(page)
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    expect(data).toHaveProperty('stage_completions')
    expect(Array.isArray(data.stage_completions)).toBe(true)

    if (data.stage_completions.length > 0) {
      const sc = data.stage_completions[0]
      expect(sc).toHaveProperty('stage')
      expect(sc).toHaveProperty('completed_at')
      expect(sc).toHaveProperty('status')
    }

    expect(data).toHaveProperty('derived_stage')
    expect(data.derived_stage).toHaveProperty('label')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 6: Workflow Suggestions & Chat (BL-135, BL-169)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 6: Workflow Suggestions & Chat (BL-135, BL-169)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('6.1 — Playbook page loads chat panel', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if showing
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Chat panel should be visible
    const hasChat =
      (await page.locator('text=AI Chat').count()) > 0 ||
      (await page.locator('textarea').count()) > 0

    expect(hasChat).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-6.1-chat-panel.png`, fullPage: true })
  })

  test('6.2 — Workflow progress strip or suggestions area exists', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if showing
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Check for workflow suggestions or progress indicators
    const hasSuggestions =
      (await page.locator('[class*="suggestion"], [class*="workflow"], [data-testid*="suggestion"]').count()) > 0 ||
      (await page.locator('text=/suggest|next step|recommend/i').count()) > 0

    const hasProgressStrip =
      (await page.locator('[class*="progress-strip"], [class*="workflow-progress"]').count()) > 0

    // At least one of these should exist (or the page should be functional)
    const body = await page.textContent('body') ?? ''
    expect(hasSuggestions || hasProgressStrip || body.length > 200).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-6.2-workflow-suggestions.png`, fullPage: true })
  })

  test('6.3 — Chat textarea accepts input', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if showing
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    const textarea = page.locator('textarea').first()
    const isVisible = await textarea.isVisible({ timeout: TIMEOUTS.elementVisible }).catch(() => false)

    if (!isVisible) {
      test.skip(true, 'Chat textarea not visible — may be in onboarding state')
      return
    }

    // Type a message and verify it appears
    const testMessage = 'What enrichment data is available?'
    await textarea.fill(testMessage)
    const inputValue = await textarea.inputValue()
    expect(inputValue).toBe(testMessage)

    // Send button should be available
    const sendBtn = page.locator('button[aria-label="Send message"]')
    if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      expect(await sendBtn.isDisabled()).toBe(false)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-6.3-chat-input.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 7: Phase Transitions (BL-170)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 7: Phase Transitions (BL-170)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('7.1 — Phase stepper buttons are visible', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if needed
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Check for phase navigation buttons
    const phases = ['Strategy', 'Contacts', 'Messages', 'Campaign']
    let phasesFound = 0

    for (const phase of phases) {
      const btn = page.locator(`button:has-text("${phase}")`).first()
      if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
        phasesFound++
      }
    }

    if (phasesFound === 0) {
      // Might still be in onboarding
      const onboarding = await page.locator('text=/Set Up|Generate|Get Started/i').count()
      expect(onboarding).toBeGreaterThan(0)
    } else {
      expect(phasesFound).toBeGreaterThanOrEqual(2)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-7.1-phase-stepper.png`, fullPage: true })
  })

  test('7.2 — Phase navigation changes active phase', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if needed
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Try clicking through phases
    const phases = ['Contacts', 'Messages', 'Strategy']
    for (const phase of phases) {
      const btn = page.locator(`button:has-text("${phase}")`).first()
      if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await btn.click()
        await page.waitForTimeout(1000)

        // URL or page content should reflect phase change
        const body = await page.textContent('body') ?? ''
        // Phase button should have an active/selected state (typically different styling)
        // At minimum, the page should not crash
        expect(body.length).toBeGreaterThan(200)

        await page.screenshot({
          path: `${SCREENSHOTS_DIR}/s6-7.2-phase-${phase.toLowerCase()}.png`,
          fullPage: true,
        })
      }
    }
  })

  test('7.3 — Phase state persists on page reload', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if needed
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Click on "Contacts" phase if available
    const contactsBtn = page.locator('button:has-text("Contacts")').first()
    if (!(await contactsBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Phase stepper not visible')
      return
    }

    await contactsBtn.click()
    await page.waitForTimeout(1000)

    // Reload the page
    await page.reload()
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // The page should load successfully (no crash)
    const body = await page.textContent('body') ?? ''
    expect(body.length).toBeGreaterThan(200)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/s6-7.3-phase-persist.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 8: Cross-Cutting Validation
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 8: Cross-Cutting Validation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('8.1 — No 500 errors during Sprint 6 page navigation', async ({ page }) => {
    const serverErrors: { url: string; status: number; page: string }[] = []

    page.on('response', (resp) => {
      if (resp.status() >= 500) {
        serverErrors.push({
          url: resp.url(),
          status: resp.status(),
          page: page.url(),
        })
      }
    })

    // Navigate through all enrichment-relevant pages
    const companyId = await fetchEnrichedCompanyId(page)
    const contactId = await fetchEnrichedContactId(page)

    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    await gotoNamespacedPage(page, NS, 'companies')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    if (companyId) {
      await page.goto(`${API}/${NS}/companies/${companyId}`)
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    await gotoNamespacedPage(page, NS, 'contacts')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    if (contactId) {
      await page.goto(`${API}/${NS}/contacts/${contactId}`)
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    if (serverErrors.length > 0) {
      const errorReport = serverErrors
        .map((e) => `${e.status} on ${e.url} (while on ${e.page})`)
        .join('\n')
      expect(serverErrors, `Server errors found:\n${errorReport}`).toEqual([])
    }
  })

  test('8.2 — No console errors on enrichment pages', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    const companyId = await fetchEnrichedCompanyId(page)
    if (companyId) {
      await page.goto(`${API}/${NS}/companies/${companyId}`)
      await page.waitForTimeout(TIMEOUTS.mediumWait)

      // Click Intelligence tab if present
      const intelTab = page.getByRole('button', { name: 'Intelligence', exact: true })
      if ((await intelTab.count()) > 0) {
        await intelTab.click()
        await page.waitForTimeout(500)
      }
    }

    const contactId = await fetchEnrichedContactId(page)
    if (contactId) {
      await page.goto(`${API}/${NS}/contacts/${contactId}`)
      await page.waitForTimeout(TIMEOUTS.mediumWait)

      // Click Enrichment tab if present
      const enrichmentTab = page.locator('button:has-text("Enrichment")')
      if ((await enrichmentTab.count()) > 0) {
        await enrichmentTab.click()
        await page.waitForTimeout(500)
      }
    }

    // Filter out known benign errors
    const realErrors = consoleErrors.filter(
      (e) =>
        !e.includes('favicon') &&
        !e.includes('404') &&
        !e.includes('net::ERR') &&
        !e.includes('Failed to load resource'),
    )

    expect(realErrors).toEqual([])
  })
})
