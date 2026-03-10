/**
 * Strategy Creation Quality Assessment Test
 *
 * Exercises the chat-based strategy creation flow to evaluate
 * the LangGraph agent architecture quality.
 */
import { test, expect, type Page, type ConsoleMessage } from '@playwright/test'

const BASE = 'http://localhost:5173'
const API = 'http://127.0.0.1:5001'
const NS = 'visionvolve'
const SCREENSHOT_DIR = '../docs/testing/strategy-test'

async function login(page: Page) {
  const resp = await page.request.post(`${API}/api/auth/login`, {
    data: { email: 'test@staging.local', password: 'staging123' },
  })
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  await page.goto(BASE)
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem('lg_access_token', access)
      localStorage.setItem('lg_refresh_token', refresh)
      localStorage.setItem('lg_user', JSON.stringify(user))
    },
    { access: body.access_token, refresh: body.refresh_token, user: body.user },
  )
}

function setupConsoleCapture(page: Page): ConsoleMessage[] {
  const logs: ConsoleMessage[] = []
  page.on('console', (msg) => logs.push(msg))
  return logs
}

async function ensureChatOpen(page: Page) {
  const sidebar = page.locator('[aria-label="AI Chat Sidebar"]')
  const chatInput = sidebar.locator('textarea')
  if (await chatInput.isVisible({ timeout: 2000 }).catch(() => false)) return
  const chatToggle = page.locator('button[aria-label*="Open AI Chat"]')
  if (await chatToggle.isVisible({ timeout: 2000 }).catch(() => false)) {
    await chatToggle.click()
    await page.waitForTimeout(500)
  }
}

async function scrollChatToBottom(page: Page) {
  await page.evaluate(() => {
    const sidebar = document.querySelector('[aria-label="AI Chat Sidebar"]')
    if (!sidebar) return
    sidebar.querySelectorAll('div').forEach((div) => {
      const style = window.getComputedStyle(div)
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
        div.scrollTop = div.scrollHeight
      }
    })
  })
}

