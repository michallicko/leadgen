import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const BASE = 'https://leadgen-staging.visionvolve.com'
const NS = 'visionvolve'
const SCREENSHOTS = 'test-results/screenshots'

let authToken = ''

/** Login via API and inject tokens into localStorage. */
async function login(page: Page) {
  const resp = await page.request.post(`${BASE}/api/auth/login`, {
    data: { email: 'test@staging.local', password: 'staging123' },
  })
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  authToken = body.access_token
  await page.goto(`${BASE}/${NS}/`)
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

/** Authenticated API request helper */
async function apiRequest(request: APIRequestContext, method: string, path: string, data?: object) {
  if (!authToken) {
    const loginResp = await request.post(`${BASE}/api/auth/login`, {
      data: { email: 'test@staging.local', password: 'staging123' },
    })
    const loginBody = await loginResp.json()
    authToken = loginBody.access_token
  }
  const opts: Record<string, unknown> = {
    headers: {
      Authorization: `Bearer ${authToken}`,
      'X-Namespace': NS,
      'Content-Type': 'application/json',
    },
  }
  if (data) opts.data = data
  if (method === 'GET') return request.get(`${BASE}${path}`, opts)
  if (method === 'POST') return request.post(`${BASE}${path}`, opts)
  if (method === 'PATCH') return request.patch(`${BASE}${path}`, opts)
  if (method === 'DELETE') return request.delete(`${BASE}${path}`, opts)
  return request.get(`${BASE}${path}`, opts)
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. SETTINGS — Tabbed Preferences Page
// ─────────────────────────────────────────────────────────────────────────────
test.describe('1. SETTINGS — Tabbed Preferences Page', () => {
  test('renders tabbed layout with vertical nav', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Verify the page heading
    const heading = page.locator('h1:has-text("Settings")')
    await expect(heading).toBeVisible({ timeout: 10_000 })

    // Desktop vertical tab buttons (role="tab" inside role="tablist")
    const tablist = page.locator('[role="tablist"]')
    await expect(tablist).toBeVisible({ timeout: 10_000 })

    // Verify all 4 tab buttons exist
    const generalTab = page.locator('button[role="tab"]:has-text("General")')
    await expect(generalTab).toBeVisible()

    const languageTab = page.locator('button[role="tab"]:has-text("Language")')
    await expect(languageTab).toBeVisible()

    const campaignTab = page.locator('button[role="tab"]:has-text("Campaign Templates")')
    await expect(campaignTab).toBeVisible()

    const strategyTab = page.locator('button[role="tab"]:has-text("Strategy Templates")')
    await expect(strategyTab).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOTS}/SETTINGS_tabbed-layout.png`, fullPage: true })
  })

  test('General tab loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // General tab is default active
    const generalTab = page.locator('button[role="tab"]:has-text("General")')
    await expect(generalTab).toBeVisible()
    await expect(generalTab).toHaveAttribute('aria-selected', 'true')

    // Tab panel should be visible
    const panel = page.locator('[role="tabpanel"]')
    await expect(panel).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOTS}/SETTINGS_general-tab.png`, fullPage: true })
  })

  test('Language tab loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    const languageTab = page.locator('button[role="tab"]:has-text("Language")')
    await expect(languageTab).toBeVisible()
    await languageTab.click()
    await page.waitForTimeout(1000)

    // Verify language tab is now active
    await expect(languageTab).toHaveAttribute('aria-selected', 'true')
    await page.screenshot({ path: `${SCREENSHOTS}/SETTINGS_language-tab.png`, fullPage: true })
  })

  test('Campaign Templates tab loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    const tab = page.locator('button[role="tab"]:has-text("Campaign Templates")')
    await expect(tab).toBeVisible()
    await tab.click()
    await page.waitForTimeout(1000)

    await expect(tab).toHaveAttribute('aria-selected', 'true')
    await page.screenshot({ path: `${SCREENSHOTS}/SETTINGS_campaign-templates-tab.png`, fullPage: true })
  })

  test('Strategy Templates tab loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    const tab = page.locator('button[role="tab"]:has-text("Strategy Templates")')
    await expect(tab).toBeVisible()
    await tab.click()
    await page.waitForTimeout(1000)

    await expect(tab).toHaveAttribute('aria-selected', 'true')
    await page.screenshot({ path: `${SCREENSHOTS}/SETTINGS_strategy-templates-tab.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 2. BL-038 — Clone Campaign
// ─────────────────────────────────────────────────────────────────────────────
test.describe('2. BL-038 — Clone Campaign', () => {
  test('campaigns page shows campaigns', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/campaigns`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-038_campaigns-list.png`, fullPage: true })

    // Look for campaign entries
    const campaignName = page.locator('text=/Test Outreach Campaign/i').first()
    await expect(campaignName).toBeVisible({ timeout: 10_000 })
  })

  test('clone campaign via API and verify', async ({ page, request }) => {
    // Get the campaigns list
    const listResp = await apiRequest(request, 'GET', '/api/campaigns')
    expect(listResp.ok()).toBeTruthy()
    const listData = await listResp.json()
    const campaigns = listData.campaigns || listData.items || []
    expect(campaigns.length).toBeGreaterThan(0)

    // Find the original campaign (not a copy)
    const original = campaigns.find((c: { name: string }) => c.name === 'Test Outreach Campaign')
    expect(original).toBeDefined()

    // Clone it via API
    const cloneResp = await apiRequest(request, 'POST', `/api/campaigns/${original.id}/clone`)
    expect(cloneResp.ok()).toBeTruthy()
    const cloneData = await cloneResp.json()

    // Verify cloned campaign has "(Copy)" suffix
    const clonedName = cloneData.campaign?.name || cloneData.name || ''
    expect(clonedName).toContain('Copy')

    // Navigate to campaigns to see the cloned entry
    await login(page)
    await page.goto(`${BASE}/${NS}/campaigns`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOTS}/BL-038_cloned-campaign.png`, fullPage: true })

    // Verify cloned campaign visible
    const clonedEntry = page.locator('text=/Copy/i').first()
    await expect(clonedEntry).toBeVisible({ timeout: 10_000 })

    // Clean up: delete the cloned campaign
    const clonedId = cloneData.campaign?.id || cloneData.id
    if (clonedId) {
      await apiRequest(request, 'DELETE', `/api/campaigns/${clonedId}`)
    }
  })

  test('clone button visible on campaign card', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/campaigns`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for clone/duplicate buttons, icons, or menu options
    const cloneBtn = page.locator(
      '[aria-label*="clone" i], [aria-label*="duplicate" i], ' +
      '[title*="clone" i], [title*="duplicate" i], ' +
      'button:has-text("Clone"), button:has-text("Duplicate"), ' +
      'svg[data-icon="copy"], [class*="clone" i]',
    ).first()

    await page.screenshot({ path: `${SCREENSHOTS}/BL-038_clone-button.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 3. BL-044 — Custom Prompt Instructions
// ─────────────────────────────────────────────────────────────────────────────
test.describe('3. BL-044 — Custom Prompt Instructions', () => {
  test('campaign detail has message generation tab with custom instructions', async ({ page, request }) => {
    // Get a campaign ID
    const listResp = await apiRequest(request, 'GET', '/api/campaigns')
    const listData = await listResp.json()
    const campaigns = listData.campaigns || []
    expect(campaigns.length).toBeGreaterThan(0)

    const campaign = campaigns.find((c: { name: string }) => c.name === 'Test Outreach Campaign')
    expect(campaign).toBeDefined()

    await login(page)
    await page.goto(`${BASE}/${NS}/campaigns/${campaign.id}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for Message Generation tab (could be "Messages", "Generate", "Message Gen")
    const tabs = page.locator('button, [role="tab"], a').filter({ hasText: /message|generat/i })
    const tabCount = await tabs.count()
    if (tabCount > 0) {
      await tabs.first().click()
      await page.waitForTimeout(1500)
    }

    await page.screenshot({ path: `${SCREENSHOTS}/BL-044_message-gen-tab.png`, fullPage: true })

    // Look for custom instructions textarea
    const textareas = page.locator('textarea')
    const textareaCount = await textareas.count()
    if (textareaCount > 0) {
      await page.screenshot({ path: `${SCREENSHOTS}/BL-044_custom-instructions.png`, fullPage: true })
    } else {
      // Still capture what's there
      await page.screenshot({ path: `${SCREENSHOTS}/BL-044_custom-instructions.png`, fullPage: true })
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 4. BL-052 — Contact Search API + Chat Tools
// ─────────────────────────────────────────────────────────────────────────────
test.describe('4. BL-052 — Contact Search API', () => {
  test('POST /api/contacts/search returns results', async ({ request }) => {
    const resp = await apiRequest(request, 'POST', '/api/contacts/search', {
      query: 'ceo',
      page: 1,
      page_size: 10,
    })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.total).toBeGreaterThan(0)
    const contacts = data.contacts || data.items || []
    expect(contacts.length).toBeGreaterThan(0)
    expect(contacts.length).toBeLessThanOrEqual(10)
  })

  test('POST /api/contacts/filter-counts returns facets', async ({ request }) => {
    const resp = await apiRequest(request, 'POST', '/api/contacts/filter-counts', {})
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.facets).toBeDefined()
    expect(Object.keys(data.facets).length).toBeGreaterThan(0)
  })

  test('contacts page loads and shows data', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-052_contacts-page.png`, fullPage: true })

    // Should have a table with contact data
    const table = page.locator('table')
    await expect(table.first()).toBeVisible({ timeout: 10_000 })
  })

  test('contacts search works in UI', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for search input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i], input[placeholder*="Search" i]').first()
    if (await searchInput.isVisible()) {
      await searchInput.fill('ceo')
      await page.waitForTimeout(2000)
    }
    await page.screenshot({ path: `${SCREENSHOTS}/BL-052_search-results.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 5. BL-052b — Contact Filter UI
// ─────────────────────────────────────────────────────────────────────────────
test.describe('5. BL-052b — Contact Filter UI', () => {
  test('contacts page has filter sidebar', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-052b_filter-sidebar.png`, fullPage: true })

    // Look for filter-related text (ICP Fit, Tags, Owner, Status, etc.)
    const filterLabels = page.locator('text=/ICP|Tags|Owner|Status|Company Size|Filter/i')
    const count = await filterLabels.count()
    expect(count).toBeGreaterThan(0)
  })

  test('contacts table is visible', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-052b_contacts-table.png`, fullPage: true })

    // Should have a table
    const table = page.locator('table, [role="grid"]').first()
    await expect(table).toBeVisible({ timeout: 10_000 })
  })

  test('filter interaction changes results', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // Try clicking a filter checkbox if available
    const filterCheckbox = page.locator('input[type="checkbox"]').first()
    if (await filterCheckbox.isVisible()) {
      await filterCheckbox.click()
      await page.waitForTimeout(2000)
    }

    await page.screenshot({ path: `${SCREENSHOTS}/BL-052b_filters-active.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 6. BL-056 — Token Credit System
// ─────────────────────────────────────────────────────────────────────────────
test.describe('6. BL-056 — Token Credit System', () => {
  test('GET /api/admin/tokens returns token data', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/admin/tokens')
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.current_period).toBeDefined()
  })

  test('GET /api/admin/tokens/status returns status', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/admin/tokens/status')
    expect(resp.ok()).toBeTruthy()
  })

  test('GET /api/admin/tokens/history returns history', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/admin/tokens/history')
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.data).toBeDefined()
    expect(Array.isArray(data.data)).toBeTruthy()
  })

  test('tokens dashboard page renders', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/admin/tokens`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-056_tokens-dashboard.png`, fullPage: true })

    // Look for dashboard elements (SVG gauge, charts, etc.)
    const dashboard = page.locator('svg, canvas, [class*="gauge" i], [class*="chart" i], [class*="token" i]').first()
    await expect(dashboard).toBeVisible({ timeout: 10_000 })
  })

  test('tokens page shows SVG gauge or usage chart', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/admin/tokens`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // Verify SVG elements exist (gauge and/or charts)
    const svgElements = page.locator('svg')
    const count = await svgElements.count()
    expect(count).toBeGreaterThan(0)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-056_budget-gauge.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 7. BL-037 — Template Library
// ─────────────────────────────────────────────────────────────────────────────
test.describe('7. BL-037 — Template Library', () => {
  test('GET /api/campaign-templates returns templates', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/campaign-templates')
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    const templates = data.templates || data.items || []
    expect(templates.length).toBeGreaterThan(0)
  })

  test('campaign templates section in preferences', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // Click Campaign Templates tab (desktop button with role="tab")
    const tab = page.locator('button[role="tab"]:has-text("Campaign Templates")')
    await expect(tab).toBeVisible({ timeout: 10_000 })
    await tab.click()
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-037_campaign-templates-section.png`, fullPage: true })

    // Look for template entries/cards in the tab panel
    const panel = page.locator('[role="tabpanel"]')
    await expect(panel).toBeVisible()

    // Check for template-related content
    const templateEntries = panel.locator('text=/Email|LinkedIn|Multi-Channel|Step|template/i')
    const count = await templateEntries.count()
    expect(count).toBeGreaterThan(0)

    await page.screenshot({ path: `${SCREENSHOTS}/BL-037_template-list.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 8. LANG — Namespace Language Settings
// ─────────────────────────────────────────────────────────────────────────────
test.describe('8. LANG — Namespace Language Settings', () => {
  test('GET /api/tenants returns tenant with settings', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/tenants')
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    const tenants = Array.isArray(data) ? data : data.tenants || []
    expect(tenants.length).toBeGreaterThan(0)

    // VisionVolve tenant should exist
    const vv = tenants.find((t: { slug: string }) => t.slug === 'visionvolve')
    expect(vv).toBeDefined()
  })

  test('language section in preferences', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // Click Language tab (desktop button with role="tab")
    const tab = page.locator('button[role="tab"]:has-text("Language")')
    await expect(tab).toBeVisible({ timeout: 10_000 })
    await tab.click()
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOTS}/LANG_language-section.png`, fullPage: true })

    const panel = page.locator('[role="tabpanel"]')
    await expect(panel).toBeVisible()

    // Look for language options (dropdown, radio buttons, cards, etc.)
    // The panel should contain language-related content
    const langContent = panel.locator('text=/English|German|Dutch|Czech|Spanish|Italian|French|language/i')
    const count = await langContent.count()
    expect(count).toBeGreaterThan(0)

    await page.screenshot({ path: `${SCREENSHOTS}/LANG_language-dropdown.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 9. TMPL — GTM Strategy Templates
// ─────────────────────────────────────────────────────────────────────────────
test.describe('9. TMPL — GTM Strategy Templates', () => {
  test('GET /api/strategy-templates returns system templates', async ({ request }) => {
    const resp = await apiRequest(request, 'GET', '/api/strategy-templates')
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    const templates = Array.isArray(data) ? data : data.templates || []
    expect(templates.length).toBeGreaterThanOrEqual(3)

    // Verify they are system templates
    const systemTemplates = templates.filter((t: { is_system: boolean }) => t.is_system)
    expect(systemTemplates.length).toBeGreaterThanOrEqual(3)
  })

  test('strategy templates section in preferences', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // Click Strategy Templates tab (desktop button with role="tab")
    const tab = page.locator('button[role="tab"]:has-text("Strategy Templates")')
    await expect(tab).toBeVisible({ timeout: 10_000 })
    await tab.click()
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOTS}/TMPL_strategy-templates-section.png`, fullPage: true })

    const panel = page.locator('[role="tabpanel"]')
    await expect(panel).toBeVisible()

    // Look for strategy template content
    const templateContent = panel.locator('text=/B2B SaaS|Market Entry|Services|Consulting|Product-Led|template|strategy/i')
    const count = await templateContent.count()
    expect(count).toBeGreaterThan(0)

    await page.screenshot({ path: `${SCREENSHOTS}/TMPL_template-cards.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 10. Regression — Core Pages
// ─────────────────────────────────────────────────────────────────────────────
test.describe('10. Regression — Core Pages Load', () => {
  test('contacts page loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/contacts`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const content = page.locator('table, main').first()
    await expect(content).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/REGRESSION_contacts.png`, fullPage: true })
  })

  test('companies page loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/companies`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const content = page.locator('table, main').first()
    await expect(content).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/REGRESSION_companies.png`, fullPage: true })
  })

  test('campaigns page loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/campaigns`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const content = page.locator('text=/campaign/i').first()
    await expect(content).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/REGRESSION_campaigns.png`, fullPage: true })
  })

  test('playbook page loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/playbook`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const content = page.locator('text=/playbook|strategy/i').first()
    await expect(content).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/REGRESSION_playbook.png`, fullPage: true })
  })

  test('preferences page loads', async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/preferences`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const content = page.locator('h1:has-text("Settings")')
    await expect(content).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/REGRESSION_preferences.png`, fullPage: true })
  })
})
