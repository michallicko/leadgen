import { test, expect, type Page } from '@playwright/test'

const BASE = process.env.BASE_URL ?? 'https://leadgen-staging.visionvolve.com'
const API = process.env.API_URL ?? BASE
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

/**
 * Wait for the playbook page to finish loading.
 * Handles both states:
 *   - Returning user: shows "ICP Playbook" heading with editor
 *   - New user: shows onboarding form (variant A: "Set Up Your Playbook",
 *     variant B: "Generate Your GTM Strategy")
 */
async function waitForPlaybookReady(page: Page) {
  // Wait for any of the three possible heading texts
  await Promise.race([
    page.waitForSelector('h1:has-text("ICP Playbook")', { timeout: 20000 }),
    page.waitForSelector('h2:has-text("Set Up Your Playbook")', { timeout: 20000 }),
    page.waitForSelector('h2:has-text("Generate Your GTM Strategy")', { timeout: 20000 }),
  ])
}

/**
 * Skip onboarding if it's showing.
 * Returns true if onboarding was skipped, false if already on main view.
 */
async function skipOnboardingIfNeeded(page: Page): Promise<boolean> {
  const skipButton = page.locator('button:has-text("write it myself")')
  if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skipButton.click()
    // After skipping, the main playbook view should appear
    await page.waitForSelector('h1:has-text("ICP Playbook")', { timeout: 10000 })
    return true
  }
  return false
}

test.describe('Playbook Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/playbook`)
    await waitForPlaybookReady(page)
  })

  test('renders page heading or onboarding', async ({ page }) => {
    // Sprint 4 shows "ICP Playbook" for returning users or onboarding for new users
    const playbookHeading = page.locator('h1:has-text("ICP Playbook")')
    const onboardingA = page.locator('h2:has-text("Set Up Your Playbook")')
    const onboardingB = page.locator('h2:has-text("Generate Your GTM Strategy")')

    const visible =
      (await playbookHeading.isVisible()) ||
      (await onboardingA.isVisible()) ||
      (await onboardingB.isVisible())
    expect(visible).toBe(true)
  })

  test('phase stepper is visible with correct phases', async ({ page }) => {
    await skipOnboardingIfNeeded(page)

    // PhaseIndicator renders phase buttons — check for the phase labels
    await expect(page.locator('button:has-text("Strategy")').first()).toBeVisible()
    await expect(page.locator('button:has-text("Contacts")').first()).toBeVisible()
    await expect(page.locator('button:has-text("Messages")').first()).toBeVisible()
    await expect(page.locator('button:has-text("Campaign")').first()).toBeVisible()
  })

  test('chat panel is visible with input', async ({ page }) => {
    await skipOnboardingIfNeeded(page)

    // Chat header says "AI Chat"
    await expect(page.locator('text=AI Chat').first()).toBeVisible()

    // Chat textarea — the placeholder varies by phase but always ends with "..."
    const textarea = page.locator('textarea')
    await expect(textarea.first()).toBeVisible()

    // Send button (aria-label)
    const sendBtn = page.locator('button[aria-label="Send message"]')
    await expect(sendBtn).toBeVisible()
  })

  test('chat area displays correctly', async ({ page }) => {
    await skipOnboardingIfNeeded(page)

    // The chat panel should contain either an empty state message or existing messages
    const chatPanel = page.locator('text=AI Chat').first()
    await expect(chatPanel).toBeVisible()

    // Verify the chat area has either empty state or message bubbles
    const emptyState = page.locator('text=No messages yet')
    const anyMessage = page.locator('[class*="overflow-y-auto"]').first()
    const hasContent =
      (await emptyState.isVisible().catch(() => false)) ||
      (await anyMessage.isVisible().catch(() => false))
    expect(hasContent).toBe(true)
  })

  test('phase navigation works', async ({ page }) => {
    await skipOnboardingIfNeeded(page)

    // Click "Contacts" phase button
    const contactsBtn = page.locator('button:has-text("Contacts")').first()
    await contactsBtn.click()

    // URL should update to include /contacts
    await expect(page).toHaveURL(/\/playbook\/contacts/)

    // Click "Campaign" phase button
    const campaignBtn = page.locator('button:has-text("Campaign")').first()
    await campaignBtn.click()

    // URL should update to include /campaign
    await expect(page).toHaveURL(/\/playbook\/campaign/)

    // Navigate back to Strategy
    const strategyBtn = page.locator('button:has-text("Strategy")').first()
    await strategyBtn.click()
    await expect(page).toHaveURL(/\/playbook\/strategy/)
  })
})
