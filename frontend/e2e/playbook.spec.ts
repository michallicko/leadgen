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

test.describe('Playbook Page', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto(`${BASE}/${NS}/playbook`)
    // Wait for editor to initialise (Tiptap renders .ProseMirror inside .strategy-editor)
    await page.waitForSelector('.strategy-editor .ProseMirror', { timeout: 15000 })
  })

  test('renders page heading', async ({ page }) => {
    // The page title says "ICP Playbook"
    await expect(page.locator('text=ICP Playbook').first()).toBeVisible()
  })

  test('strategy editor is visible with toolbar', async ({ page }) => {
    // Editor container
    const editor = page.locator('.strategy-editor')
    await expect(editor).toBeVisible()

    // Toolbar buttons: Bold (B), Italic (I), headings (H1, H2, H3)
    const toolbar = editor.locator('button')
    const labels = await toolbar.allTextContents()
    expect(labels).toContain('B')
    expect(labels).toContain('I')
    expect(labels).toContain('H1')
    expect(labels).toContain('H2')
    expect(labels).toContain('H3')
  })

  test('chat panel is visible with input', async ({ page }) => {
    // Chat header says "AI Chat"
    await expect(page.locator('text=AI Chat').first()).toBeVisible()

    // Chat textarea placeholder
    const textarea = page.locator('textarea[placeholder="Ask about your strategy..."]')
    await expect(textarea).toBeVisible()

    // Send button (aria-label)
    const sendBtn = page.locator('button[aria-label="Send message"]')
    await expect(sendBtn).toBeVisible()
  })

  test('chat empty state shows when no messages', async ({ page }) => {
    // Empty state text
    await expect(page.locator('text=No messages yet').first()).toBeVisible()
  })

  test('save and extract buttons are present', async ({ page }) => {
    // Save button
    const saveBtn = page.locator('button:has-text("Save")')
    await expect(saveBtn).toBeVisible()

    // Extract button
    const extractBtn = page.locator('button:has-text("Extract")')
    await expect(extractBtn).toBeVisible()
  })
})
