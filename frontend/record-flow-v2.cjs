const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: {
      dir: '/Users/michal/git/leadgen-pipeline/docs/testing/baseline-004-video/',
      size: { width: 1280, height: 720 }
    }
  });
  const page = await context.newPage();

  // 1. Login
  await page.goto('https://leadgen-staging.visionvolve.com');
  await page.waitForTimeout(2000);
  await page.fill('input[type="email"]', 'test@staging.local');
  await page.fill('input[type="password"]', 'staging123');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(4000);

  // 2. Playbook page
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/playbook');
  await page.waitForTimeout(5000);

  // 3. Try chat
  try { await page.keyboard.press('Meta+k'); } catch(e) {}
  await page.waitForTimeout(3000);

  // 4. Contacts with enrichment columns
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/contacts');
  await page.waitForTimeout(4000);

  // 5. Companies
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/companies');
  await page.waitForTimeout(4000);
  // Click first company row
  try {
    await page.click('table tbody tr:first-child', { timeout: 3000 });
    await page.waitForTimeout(4000);
    await page.goBack();
    await page.waitForTimeout(2000);
  } catch(e) {}

  // 6. Import
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/import');
  await page.waitForTimeout(4000);

  // 7. Enrich — show human-friendly labels
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/enrich');
  await page.waitForTimeout(5000);

  // 8. Triage review page
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/triage');
  await page.waitForTimeout(4000);

  // 9. Messages with batch review
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/messages');
  await page.waitForTimeout(4000);

  // 10. Campaigns
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/campaigns');
  await page.waitForTimeout(4000);

  // 11. Settings
  await page.goto('https://leadgen-staging.visionvolve.com/visionvolve/settings');
  await page.waitForTimeout(3000);

  // 12. Admin
  await page.goto('https://leadgen-staging.visionvolve.com/admin');
  await page.waitForTimeout(3000);

  // 13. Empty namespace — test onboarding
  await page.goto('https://leadgen-staging.visionvolve.com/test/');
  await page.waitForTimeout(4000);

  await page.goto('https://leadgen-staging.visionvolve.com/test/playbook');
  await page.waitForTimeout(4000);

  // 14. Empty enrich page
  await page.goto('https://leadgen-staging.visionvolve.com/test/enrich');
  await page.waitForTimeout(3000);

  // 15. Empty campaigns
  await page.goto('https://leadgen-staging.visionvolve.com/test/campaigns');
  await page.waitForTimeout(3000);

  await context.close();
  await browser.close();
  console.log('Video recording complete!');
})();
