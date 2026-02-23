import { test, expect, type Page, type Route } from '@playwright/test'

const BASE = process.env.BASE_URL ?? 'http://localhost:5174'
const API = process.env.API_URL ?? 'http://localhost:5002'
const NS = 'visionvolve'

const CAMPAIGN_ID = '00000000-0000-0000-0000-000000000001'

/* eslint-disable @typescript-eslint/no-explicit-any */
type MockData = Record<string, any>

// ── Mock data ─────────────────────────────────────────────

const mockCampaignDetail = {
  id: CAMPAIGN_ID,
  name: 'Q1 Outreach Campaign',
  status: 'Approved',
  description: 'AI-targeted outreach for Q1 2026',
  owner_id: '11111111-1111-1111-1111-111111111111',
  owner_name: 'Michal',
  total_contacts: 50,
  generated_count: 150,
  generation_cost: 3.5,
  template_config: [
    { step: 1, channel: 'email', label: 'Intro Email', enabled: true, needs_pdf: false, variant_count: 1 },
    { step: 2, channel: 'linkedin_connect', label: 'LinkedIn Connect', enabled: true, needs_pdf: false, variant_count: 1 },
    { step: 3, channel: 'email', label: 'Follow-up Email', enabled: true, needs_pdf: false, variant_count: 1 },
  ],
  generation_config: {},
  generation_started_at: '2026-02-18T10:00:00Z',
  generation_completed_at: '2026-02-18T10:15:00Z',
  sender_config: {
    from_email: 'michal@aitransformers.eu',
    from_name: 'Michal',
    reply_to: 'michal@aitransformers.eu',
  },
  contact_status_counts: { generated: 0, approved: 50, pending: 0 },
  created_at: '2026-02-17T09:00:00Z',
  updated_at: '2026-02-19T14:00:00Z',
}

const mockAnalytics = {
  messages: {
    total: 150,
    by_status: { approved: 140, rejected: 5, draft: 5 },
    by_channel: { email: 100, linkedin_connect: 50 },
    by_step: { '1': 50, '2': 50, '3': 50 },
  },
  sending: {
    email: { total: 100, queued: 10, sent: 60, delivered: 25, bounced: 3, failed: 2 },
    linkedin: { total: 50, queued: 20, sent: 15, delivered: 10, failed: 5 },
  },
  contacts: {
    total: 50,
    with_email: 48,
    with_linkedin: 42,
    both_channels: 40,
  },
  cost: {
    generation_usd: 3.5,
    email_sends: 60,
  },
  timeline: {
    created_at: '2026-02-17T09:00:00Z',
    generation_started_at: '2026-02-18T10:00:00Z',
    generation_completed_at: '2026-02-18T10:15:00Z',
    first_send_at: '2026-02-19T08:00:00Z',
    last_send_at: '2026-02-19T14:00:00Z',
  },
}

const mockAnalyticsEmpty = {
  messages: {
    total: 0,
    by_status: {},
    by_channel: {},
    by_step: {},
  },
  sending: {
    email: { total: 0, queued: 0, sent: 0, delivered: 0, bounced: 0, failed: 0 },
    linkedin: { total: 0, queued: 0, sent: 0, delivered: 0, failed: 0 },
  },
  contacts: {
    total: 0,
    with_email: 0,
    with_linkedin: 0,
    both_channels: 0,
  },
  cost: { generation_usd: 0, email_sends: 0 },
  timeline: {
    created_at: null,
    generation_started_at: null,
    generation_completed_at: null,
    first_send_at: null,
    last_send_at: null,
  },
}

const mockContacts = {
  contacts: [],
  total: 0,
}

const mockReviewSummary = {
  total: 150,
  by_status: { approved: 140, rejected: 5, draft: 5 },
  can_approve_outreach: false,
  pending_reason: null,
}

// ── Helpers ───────────────────────────────────────────────

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

/**
 * Set up route interception for campaign detail page API calls.
 * The `analyticsOverride` parameter allows tests to provide custom analytics data.
 */
