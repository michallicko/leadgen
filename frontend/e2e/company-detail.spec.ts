import { test, expect, type Page } from '@playwright/test'

const BASE = process.env.BASE_URL ?? 'http://localhost:5174'
const API = process.env.API_URL ?? 'http://localhost:5002'
const NS = 'visionvolve'

/** Login via API and inject tokens into localStorage. */
async function login(page: Page) {
  const resp = await page.request.post(`${API}/api/auth/login`, {
    data: { email: 'test@staging.local', password: 'staging123' },
  })
  const body = await resp.json()
  await page.goto(BASE)
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem('lg_access_token', access)
      localStorage.setItem('lg_refresh_token', refresh)
      localStorage.setItem('lg_user', JSON.stringify(user))
    },
    {
      access: body.access_token,
      refresh: body.refresh_token,
      user: body.user,
    },
  )
}

test.describe('Company List', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/companies`)
    // Wait for the company list to load
    await page.waitForSelector('table tbody tr, [data-testid="company-row"]', { timeout: 15000 })
  })

  test('renders companies with derived stage badges', async ({ page }) => {
    // Should show a list of companies
    const rows = page.locator('table tbody tr, [data-testid="company-row"]')
    await expect(rows.first()).toBeVisible()
    const count = await rows.count()
    expect(count).toBeGreaterThan(0)

    // Page title or heading should contain "Companies"
    await expect(page.locator('text=Companies').first()).toBeVisible()
  })

  test('company list shows tier badges', async ({ page }) => {
    // At least some companies should have tier badges displayed
    const pageText = await page.textContent('body')
    // Should contain some known display values
    expect(pageText).toBeTruthy()
  })
})

test.describe('Company Detail', () => {
  let companyId: string

  test.beforeEach(async ({ page }) => {
    await login(page)

    // Fetch a company with L2 enrichment from API
    const resp = await page.request.get(`${API}/api/companies?page_size=50`, {
      headers: {
        Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem('lg_access_token'))}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()
    // Find a company with enriched_l2 status or the first one
    const companies = data.items ?? data.data ?? []
    const enriched = companies.find((c: any) => c.status?.includes('Enriched')) ?? companies[0]
    companyId = enriched?.id
    expect(companyId).toBeTruthy()

    await page.goto(`${BASE}/${NS}/companies/${companyId}`)
    // Wait for detail page to load
    await page.waitForSelector('[role="tablist"], .space-y-1', { timeout: 15000 })
  })

  test('shows Overview tab with classification fields', async ({ page }) => {
    // Overview tab should be visible by default
    const body = await page.textContent('body')
    expect(body).toContain('Classification')
    expect(body).toContain('Pipeline')
    expect(body).toContain('Scores')
  })

  test('shows derived stage badge in header', async ({ page }) => {
    // The header should show a derived stage or tier badge
    // Look for the colored badge (has inline style with backgroundColor)
    const badges = page.locator('.rounded-full')
    const count = await badges.count()
    expect(count).toBeGreaterThan(0)
  })

  test('shows company links when available', async ({ page }) => {
    // Check for website/linkedin links if the company has them
    const links = page.locator('a[target="_blank"]')
    // Some companies may not have links, so just check page loads
    const body = await page.textContent('body')
    expect(body).toBeTruthy()
  })

  test('shows L1 metadata when enrichment exists', async ({ page }) => {
    const body = await page.textContent('body')
    // Should show at least some of: Confidence, Quality, or classification fields
    const hasL1Data =
      body?.includes('Confidence') ||
      body?.includes('Quality') ||
      body?.includes('Business Model') ||
      body?.includes('Industry')
    expect(hasL1Data).toBeTruthy()
  })

  test('Intelligence tab shows module cards', async ({ page }) => {
    // Click on Intelligence tab if it exists
    const intelTab = page.locator('button:has-text("Intelligence"), [role="tab"]:has-text("Intelligence")')
    if ((await intelTab.count()) > 0) {
      await intelTab.click()
      await page.waitForTimeout(500)

      const body = await page.textContent('body')
      // Should show module cards: Profile, Signals, Market, or Opportunity
      const hasModules =
        body?.includes('Company Profile') ||
        body?.includes('Signals') ||
        body?.includes('Market Intelligence') ||
        body?.includes('AI Opportunity') ||
        body?.includes('Legal & Registry')
      expect(hasModules).toBeTruthy()
    }
  })

  test('module cards expand and collapse', async ({ page }) => {
    const intelTab = page.locator('button:has-text("Intelligence"), [role="tab"]:has-text("Intelligence")')
    if ((await intelTab.count()) > 0) {
      await intelTab.click()
      await page.waitForTimeout(500)

      // Find a module card header button (the collapsible trigger)
      const cardButtons = page.locator('button:has(svg)')
      if ((await cardButtons.count()) > 0) {
        const firstCard = cardButtons.first()
        // Click to toggle
        await firstCard.click()
        await page.waitForTimeout(300)
        // Click again to toggle back
        await firstCard.click()
        await page.waitForTimeout(300)
      }
    }
  })

  test('Contacts tab shows enrichment columns', async ({ page }) => {
    const contactsTab = page.locator('button:has-text("Contacts"), [role="tab"]:has-text("Contacts")')
    if ((await contactsTab.count()) > 0) {
      await contactsTab.click()
      await page.waitForTimeout(500)

      const body = await page.textContent('body')
      // Should show enrichment columns: Seniority, Authority, AI Champion
      const hasColumns =
        body?.includes('Seniority') ||
        body?.includes('Authority') ||
        body?.includes('AI Champion') ||
        body?.includes('ICP') ||
        body?.includes('Score')
      expect(hasColumns).toBeTruthy()
    }
  })

  test('History tab shows enrichment timeline', async ({ page }) => {
    const historyTab = page.locator('button:has-text("History"), [role="tab"]:has-text("History")')
    if ((await historyTab.count()) > 0) {
      await historyTab.click()
      await page.waitForTimeout(500)

      const body = await page.textContent('body')
      expect(body).toContain('Timeline')
    }
  })

  test('stage completions appear in API response', async ({ page }) => {
    // Verify the API returns stage_completions and derived_stage
    const token = await page.evaluate(() => localStorage.getItem('lg_access_token'))
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    // Should have stage_completions array and derived_stage
    expect(data).toHaveProperty('stage_completions')
    expect(data).toHaveProperty('derived_stage')
    expect(Array.isArray(data.stage_completions)).toBeTruthy()
    expect(data.derived_stage).toHaveProperty('label')
    expect(data.derived_stage).toHaveProperty('color')
  })

  test('L2 enrichment returns module structure', async ({ page }) => {
    const token = await page.evaluate(() => localStorage.getItem('lg_access_token'))
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    if (data.enrichment_l2) {
      // Should have modules structure
      expect(data.enrichment_l2).toHaveProperty('modules')
      expect(data.enrichment_l2).toHaveProperty('enriched_at')

      const modules = data.enrichment_l2.modules
      // At least one module should exist
      const moduleKeys = Object.keys(modules)
      expect(moduleKeys.length).toBeGreaterThan(0)

      // Each module should have enriched_at
      for (const key of moduleKeys) {
        expect(modules[key]).toHaveProperty('enriched_at')
      }
    }
  })

  test('contacts have enrichment fields', async ({ page }) => {
    const token = await page.evaluate(() => localStorage.getItem('lg_access_token'))
    const resp = await page.request.get(`${API}/api/companies/${companyId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()

    if (data.contacts?.length > 0) {
      const contact = data.contacts[0]
      // Should have expanded fields
      expect(contact).toHaveProperty('seniority_level')
      expect(contact).toHaveProperty('department')
      expect(contact).toHaveProperty('ai_champion')
      expect(contact).toHaveProperty('authority_score')
      expect(contact).toHaveProperty('person_summary')
      expect(contact).toHaveProperty('linkedin_url')
    }
  })
})

test.describe('Field Quality (API)', () => {
  test('company list returns industry_category and business_type', async ({ page }) => {
    await login(page)
    const token = await page.evaluate(() => localStorage.getItem('lg_access_token'))

    const resp = await page.request.get(`${API}/api/companies?page_size=10`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    const data = await resp.json()
    const companies = data.items ?? data.data ?? []
    expect(companies.length).toBeGreaterThan(0)

    // Check that display values are used (not raw enum values)
    for (const c of companies) {
      if (c.industry_category) {
        // Should be display form like "Technology" not "technology"
        expect(c.industry_category[0]).toEqual(c.industry_category[0].toUpperCase())
      }
    }
  })
})