test.describe('Strategy Creation Quality Assessment', () => {
  test.setTimeout(240_000) // 4 minutes

  test('diagnose chat API and UI rendering', async ({ page }) => {
    const consoleLogs = setupConsoleCapture(page)

    // -----------------------------------------------------------------------
    // Step 1: Login & Navigate
    // -----------------------------------------------------------------------
    await login(page)
    await page.goto(`${BASE}/${NS}/playbook`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/01-playbook-loaded.png`, fullPage: true })
    console.log(`[ASSESS] Playbook loaded`)

    // -----------------------------------------------------------------------
    // Step 2: Test chat API directly from browser context (SSE)
    // -----------------------------------------------------------------------
    console.log(`\n[ASSESS] === Direct SSE API Test ===`)
    const sseResult = await page.evaluate(async () => {
      const token = localStorage.getItem('lg_access_token')
      const results: string[] = []
      try {
        const resp = await fetch('/api/playbook/chat', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'X-Namespace': 'visionvolve',
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({
            message: 'Say hello in one sentence',
            page_context: 'playbook',
          }),
        })

        const contentType = resp.headers.get('content-type') ?? 'unknown'
        const status = resp.status
        results.push(`Status: ${status}`)
        results.push(`Content-Type: ${contentType}`)

        if (!resp.body) {
          results.push('No response body (not streamable)')
          return { results, events: [], error: null }
        }

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        const events: string[] = []
        let buffer = ''
        const startTime = Date.now()

        // Read SSE events for up to 60 seconds
        while (Date.now() - startTime < 60000) {
          const { done, value } = await reader.read()
          if (done) {
            results.push(`Stream ended after ${Date.now() - startTime}ms`)
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() ?? ''

          for (const part of parts) {
            const trimmed = part.trim()
            if (!trimmed) continue
            events.push(trimmed)
            results.push(`SSE event: ${trimmed.substring(0, 200)}`)
          }
        }

        // Process remaining buffer
        if (buffer.trim()) {
          events.push(buffer.trim())
          results.push(`SSE event (final): ${buffer.trim().substring(0, 200)}`)
        }

        reader.cancel()
        return { results, events, error: null }
      } catch (err) {
        return { results, events: [], error: String(err) }
      }
    })

    for (const r of sseResult.results) {
      console.log(`  ${r}`)
    }
    if (sseResult.error) {
      console.log(`  ERROR: ${sseResult.error}`)
    }
    console.log(`  Total SSE events: ${sseResult.events.length}`)

    // -----------------------------------------------------------------------
    // Step 3: Test JSON API (non-SSE) from browser context
    // -----------------------------------------------------------------------
    console.log(`\n[ASSESS] === Direct JSON API Test ===`)
    const jsonResult = await page.evaluate(async () => {
      const token = localStorage.getItem('lg_access_token')
      try {
        const resp = await fetch('/api/playbook/chat', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'X-Namespace': 'visionvolve',
            'Content-Type': 'application/json',
            // NO Accept: text/event-stream — should get JSON back
          },
          body: JSON.stringify({
            message: 'Say hello briefly',
            page_context: 'playbook',
          }),
        })

        const contentType = resp.headers.get('content-type') ?? 'unknown'
        const status = resp.status
        const body = await resp.text()

        return { status, contentType, body: body.substring(0, 500), error: null }
      } catch (err) {
        return { status: 0, contentType: '', body: '', error: String(err) }
      }
    })

    console.log(`  Status: ${jsonResult.status}`)
    console.log(`  Content-Type: ${jsonResult.contentType}`)
    console.log(`  Error: ${jsonResult.error}`)
    console.log(`  Body: ${jsonResult.body}`)

    // -----------------------------------------------------------------------
    // Step 4: Now test the actual chat UI
    // -----------------------------------------------------------------------
    console.log(`\n[ASSESS] === Chat UI Test ===`)
    await ensureChatOpen(page)
    await page.waitForTimeout(1000)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-chat-open.png`, fullPage: true })

    const sidebar = page.locator('[aria-label="AI Chat Sidebar"]')
    const textarea = sidebar.locator('textarea')
    await expect(textarea).toBeVisible({ timeout: 5000 })

    // Send message via UI
    await textarea.fill('Create a lead generation strategy for B2B SaaS targeting enterprise in Europe')
    await page.waitForTimeout(300)
    await textarea.press('Enter')

    console.log(`  Message sent via UI`)

    // Check for thinking/streaming indicators immediately
    await page.waitForTimeout(2000)
    const earlyState = await page.evaluate(() => {
      const sidebar = document.querySelector('[aria-label="AI Chat Sidebar"]')
      if (!sidebar) return { text: '', hasPulse: false }
      return {
        text: (sidebar.textContent ?? '').substring(0, 200),
        hasPulse: !!sidebar.querySelector('[class*="animate-pulse"]'),
        hasThinking: (sidebar.textContent ?? '').includes('Thinking'),
      }
    })
    console.log(`  After 2s: hasPulse=${earlyState.hasPulse}, hasThinking=${earlyState.hasThinking}`)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-after-2s.png`, fullPage: true })

    // Wait up to 90s for any assistant prose block
    try {
      await page.waitForFunction(
        () => {
          const sidebar = document.querySelector('[aria-label="AI Chat Sidebar"]')
          return sidebar && sidebar.querySelectorAll('.prose').length > 0
        },
        { timeout: 90_000 },
      )
      console.log(`  Assistant response appeared!`)
    } catch {
      console.log(`  No assistant response after 90s`)
    }

    await scrollChatToBottom(page)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-after-wait.png`, fullPage: true })

    // Final chat state
    const finalState = await page.evaluate(() => {
      const sidebar = document.querySelector('[aria-label="AI Chat Sidebar"]')
      if (!sidebar) return { proseCount: 0, textLen: 0 }
      return {
        proseCount: sidebar.querySelectorAll('.prose').length,
        textLen: (sidebar.textContent ?? '').length,
        text: (sidebar.textContent ?? '').substring(0, 500),
      }
    })
    console.log(`  Final: proseBlocks=${finalState.proseCount}, textLen=${finalState.textLen}`)

    // Scroll to see all content
    await page.evaluate(() => {
      const sidebar = document.querySelector('[aria-label="AI Chat Sidebar"]')
      if (!sidebar) return
      sidebar.querySelectorAll('div').forEach((div) => {
        const style = window.getComputedStyle(div)
        if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
          div.scrollTop = 0
        }
      })
    })
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-scrolled-top.png`, fullPage: true })

    // -----------------------------------------------------------------------
    // Step 5: Console errors
    // -----------------------------------------------------------------------
    const consoleErrors = consoleLogs.filter((m) => m.type() === 'error')
    console.log(`\n[ASSESS] Console errors: ${consoleErrors.length}`)
    for (const err of consoleErrors.slice(0, 10)) {
      console.log(`  [ERROR] ${err.text().substring(0, 300)}`)
    }

    // -----------------------------------------------------------------------
    // Summary
    // -----------------------------------------------------------------------
    console.log('\n=== QUALITY ASSESSMENT SUMMARY ===')
    console.log(`Login: PASS`)
    console.log(`Playbook loads: PASS`)
    console.log(`Chat sidebar opens: PASS`)
    console.log(`SSE API works: ${sseResult.events.length > 0 ? 'PASS' : 'FAIL'} (${sseResult.events.length} events)`)
    console.log(`JSON API works: ${jsonResult.status === 201 ? 'PASS' : 'FAIL'} (status ${jsonResult.status})`)
    console.log(`Chat UI renders response: ${finalState.proseCount > 0 ? 'PASS' : 'FAIL'} (${finalState.proseCount} assistant msgs)`)
    console.log(`Console errors: ${consoleErrors.length}`)
    console.log('=================================')
  })
})