async function mockCampaignAPIs(
  page: Page,
  opts?: {
    analytics?: MockData
    campaign?: MockData
  },
) {
  const analytics = opts?.analytics ?? mockAnalytics
  const campaign = opts?.campaign ?? mockCampaignDetail

  // Campaign detail
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}`, async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: campaign })
    } else {
      await route.fallback()
    }
  })

  // Campaign contacts
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}/contacts`, async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: mockContacts })
    } else {
      await route.fallback()
    }
  })

  // Campaign analytics
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}/analytics`, async (route: Route) => {
    await route.fulfill({ json: analytics })
  })

  // Review summary
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}/review-summary`, async (route: Route) => {
    await route.fulfill({ json: mockReviewSummary })
  })

  // Send emails
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}/send-emails`, async (route: Route) => {
    await route.fulfill({
      json: { queued_count: 42, sender: { from_email: 'michal@aitransformers.eu', from_name: 'Michal' } },
    })
  })

  // Queue LinkedIn
  await page.route(`**/api/campaigns/${CAMPAIGN_ID}/queue-linkedin`, async (route: Route) => {
    await route.fulfill({
      json: { queued_count: 15, by_owner: { michal: 15 } },
    })
  })
}

// ── Tests: Campaign Detail Page Tabs ──────────────────────

test.describe('Campaign Detail Page — Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await mockCampaignAPIs(page)
    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}`)
    // Wait for campaign header to render
    await page.waitForSelector('text=Q1 Outreach Campaign', { timeout: 15000 })
  })

  test('renders campaign header with name and status', async ({ page }) => {
    await expect(page.locator('text=Q1 Outreach Campaign').first()).toBeVisible()
    await expect(page.locator('text=Approved').first()).toBeVisible()
  })

  test('shows all six tabs', async ({ page }) => {
    const tabBar = page.locator('button[class*="border-b-2"]')

    const tabTexts: string[] = []
    const count = await tabBar.count()
    for (let i = 0; i < count; i++) {
      const text = await tabBar.nth(i).textContent()
      if (text) tabTexts.push(text.trim())
    }

    expect(tabTexts.some((t) => t.includes('Contacts'))).toBeTruthy()
    expect(tabTexts.some((t) => t.includes('Generation'))).toBeTruthy()
    expect(tabTexts.some((t) => t.includes('Messages'))).toBeTruthy()
    expect(tabTexts.some((t) => t.includes('Outreach'))).toBeTruthy()
    expect(tabTexts.some((t) => t.includes('Analytics'))).toBeTruthy()
    expect(tabTexts.some((t) => t.includes('Settings'))).toBeTruthy()
  })

  test('navigating to Outreach tab updates URL and renders content', async ({ page }) => {
    // Click Outreach tab
    const outreachTab = page.locator('button:has-text("Outreach")').first()
    await outreachTab.click()
    await page.waitForTimeout(500)

    // URL should update
    expect(page.url()).toContain('tab=outreach')

    // Outreach content should be visible
    await expect(page.locator('text=Outreach Summary').first()).toBeVisible()
  })

  test('navigating to Analytics tab updates URL and renders content', async ({ page }) => {
    const analyticsTab = page.locator('button:has-text("Analytics")').first()
    await analyticsTab.click()
    await page.waitForTimeout(500)

    expect(page.url()).toContain('tab=analytics')

    // Analytics overview heading should be visible
    await expect(page.locator('text=Overview').first()).toBeVisible()
  })

  test('tab navigation works between all tabs', async ({ page }) => {
    const tabIds = ['Generation', 'Messages', 'Outreach', 'Analytics', 'Settings', 'Contacts']

    for (const label of tabIds) {
      const tab = page.locator(`button:has-text("${label}")`).first()
      await tab.click()
      await page.waitForTimeout(300)

      // Verify the URL query param changed
      const url = new URL(page.url())
      const tabParam = url.searchParams.get('tab')
      // The tab param should be set (except for default which might be 'contacts')
      expect(tabParam).toBeTruthy()
    }
  })
})

