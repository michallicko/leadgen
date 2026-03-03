/**
 * Deep Workflow E2E Tests — Tests actual workflow OUTCOMES, not just rendering.
 *
 * These tests catch the real failures that baseline-workflow.spec.ts missed:
 * - Strategy generation stuck forever (only checked page loads)
 * - Import preview 500 (only checked upload form renders)
 * - Auto-mapping broken (only checked mapping UI appears)
 * - Chat history pollution across namespaces
 *
 * Expected: many of these FAIL against current staging, proving they catch real bugs.
 * After fixes land, they should PASS.
 */
import { test, expect } from '@playwright/test'
import { login, getToken, API } from './fixtures/auth'
import { gotoNamespacedPage } from './fixtures/namespace'
import { NAMESPACES, TIMEOUTS, SCREENSHOTS_DIR } from './fixtures/test-data'

const NS = NAMESPACES.primary
const NS2 = NAMESPACES.secondary

// Path to test CSV with standard headers: First Name, Last Name, Organization, Title, Email, Phone, Notes
const TEST_CSV_PATH = '/Users/michal/git/leadgen-pipeline/tests/baseline-eval/test-contacts.csv'


// ─────────────────────────────────────────────────────────────────────────────
// Group 1: Strategy Generation Flow
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 1: Strategy Generation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('1.1 — Strategy generation produces real content within timeout', async ({ page }) => {
    // Use secondary namespace which is more likely to be in onboarding state
    await gotoNamespacedPage(page, NS2, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Check if we're in a state where strategy content exists
    const hasStrategyContent = await page.locator('[class*="strategy"], [class*="playbook"], [data-testid*="strategy"]').count() > 0
    const hasOnboarding = await page.locator('text=/Set Up Your Playbook|Generate Your GTM/i').count() > 0

    if (hasOnboarding) {
      // Fill onboarding wizard with short casual inputs to trigger generation
      const inputs = page.locator('input[type="text"], textarea')
      const inputCount = await inputs.count()
      for (let i = 0; i < Math.min(inputCount, 5); i++) {
        const input = inputs.nth(i)
        if (await input.isVisible()) {
          await input.fill('Test company selling B2B SaaS to mid-market')
        }
      }

      // Look for generate/submit button
      const generateBtn = page.locator(
        'button:has-text("Generate"), button:has-text("Create"), button:has-text("Build"), button:has-text("Submit"), button:has-text("Next")'
      ).first()

      if (await generateBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await generateBtn.click()

        // Wait up to 90 seconds for content to appear (AI generation is slow)
        const contentAppeared = await page.locator(
          'text=/target market|value proposition|ideal customer|positioning|strategy/i'
        ).first().waitFor({ timeout: 90_000, state: 'visible' }).then(() => true).catch(() => false)

        if (contentAppeared) {
          // Verify content is real, not placeholder
          const bodyText = await page.textContent('body') ?? ''
          expect(bodyText).not.toMatch(/\[X\]|\[Y\]%|\[placeholder\]|\[insert\]/i)
          expect(bodyText.length).toBeGreaterThan(500)
        } else {
          // If content didn't appear, check if we're stuck in "Researching..." state
          const bodyText = await page.textContent('body') ?? ''
          const isStuck = /researching|generating|loading|please wait/i.test(bodyText)
          expect(isStuck).toBe(false) // FAIL: stuck in loading state
        }
      }
    } else if (hasStrategyContent) {
      // Strategy already exists — verify it has real content
      const bodyText = await page.textContent('body') ?? ''
      expect(bodyText).not.toMatch(/\[X\]|\[Y\]%|\[placeholder\]|\[insert\]/i)
      expect(bodyText.length).toBeGreaterThan(200)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-1.1-strategy-content.png`, fullPage: true })
  })

  test('1.2 — Build a Strategy button works on empty namespace', async ({ page }) => {
    await gotoNamespacedPage(page, NS2, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Find "Build a Strategy" or similar entry point
    const buildBtn = page.locator(
      'button:has-text("Build"), a:has-text("Build a Strategy"), button:has-text("Get Started"), [data-testid="entry-signpost"] >> button'
    ).first()

    const btnVisible = await buildBtn.isVisible({ timeout: 5000 }).catch(() => false)

    if (btnVisible) {
      const beforeUrl = page.url()
      await buildBtn.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)

      // Should navigate or show wizard — NOT stay on the same page doing nothing
      const afterUrl = page.url()
      const bodyText = await page.textContent('body') ?? ''

      const pageChanged = afterUrl !== beforeUrl
      const wizardAppeared = /wizard|step|onboarding|company|industry|set up/i.test(bodyText)
      const formAppeared = await page.locator('input, textarea, select').count() > 0

      // At least ONE of these should be true — the button must DO something
      expect(pageChanged || wizardAppeared || formAppeared).toBe(true)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-1.2-build-strategy-btn.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 2: Import Workflow
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 2: Import Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('2.1 — CSV upload auto-maps standard columns correctly', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'import')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const fileInput = page.locator('input[type="file"]')
    if ((await fileInput.count()) === 0) {
      test.skip(true, 'No file input found on import page')
      return
    }

    // Select the CSV file (this shows the file in the UI but does NOT upload)
    await fileInput.setInputFiles(TEST_CSV_PATH)
    await page.waitForTimeout(1000)

    // Click "Upload & Analyze" to actually send the file and trigger AI mapping
    const uploadBtn = page.locator('button:has-text("Upload & Analyze")')
    if (!(await uploadBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Upload & Analyze button not found after file selection')
      return
    }
    await uploadBtn.click()

    // Wait for AI mapping to process (needs time for API call)
    await page.waitForTimeout(10000)

    // Find all mapping select dropdowns (in the mapping step)
    const selects = page.locator('select')
    const selectCount = await selects.count()

    if (selectCount === 0) {
      // No selects found — mapping UI didn't appear or uses different controls
      const customDropdowns = page.locator('[role="combobox"], [class*="select"], [class*="dropdown"], [class*="mapping"]')
      expect(await customDropdowns.count()).toBeGreaterThan(0)
      return
    }

    // Count how many columns are mapped vs skipped
    // Note: first select may be the owner dropdown from upload step, skip it
    let skippedCount = 0
    let mappedCount = 0
    const mappedValues: string[] = []

    for (let i = 0; i < selectCount; i++) {
      const value = await selects.nth(i).inputValue()
      if (!value || value === '' || /skip|--/i.test(value)) {
        skippedCount++
      } else {
        mappedCount++
        mappedValues.push(value)
      }
    }

    // CRITICAL: Standard columns (Email, First Name, Last Name) should NOT be "Skip"
    // Test CSV has: First Name, Last Name, Organization, Title, Email, Phone, Notes
    // At minimum, Email and Name fields should be auto-mapped
    expect(mappedCount).toBeGreaterThanOrEqual(3) // At least email + first_name + last_name
    expect(skippedCount).not.toBe(selectCount) // NOT all skipped — that's a mapping failure

    // Verify email column specifically maps to an email-like field
    const emailMapped = mappedValues.some(v => /email/i.test(v))
    expect(emailMapped).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-2.1-auto-mapping.png`, fullPage: true })
  })

  test('2.2 — Import preview succeeds without 500 error', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'import')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const fileInput = page.locator('input[type="file"]')
    if ((await fileInput.count()) === 0) {
      test.skip(true, 'No file input found on import page')
      return
    }

    // Track 500 errors during the entire flow
    const serverErrors: { url: string; status: number }[] = []
    page.on('response', (resp) => {
      if (resp.status() >= 500) {
        serverErrors.push({ url: resp.url(), status: resp.status() })
      }
    })

    // Select CSV file then click Upload & Analyze
    await fileInput.setInputFiles(TEST_CSV_PATH)
    await page.waitForTimeout(1000)

    const uploadBtn = page.locator('button:has-text("Upload & Analyze")')
    if (!(await uploadBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Upload & Analyze button not found after file selection')
      return
    }
    await uploadBtn.click()

    // Wait for mapping step to load (AI mapping API call)
    await page.waitForTimeout(10000)

    // Look for Preview button in the mapping step to advance to preview
    const previewBtn = page.locator(
      'button:has-text("Preview"), button:has-text("Next"), button:has-text("Import"), button:has-text("Continue")'
    ).first()

    if (await previewBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Check if the button is actually enabled (not stuck disabled)
      const isDisabled = await previewBtn.isDisabled()
      expect(isDisabled, 'Import Next/Preview button is disabled — mapping likely failed').toBe(false)

      if (!isDisabled) {
        await previewBtn.click()
        await page.waitForTimeout(5000)
      }
    }

    // Assert: NO 500 errors occurred during the entire flow
    expect(serverErrors).toEqual([])

    // Assert: page shows either a preview table or a success message, not an error
    const bodyText = await page.textContent('body') ?? ''
    expect(bodyText).not.toMatch(/internal server error|500|unexpected error/i)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-2.2-import-preview.png`, fullPage: true })
  })

  test('2.3 — Sample values column is populated in mapping UI', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'import')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const fileInput = page.locator('input[type="file"]')
    if ((await fileInput.count()) === 0) {
      test.skip(true, 'No file input found on import page')
      return
    }

    // Select CSV file then click Upload & Analyze
    await fileInput.setInputFiles(TEST_CSV_PATH)
    await page.waitForTimeout(1000)

    const uploadBtn = page.locator('button:has-text("Upload & Analyze")')
    if (!(await uploadBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Upload & Analyze button not found after file selection')
      return
    }
    await uploadBtn.click()

    // Wait for mapping step to load
    await page.waitForTimeout(10000)

    // Look for sample/preview values from the CSV in the mapping UI
    const bodyText = await page.textContent('body') ?? ''

    // CSV contains: David, Malina, EVENT ARENA, david.malina@eventarena.cz
    // At least some sample values should be visible in the mapping UI
    const hasSampleValues =
      bodyText.includes('David') ||
      bodyText.includes('Malina') ||
      bodyText.includes('EVENT ARENA') ||
      bodyText.includes('eventarena')

    expect(hasSampleValues).toBe(true)

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-2.3-sample-values.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 3: Enrich Page
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 3: Enrich Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('3.1 — Enrich page shows human-friendly stage labels', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    const bodyText = await page.textContent('body') ?? ''

    // Should NOT show raw internal labels as stage names
    // Look for standalone "L1" / "L2" / "Person" used as stage headers/labels
    // (not within longer text like "L1 enrichment completed")
    const stageHeaders = page.locator('h1, h2, h3, h4, [class*="stage-label"], [class*="stage-name"], [class*="node-label"]')
    const headerCount = await stageHeaders.count()

    let hasRawLabels = false
    for (let i = 0; i < headerCount; i++) {
      const text = (await stageHeaders.nth(i).textContent()) ?? ''
      // Match standalone "L1", "L2", "Person" as stage labels
      if (/^\s*(L1|L2|Person)\s*$/i.test(text.trim())) {
        hasRawLabels = true
        break
      }
    }

    // Expect human-friendly labels like "Company Discovery", "Deep Company Research", "Contact Research"
    const hasHumanLabels =
      /company discovery|deep.*research|contact research|company research|deep analysis/i.test(bodyText)

    // FAIL if we see raw labels without human-friendly alternatives
    if (hasRawLabels) {
      expect(hasHumanLabels).toBe(true)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-3.1-enrich-labels.png`, fullPage: true })
  })

  test('3.2 — Run button becomes interactive within 5 seconds', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'enrich')

    // Wait a reasonable time for data to load (not forever)
    await page.waitForTimeout(5000)

    const runButton = page.locator(
      'button:has-text("Run"), button:has-text("Start"), button:has-text("Enrich")'
    ).first()

    const buttonVisible = await runButton.isVisible({ timeout: 5000 }).catch(() => false)

    if (buttonVisible) {
      // Button should NOT be disabled or showing a loading state
      const isDisabled = await runButton.isDisabled()
      const buttonText = (await runButton.textContent()) ?? ''

      // If disabled, it should NOT be because of infinite loading
      if (isDisabled) {
        expect(buttonText.toLowerCase()).not.toContain('loading')
        expect(buttonText.toLowerCase()).not.toContain('...')
      }
    } else {
      // If no Run button at all, that might be OK if there are no contacts
      // But we should at least see the enrich page content
      const bodyText = await page.textContent('body') ?? ''
      expect(bodyText.length).toBeGreaterThan(200)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-3.2-run-button.png`, fullPage: true })
  })

  test('3.3 — Enrich page does not show console errors on load', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Filter out known benign errors (favicon, etc.)
    const realErrors = consoleErrors.filter(
      (e) => !e.includes('favicon') && !e.includes('404') && !e.includes('net::ERR')
    )

    // Should not have JavaScript runtime errors
    expect(realErrors).toEqual([])

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-3.3-enrich-no-errors.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 4: Chat Isolation
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 4: Chat Isolation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('4.1 — Chat history is scoped to namespace', async ({ page }) => {
    // Navigate to primary namespace playbook
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if showing
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Capture chat content in primary namespace
    const chatPanel = page.locator('[class*="chat"], [data-testid*="chat"], [role="log"]').first()
    const hasChatPanel = await chatPanel.isVisible({ timeout: 5000 }).catch(() => false)

    if (!hasChatPanel) {
      test.skip(true, 'Chat panel not visible — may be in onboarding state')
      return
    }

    const ns1ChatText = await chatPanel.textContent() ?? ''

    // Navigate to secondary namespace playbook
    await gotoNamespacedPage(page, NS2, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding if showing
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    const ns2ChatPanel = page.locator('[class*="chat"], [data-testid*="chat"], [role="log"]').first()
    const ns2HasChat = await ns2ChatPanel.isVisible({ timeout: 5000 }).catch(() => false)

    if (ns2HasChat && ns1ChatText.length > 50) {
      const ns2ChatText = await ns2ChatPanel.textContent() ?? ''

      // Chat content should be DIFFERENT between namespaces
      // If both have substantial content, they shouldn't be identical
      if (ns2ChatText.length > 50) {
        expect(ns2ChatText).not.toBe(ns1ChatText)
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-4.1-chat-isolation.png`, fullPage: true })
  })

  test('4.2 — New conversation clears history', async ({ page }) => {
    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Find and count existing chat messages
    const messages = page.locator('[class*="message"], [data-testid*="message"]')
    const initialCount = await messages.count()

    // Find "New conversation" or "Clear" or "+" button
    const newChatBtn = page.locator(
      'button:has-text("New"), button:has-text("Clear"), button[aria-label*="new conversation"], button[aria-label*="new chat"]'
    ).first()

    if (await newChatBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newChatBtn.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)

      // After clearing, message count should be 0 or just a system welcome
      const afterCount = await messages.count()

      if (initialCount > 0) {
        expect(afterCount).toBeLessThan(initialCount)
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-4.2-new-conversation.png`, fullPage: true })
  })

  test('4.3 — Chat API calls include correct namespace header', async ({ page }) => {
    const apiCalls: { url: string; namespace: string | null }[] = []

    // Intercept API requests to check X-Namespace header
    page.on('request', (req) => {
      if (req.url().includes('/api/') && req.url().includes('chat')) {
        apiCalls.push({
          url: req.url(),
          namespace: req.headers()['x-namespace'] ?? null,
        })
      }
    })

    await gotoNamespacedPage(page, NS, 'playbook')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Skip onboarding
    const skipButton = page.locator('button:has-text("write it myself")')
    if (await skipButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skipButton.click()
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Send a chat message to trigger an API call
    const textarea = page.locator('textarea').first()
    if (await textarea.isVisible({ timeout: 5000 }).catch(() => false)) {
      await textarea.fill('test message for namespace check')

      const sendBtn = page.locator('button[aria-label="Send message"]')
      if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await sendBtn.click()
        await page.waitForTimeout(5000)
      }
    }

    // All chat API calls should include the correct namespace
    for (const call of apiCalls) {
      expect(call.namespace).toBe(NS)
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-4.3-chat-namespace-header.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 5: Cross-Namespace Isolation
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 5: Cross-Namespace Isolation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('5.1 — Tag filter resets completely on namespace switch', async ({ page }) => {
    // Navigate to primary namespace enrich page
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Try to select a tag if a tag selector is available
    const tagSelect = page.locator(
      'select[class*="tag"], [class*="tag-filter"], [data-testid*="tag"]'
    ).first()

    if (await tagSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Navigate to secondary namespace
      await gotoNamespacedPage(page, NS2, 'enrich')
      await page.waitForTimeout(TIMEOUTS.mediumWait)

      const ns2TagSelect = page.locator(
        'select[class*="tag"], [class*="tag-filter"], [data-testid*="tag"]'
      ).first()

      if (await ns2TagSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
        // Should not have a pre-selected tag from the previous namespace
        const selectedValue = await ns2TagSelect.inputValue()
        expect(selectedValue === '' || selectedValue === 'all' || selectedValue === null).toBeTruthy()
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-5.1-tag-reset.png`, fullPage: true })
  })

  test('5.2 — No cross-namespace API calls on navigation', async ({ page }) => {
    const crossNamespaceCalls: { url: string; namespace: string | null }[] = []

    // Monitor all API calls for namespace header
    page.on('request', (req) => {
      if (req.url().includes('/api/') && !req.url().includes('/auth/')) {
        crossNamespaceCalls.push({
          url: req.url(),
          namespace: req.headers()['x-namespace'] ?? null,
        })
      }
    })

    // Start at primary namespace
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Clear tracked calls
    crossNamespaceCalls.length = 0

    // Navigate to secondary namespace
    await gotoNamespacedPage(page, NS2, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // After navigating to NS2, all API calls should use NS2 namespace
    const wrongNamespaceCalls = crossNamespaceCalls.filter(
      (call) => call.namespace !== null && call.namespace !== NS2
    )

    // No API calls should be made with the old namespace
    expect(wrongNamespaceCalls).toEqual([])

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-5.2-no-cross-ns-calls.png`, fullPage: true })
  })

  test('5.3 — Page header shows correct namespace after switch', async ({ page }) => {
    // Navigate to NS1
    await gotoNamespacedPage(page, NS, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // Navigate to NS2
    await gotoNamespacedPage(page, NS2, 'enrich')
    await page.waitForTimeout(TIMEOUTS.mediumWait)

    // URL should contain NS2
    expect(page.url()).toContain(`/${NS2}/`)

    // If there's a namespace indicator in the header, it should match NS2
    const nsIndicator = page.locator(
      '[class*="namespace"], [class*="tenant"], [data-testid*="namespace"], nav >> text=' + NS2
    ).first()
    if (await nsIndicator.isVisible({ timeout: 3000 }).catch(() => false)) {
      const text = await nsIndicator.textContent() ?? ''
      expect(text.toLowerCase()).toContain(NS2.toLowerCase())
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/deep-5.3-header-namespace.png`, fullPage: true })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Group 6: API Health (Network-Level Checks)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Group 6: API Health', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('6.1 — No 500 errors during full page navigation cycle', async ({ page }) => {
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

    // Navigate through all main pages
    const pages = ['playbook', 'import', 'enrich', 'messages', 'companies', 'contacts', 'campaigns']

    for (const pageName of pages) {
      await gotoNamespacedPage(page, NS, pageName)
      await page.waitForTimeout(TIMEOUTS.mediumWait)
    }

    // Report all 500 errors with detail
    if (serverErrors.length > 0) {
      const errorReport = serverErrors.map(
        (e) => `${e.status} on ${e.url} (while on ${e.page})`
      ).join('\n')
      expect(serverErrors, `Server errors found:\n${errorReport}`).toEqual([])
    }
  })

  test('6.2 — Tags API returns namespace-scoped data', async ({ page }) => {
    const token = await getToken(page)

    // Fetch tags for NS1
    const resp1 = await page.request.get(`${API}/api/tags`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    })
    expect(resp1.ok()).toBe(true)
    const data1 = await resp1.json()
    const tags1 = data1.tags ?? data1 ?? []

    // Fetch tags for NS2
    const resp2 = await page.request.get(`${API}/api/tags`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS2,
      },
    })
    expect(resp2.ok()).toBe(true)
    const data2 = await resp2.json()
    const tags2 = data2.tags ?? data2 ?? []

    // Tags should be different between namespaces (unless one/both are empty)
    if (Array.isArray(tags1) && Array.isArray(tags2) && tags1.length > 0 && tags2.length > 0) {
      const names1 = JSON.stringify(tags1.map((t: { name?: string }) => t.name).sort())
      const names2 = JSON.stringify(tags2.map((t: { name?: string }) => t.name).sort())
      // Verify tags aren't identical — different namespaces should have different tag sets
      expect(names1).not.toBe(names2)
    }
  })

  test('6.3 — Chat history API returns namespace-scoped conversations', async ({ page }) => {
    const token = await getToken(page)

    // Try to get chat history for NS1
    const resp1 = await page.request.get(`${API}/api/chat/conversations`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS,
      },
    }).catch(() => null)

    // Try to get chat history for NS2
    const resp2 = await page.request.get(`${API}/api/chat/conversations`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Namespace': NS2,
      },
    }).catch(() => null)

    // If both endpoints exist and return data, conversations should be different
    if (resp1?.ok() && resp2?.ok()) {
      const data1 = await resp1.json()
      const data2 = await resp2.json()

      const convos1 = data1.conversations ?? data1 ?? []
      const convos2 = data2.conversations ?? data2 ?? []

      // Conversation IDs should not overlap
      if (Array.isArray(convos1) && Array.isArray(convos2) && convos1.length > 0 && convos2.length > 0) {
        const ids1 = new Set(convos1.map((c: { id?: string }) => c.id))
        const ids2 = new Set(convos2.map((c: { id?: string }) => c.id))
        const overlap = [...ids1].filter((id) => ids2.has(id))
        expect(overlap).toEqual([])
      }
    }
  })
})