// ── Tests: Outreach Tab ───────────────────────────────────

test.describe('Outreach Tab — Summary and Actions', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await mockCampaignAPIs(page)
    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=outreach`)
    await page.waitForSelector('text=Outreach Summary', { timeout: 15000 })
  })

  test('shows outreach summary stat cards', async ({ page }) => {
    // Stat cards should be visible
    await expect(page.locator('text=Approved Emails').first()).toBeVisible()
    await expect(page.locator('text=LinkedIn Ready').first()).toBeVisible()
    await expect(page.locator('text=Emails Sent').first()).toBeVisible()
    await expect(page.locator('text=LinkedIn Sent').first()).toBeVisible()
  })

  test('displays email delivery section with sender info', async ({ page }) => {
    await expect(page.locator('text=Email Delivery').first()).toBeVisible()
    // Sender address should be shown
    await expect(page.locator('text=michal@aitransformers.eu').first()).toBeVisible()
  })

  test('displays Send All Emails button', async ({ page }) => {
    const sendBtn = page.locator('button:has-text("Send All Emails")')
    await expect(sendBtn).toBeVisible()
    await expect(sendBtn).toBeEnabled()
  })

  test('displays Queue for Extension button for LinkedIn', async ({ page }) => {
    await expect(page.locator('text=LinkedIn Queue').first()).toBeVisible()
    const queueBtn = page.locator('button:has-text("Queue for Extension")')
    await expect(queueBtn).toBeVisible()
    await expect(queueBtn).toBeEnabled()
  })

  test('shows email delivery status when emails have been sent', async ({ page }) => {
    await expect(page.locator('text=Delivery Status').first()).toBeVisible()
    // Should show progress bar with sent count
    const body = await page.textContent('body')
    expect(body).toContain('Sent')
  })

  test('shows LinkedIn queue status when messages have been queued', async ({ page }) => {
    await expect(page.locator('text=Queue Status').first()).toBeVisible()
    // Should show progress bar with processed count
    const body = await page.textContent('body')
    expect(body).toContain('Processed')
  })

  test('shows messages by step table', async ({ page }) => {
    await expect(page.locator('text=Messages by Step').first()).toBeVisible()
    // Step rows should be in the table
    const body = await page.textContent('body')
    expect(body).toContain('Step 1')
    expect(body).toContain('Step 2')
    expect(body).toContain('Step 3')
  })
})

// ── Tests: Outreach Tab — Confirmation Dialogs ────────────

test.describe('Outreach Tab — Confirmation Dialogs', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await mockCampaignAPIs(page)
    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=outreach`)
    await page.waitForSelector('text=Outreach Summary', { timeout: 15000 })
  })

  test('clicking Send All Emails opens confirmation dialog', async ({ page }) => {
    const sendBtn = page.locator('button:has-text("Send All Emails")')
    await sendBtn.click()

    // Confirmation dialog should appear
    await expect(page.locator('text=Confirm Email Send').first()).toBeVisible()
    // Dialog content should mention the email count and sender
    const dialogBody = await page.textContent('body')
    expect(dialogBody).toContain('email')
    expect(dialogBody).toContain('michal@aitransformers.eu')

    // Cancel and Send buttons should be present
    await expect(page.locator('button:has-text("Cancel")').first()).toBeVisible()
    await expect(page.locator('button:has-text("Send Emails")').first()).toBeVisible()
  })

  test('cancelling email send dialog closes it', async ({ page }) => {
    const sendBtn = page.locator('button:has-text("Send All Emails")')
    await sendBtn.click()

    await expect(page.locator('text=Confirm Email Send').first()).toBeVisible()

    // Click Cancel
    await page.locator('button:has-text("Cancel")').first().click()
    await page.waitForTimeout(300)

    // Dialog should be gone
    await expect(page.locator('text=Confirm Email Send')).toHaveCount(0)
  })

  test('confirming email send calls API and shows toast', async ({ page }) => {
    const sendBtn = page.locator('button:has-text("Send All Emails")')
    await sendBtn.click()

    await expect(page.locator('text=Confirm Email Send').first()).toBeVisible()

    // Click Send Emails in the dialog
    await page.locator('button:has-text("Send Emails")').first().click()
    await page.waitForTimeout(500)

    // Dialog should close and toast should show
    const body = await page.textContent('body')
    expect(body).toContain('queued for delivery')
  })

  test('clicking Queue for Extension opens LinkedIn confirmation dialog', async ({ page }) => {
    const queueBtn = page.locator('button:has-text("Queue for Extension")')
    await queueBtn.click()

    // LinkedIn confirmation dialog should appear
    await expect(page.locator('text=Confirm LinkedIn Queue').first()).toBeVisible()
    await expect(page.locator('button:has-text("Queue Messages")').first()).toBeVisible()
    await expect(page.locator('button:has-text("Cancel")').first()).toBeVisible()
  })

  test('confirming LinkedIn queue calls API and shows toast', async ({ page }) => {
    const queueBtn = page.locator('button:has-text("Queue for Extension")')
    await queueBtn.click()

    await expect(page.locator('text=Confirm LinkedIn Queue').first()).toBeVisible()

    // Click Queue Messages in the dialog
    await page.locator('button:has-text("Queue Messages")').first().click()
    await page.waitForTimeout(500)

    // Toast should show
    const body = await page.textContent('body')
    expect(body).toContain('queued for extension')
  })
})

// ── Tests: Outreach Tab — Empty State ─────────────────────

test.describe('Outreach Tab — Empty State', () => {
  test('shows empty state when no approved messages', async ({ page }) => {
    await login(page)

    // Mock with empty analytics (0 approved messages)
    const emptyCampaign = { ...mockCampaignDetail, status: 'Draft', generated_count: 0 }
    const emptyAnalytics = { ...mockAnalyticsEmpty }

    await mockCampaignAPIs(page, {
      campaign: emptyCampaign,
      analytics: emptyAnalytics,
    })

    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=outreach`)
    await page.waitForTimeout(2000)

    // Empty state messaging
    await expect(page.locator('text=No Messages Ready for Outreach').first()).toBeVisible()
    await expect(page.locator('text=Approve messages in the Messages tab first').first()).toBeVisible()
  })
})

// ── Tests: Outreach Tab — Missing Sender Config ───────────

test.describe('Outreach Tab — Missing Sender Config', () => {
  test('shows sender warning when sender not configured', async ({ page }) => {
    await login(page)

    // Campaign with no sender config
    const noSenderCampaign = {
      ...mockCampaignDetail,
      sender_config: {},
    }
    await mockCampaignAPIs(page, { campaign: noSenderCampaign })

    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=outreach`)
    await page.waitForSelector('text=Outreach Summary', { timeout: 15000 })

    // Warning about sender not configured
    await expect(page.locator('text=Sender not configured').first()).toBeVisible()
    await expect(page.locator('text=Go to the Settings tab').first()).toBeVisible()
  })

  test('Send All Emails button is disabled without sender config', async ({ page }) => {
    await login(page)

    const noSenderCampaign = {
      ...mockCampaignDetail,
      sender_config: {},
    }
    await mockCampaignAPIs(page, { campaign: noSenderCampaign })

    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=outreach`)
    await page.waitForSelector('text=Outreach Summary', { timeout: 15000 })

    const sendBtn = page.locator('button:has-text("Send All Emails")')
    await expect(sendBtn).toBeDisabled()
  })
})

// ── Tests: Analytics Tab ──────────────────────────────────

test.describe('Analytics Tab — Renders Correctly', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await mockCampaignAPIs(page)
    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=analytics`)
    // Wait for analytics to load
    await page.waitForSelector('text=Overview', { timeout: 15000 })
  })

  test('renders overview stat cards with correct values', async ({ page }) => {
    // Stat cards
    await expect(page.locator('text=Contacts').first()).toBeVisible()
    await expect(page.locator('text=Messages').first()).toBeVisible()
    await expect(page.locator('text=Approved').first()).toBeVisible()
    await expect(page.locator('text=Cost').first()).toBeVisible()

    const body = await page.textContent('body')
    // Contact count
    expect(body).toContain('50')
    // Message count
    expect(body).toContain('150')
    // Approved count
    expect(body).toContain('140')
    // Cost
    expect(body).toContain('$3.50')
  })

  test('renders channel breakdown section', async ({ page }) => {
    await expect(page.locator('text=Messages by Channel').first()).toBeVisible()

    const body = await page.textContent('body')
    // Email and LinkedIn badges
    expect(body).toContain('Email')
    expect(body).toContain('LI Connect')
  })

  test('renders delivery status with progress bars', async ({ page }) => {
    await expect(page.locator('text=Delivery Status').first()).toBeVisible()

    // Email and LinkedIn progress bars
    const body = await page.textContent('body')
    expect(body).toContain('Email')
    expect(body).toContain('LinkedIn')
  })

  test('renders message status table', async ({ page }) => {
    await expect(page.locator('text=Message Status').first()).toBeVisible()

    const body = await page.textContent('body')
    // Status rows
    expect(body).toContain('Approved')
    expect(body).toContain('Rejected')
  })

  test('renders by sequence step table', async ({ page }) => {
    await expect(page.locator('text=By Sequence Step').first()).toBeVisible()

    const body = await page.textContent('body')
    expect(body).toContain('Step 1')
    expect(body).toContain('Step 2')
    expect(body).toContain('Step 3')
  })

  test('renders contact reach section', async ({ page }) => {
    await expect(page.locator('text=Contact Reach').first()).toBeVisible()

    const body = await page.textContent('body')
    expect(body).toContain('Total Contacts')
    expect(body).toContain('With Email')
    expect(body).toContain('With LinkedIn')
    expect(body).toContain('Both Channels')
  })

  test('renders timeline section', async ({ page }) => {
    await expect(page.locator('text=Timeline').first()).toBeVisible()

    const body = await page.textContent('body')
    expect(body).toContain('Campaign Created')
    expect(body).toContain('Generation Started')
    expect(body).toContain('Generation Completed')
    expect(body).toContain('First Send')
    expect(body).toContain('Last Send')
  })
})

// ── Tests: Analytics Tab — Empty State ────────────────────

test.describe('Analytics Tab — Empty State', () => {
  test('shows empty state when no analytics data exists', async ({ page }) => {
    await login(page)

    await mockCampaignAPIs(page, {
      analytics: mockAnalyticsEmpty,
    })

    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=analytics`)
    await page.waitForTimeout(2000)

    // Empty state
    await expect(page.locator('text=No analytics data yet').first()).toBeVisible()
    await expect(page.locator('text=Generate messages and start outreach').first()).toBeVisible()
  })
})

// ── Tests: Analytics Tab — Error State ────────────────────

test.describe('Analytics Tab — Error State', () => {
  test('shows error state when analytics API fails', async ({ page }) => {
    await login(page)

    // Mock campaign detail (needed to render the page)
    await page.route(`**/api/campaigns/${CAMPAIGN_ID}`, async (route: Route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: mockCampaignDetail })
      } else {
        await route.fallback()
      }
    })

    await page.route(`**/api/campaigns/${CAMPAIGN_ID}/contacts`, async (route: Route) => {
      await route.fulfill({ json: mockContacts })
    })

    await page.route(`**/api/campaigns/${CAMPAIGN_ID}/review-summary`, async (route: Route) => {
      await route.fulfill({ json: mockReviewSummary })
    })

    // Make analytics return 500 error
    await page.route(`**/api/campaigns/${CAMPAIGN_ID}/analytics`, async (route: Route) => {
      await route.fulfill({ status: 500, json: { error: 'Internal server error' } })
    })

    await page.goto(`${BASE}/${NS}/campaigns/${CAMPAIGN_ID}?tab=analytics`)
    await page.waitForTimeout(3000)

    // Error state
    await expect(page.locator('text=Failed to load analytics').first()).toBeVisible()
  })
})
