/**
 * Content script for LinkedIn Sales Navigator pages.
 *
 * Detects Sales Navigator list pages, extracts leads from the DOM,
 * enriches each lead with LinkedIn Sales API calls (profile URL, company data),
 * and sends extracted leads to the service worker for upload.
 *
 * Ported from ~/git/linkedin-lead-uploader/content.js
 */

import { config } from '../common/config';
import type {
  RawLeadRow,
  EnrichedLeadRow,
  Lead,
  PaginationInfo,
  ExtractionResult,
  PageExtractionResult,
} from '../common/types';

// ============== LOGGING UTILITY ==============
const LOG_PREFIX = '[VV Sales Nav]';

const log = {
  info: (msg: string, ...args: unknown[]) => console.log(`${LOG_PREFIX} ${msg}`, ...args),
  success: (msg: string, ...args: unknown[]) => console.log(`${LOG_PREFIX} ${msg}`, ...args),
  warn: (msg: string, ...args: unknown[]) => console.warn(`${LOG_PREFIX} ${msg}`, ...args),
  error: (msg: string, ...args: unknown[]) => console.error(`${LOG_PREFIX} ${msg}`, ...args),
  debug: (msg: string, ...args: unknown[]) => console.debug(`${LOG_PREFIX} ${msg}`, ...args),
  progress: (current: number, total: number, item: string) =>
    console.log(`${LOG_PREFIX} [${current}/${total}] ${item}`),
};

// ============== RATE LIMITING ==============
let lastRequestTime = 0;
let consecutiveRateLimits = 0;

async function rateLimitedFetch(url: string, options: RequestInit): Promise<Response> {
  // Ensure minimum delay between requests
  const timeSinceLastRequest = Date.now() - lastRequestTime;
  const currentDelay = Math.min(
    config.leadEnrichDelay * Math.pow(config.backoffMultiplier, consecutiveRateLimits),
    config.maxDelay,
  );

  if (timeSinceLastRequest < currentDelay) {
    await new Promise<void>((r) => setTimeout(r, currentDelay - timeSinceLastRequest));
  }

  lastRequestTime = Date.now();

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);

      if (response.status === 429) {
        consecutiveRateLimits++;
        const waitTime = config.cooldownDelay * (attempt || 1);
        log.warn(
          `Rate limited (429), waiting ${waitTime / 1000}s before retry ${attempt + 1}/${config.maxRetries}...`,
        );
        await new Promise<void>((r) => setTimeout(r, waitTime));
        continue;
      }

      // Success - decay consecutive rate limits
      if (consecutiveRateLimits > 0) {
        consecutiveRateLimits = Math.max(0, consecutiveRateLimits - 1);
      }

      return response;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      log.warn(`Fetch error on attempt ${attempt + 1}: ${lastError.message}`);
      await new Promise<void>((r) => setTimeout(r, 1000 * (attempt + 1)));
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

// ============== PUBLIC PROFILE URL FETCHER ==============

interface ProfileData {
  publicProfileUrl: string | null;
  fullName: string;
  firstName: string;
  lastName: string;
  headline: string;
}

async function getPublicLinkedInUrl(
  leadId: string,
  authType: string,
  authToken: string,
  csrfToken: string,
): Promise<ProfileData> {
  // Pre-encoded decoration -- required format for LinkedIn's Sales API
  const decoration =
    '%28entityUrn%2CfirstName%2ClastName%2CfullName%2Cheadline%2CflagshipProfileUrl%2CprofilePictureDisplayImage%2CnumOfConnections%29';

  const url = `https://www.linkedin.com/sales-api/salesApiProfiles/(profileId:${leadId},authType:${authType},authToken:${authToken})?decoration=${decoration}`;

  const response = await rateLimitedFetch(url, {
    method: 'GET',
    headers: {
      accept: '*/*',
      'csrf-token': csrfToken,
      'x-restli-protocol-version': '2.0.0',
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  const data = (await response.json()) as Record<string, string>;

  return {
    publicProfileUrl: data.flagshipProfileUrl || null,
    fullName: data.fullName || '',
    firstName: data.firstName || '',
    lastName: data.lastName || '',
    headline: data.headline || '',
  };
}

// ============== MAIN EXTRACTION FUNCTION ==============

async function extractLeads(): Promise<ExtractionResult> {
  log.info('Starting LinkedIn Sales Navigator extraction...');
  const startTime = Date.now();

  // 1. Auto-detect CSRF token from cookies
  log.debug('Detecting CSRF token from cookies...');
  const csrfCookie = document.cookie
    .split('; ')
    .find((row) => row.startsWith('JSESSIONID='));
  const csrfToken = csrfCookie ? csrfCookie.split('=')[1].replace(/"/g, '') : null;

  if (!csrfToken) {
    log.error('No CSRF token found - are you logged in?');
    return { success: false, error: 'No CSRF token found' };
  }
  log.success('CSRF token detected');

  // 2. Extract leads from current page DOM
  log.info('Scanning page for leads...');
  const leads: RawLeadRow[] = [];
  const rows = document.querySelectorAll('tr[data-row-id]');

  log.info(`Found ${rows.length} lead rows in table`);

  rows.forEach((row, index) => {
    const nameLink = row.querySelector('a[href*="/sales/lead/"]');
    if (!nameLink) {
      log.debug(`Row ${index}: No lead link found, skipping`);
      return;
    }

    const profileHref = nameLink.getAttribute('href') || '';
    // URL format: /sales/lead/{leadId},{authType},{authToken}
    const parts = profileHref.split('/sales/lead/')[1]?.split(',');

    if (!parts || parts.length < 3) {
      log.warn(`Row ${index}: Could not parse lead URL: ${profileHref}`);
      return;
    }

    const leadId = parts[0];
    const authType = parts[1];
    const authToken = parts[2];

    // Extract name
    const allText = (nameLink.textContent || '').trim();
    const name = allText.split('\n')[0].trim();

    // Extract job title from name cell
    const nameCell = row.querySelector('td:first-child');
    let jobTitle = '';
    if (nameCell) {
      const divs = nameCell.querySelectorAll('div');
      for (const div of divs) {
        const fullText = div.textContent?.trim() || '';
        const hasNoChildren = div.children.length === 0;

        if (
          hasNoChildren &&
          fullText.length > 2 &&
          fullText.length < 150 &&
          !fullText.includes('Select') &&
          !fullText.includes('reachable') &&
          !fullText.includes('Add note') &&
          !fullText.includes('No activity') &&
          !fullText.includes('Saved Badge') &&
          (/^(CEO|CFO|COO|CTO|CIO|President|VP|Director|Officer|Manager|Chief|Partner|Founder|Owner|Head)/i.test(fullText) ||
            /(Director|Officer|Manager|Chief|Partner|Founder|Owner|Head) /i.test(fullText) ||
            fullText.includes(' at ') ||
            (fullText.length > 10 && /[A-Z][a-z]+ [A-Z][a-z]+/.test(fullText)))
        ) {
          jobTitle = fullText;
          break;
        }
      }
    }

    // Extract company
    let company = '';
    let companyId = '';
    const companyLink = row.querySelector('a[href*="/sales/company/"]');
    if (companyLink) {
      company = (companyLink.textContent || '').trim().split('(+')[0].trim();
      const companyHref = companyLink.getAttribute('href') || '';
      companyId = companyHref.split('/sales/company/')[1] || '';
    }

    if (name && leadId) {
      leads.push({
        name,
        jobTitle,
        company,
        companyId,
        leadId,
        authType,
        authToken,
      });
      log.debug(`Row ${index}: Extracted "${name}" at "${company}"`);
    }
  });

  log.success(`Extracted ${leads.length} leads from DOM`);

  // 3. Fetch enrichment data (company data + public profile URLs)
  log.info('Starting data enrichment (company data + public profile URLs)...');

  const headers: HeadersInit = {
    accept: '*/*',
    'csrf-token': csrfToken,
    'x-restli-protocol-version': '2.0.0',
  };

  const results: EnrichedLeadRow[] = [];
  let processed = 0;
  let profileUrlsFound = 0;
  let companyDataFound = 0;

  for (const lead of leads) {
    const row: EnrichedLeadRow = {
      name: lead.name,
      jobTitle: lead.jobTitle,
      company: lead.company,
      linkedInUrl: '',
      industry: '',
      revenue: '',
      employees: '',
      website: '',
    };

    // Fetch public LinkedIn profile URL
    try {
      log.debug(`Fetching public profile URL for ${lead.name}...`);
      const profileData = await getPublicLinkedInUrl(
        lead.leadId,
        lead.authType,
        lead.authToken,
        csrfToken,
      );

      if (profileData.publicProfileUrl) {
        row.linkedInUrl = profileData.publicProfileUrl;
        profileUrlsFound++;
        log.debug(`  -> ${profileData.publicProfileUrl}`);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      log.warn(`Could not fetch profile URL for ${lead.name}: ${msg}`);
    }

    // Fetch company data
    if (lead.companyId) {
      try {
        log.debug(`Fetching company data for ${lead.company}...`);
        const url = `https://www.linkedin.com/sales-api/salesApiCompanies/${lead.companyId}?decoration=%28entityUrn%2Cname%2CemployeeCountRange%2CrevenueRange%2Cindustry%2Cwebsite%29`;
        const response = await rateLimitedFetch(url, { headers, method: 'GET' });

        if (response.ok) {
          const data = (await response.json()) as {
            industry?: string;
            employeeCountRange?: string;
            website?: string;
            revenueRange?: {
              estimatedMinRevenue?: { amount: number; unit: string };
              estimatedMaxRevenue?: { amount: number; unit: string };
            };
          };
          row.industry = data.industry || '';
          row.employees = data.employeeCountRange || '';
          row.website = data.website || '';

          if (data.revenueRange) {
            const min = data.revenueRange.estimatedMinRevenue;
            const max = data.revenueRange.estimatedMaxRevenue;
            if (min && max) {
              row.revenue = `$${min.amount}${min.unit.charAt(0)} - $${max.amount}${max.unit.charAt(0)}`;
            }
          }
          companyDataFound++;
          log.debug(`  -> Industry: ${row.industry}, Employees: ${row.employees}`);
        }
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        log.warn(`Could not fetch company data for ${lead.company}: ${msg}`);
      }
    }

    results.push(row);
    processed++;

    // Progress logging every 5 leads
    if (processed % 5 === 0 || processed === leads.length) {
      log.progress(processed, leads.length, `${lead.name} - ${lead.company}`);
    }
  }

  const duration = ((Date.now() - startTime) / 1000).toFixed(1);
  log.success(`Data enrichment complete in ${duration}s`);
  log.info(
    `Stats: ${profileUrlsFound}/${leads.length} profile URLs, ${companyDataFound}/${leads.length} company data`,
  );

  return {
    success: true,
    results,
    leadCount: results.length,
    stats: {
      profileUrlsFound,
      companyDataFound,
      duration,
    },
  };
}

// ============== PAGINATION ==============

function getPaginationInfo(): PaginationInfo {
  log.debug('Analyzing pagination...');
  const currentPage = parseInt(
    new URL(window.location.href).searchParams.get('page') || '1',
    10,
  );

  let totalPages: number | null = null;

  // Method 1: Look for pagination buttons
  const paginationButtons = document.querySelectorAll(
    '[class*="pagination"] button, [class*="artdeco-pagination"] button',
  );
  paginationButtons.forEach((btn) => {
    const num = parseInt((btn.textContent || '').trim(), 10);
    if (!isNaN(num) && (totalPages === null || num > totalPages)) {
      totalPages = num;
    }
  });

  // Method 2: Look for "of X" text
  const paginationText = document.body.innerText.match(/of\s+(\d+)\s*pages?/i);
  if (paginationText) {
    totalPages = parseInt(paginationText[1], 10);
  }

  // Method 3: Calculate from result count
  if (!totalPages) {
    const resultText = document.body.innerText.match(/(\d+(?:,\d+)?)\s+results?/i);
    if (resultText) {
      const totalResults = parseInt(resultText[1].replace(',', ''), 10);
      totalPages = Math.ceil(totalResults / 25); // 25 results per page
      log.debug(`Calculated ${totalPages} pages from ${totalResults} results`);
    }
  }

  // Check for next button
  const nextButton =
    document.querySelector<HTMLButtonElement>(
      'button[aria-label*="Next"], button[class*="next"]',
    ) ||
    Array.from(document.querySelectorAll('button')).find(
      (btn) => btn.textContent?.toLowerCase().includes('next') && !btn.disabled,
    );

  const hasNextPage = !!nextButton && !nextButton.disabled;

  log.debug(`Pagination: page ${currentPage}/${totalPages || '?'}, hasNext: ${hasNextPage}`);

  return {
    currentPage,
    totalPages,
    hasNextPage,
    nextPage: hasNextPage ? currentPage + 1 : null,
  };
}

/** Navigate to the next page by updating the URL query param. */
function goToNextPage(): void {
  const url = new URL(window.location.href);
  const currentPage = parseInt(url.searchParams.get('page') || '1', 10);
  const nextPage = currentPage + 1;
  url.searchParams.set('page', String(nextPage));
  log.info(`Navigating to page ${nextPage}...`);
  window.location.href = url.toString();
}

// ============== LEAD CONVERSION ==============

/** Convert enriched lead rows into the Lead format expected by the API. */
function convertToLeads(rows: EnrichedLeadRow[]): Lead[] {
  return rows.map((row) => ({
    name: row.name,
    job_title: row.jobTitle || undefined,
    company_name: row.company || undefined,
    linkedin_url: row.linkedInUrl || undefined,
    company_website: row.website || undefined,
    revenue: row.revenue || undefined,
    headcount: row.employees || undefined,
    industry: row.industry || undefined,
  }));
}

// ============== MAIN EXTRACTION ENTRY POINT ==============

async function runExtraction(): Promise<ExtractionResult> {
  log.info('='.repeat(50));
  log.info('Starting extraction run...');

  try {
    // Step 1: Extract and enrich leads
    const extraction = await extractLeads();
    if (!extraction.success || !extraction.results) {
      log.error(`Extraction failed: ${extraction.error}`);
      return extraction;
    }

    // Step 2: Convert to API format
    const leads = convertToLeads(extraction.results);

    // Step 3: Send to service worker for upload
    const currentPage = new URL(window.location.href).searchParams.get('page') || '1';
    const tag = `sn-import-p${currentPage}-${Date.now()}`;

    log.info(`Sending ${leads.length} leads to service worker...`);

    return new Promise<ExtractionResult>((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'leads_extracted',
          leads,
          source: 'sales_navigator',
          tag,
        },
        (response?: { success: boolean; created_contacts?: number; error?: string }) => {
          if (chrome.runtime.lastError) {
            log.error(`Extension messaging error: ${chrome.runtime.lastError.message}`);
            resolve({
              success: false,
              error: chrome.runtime.lastError.message,
              leadCount: extraction.leadCount,
              stats: extraction.stats,
            });
          } else if (response?.success) {
            log.success(
              `Upload successful! Leads: ${extraction.leadCount}, Created: ${response.created_contacts ?? 0}`,
            );
            resolve({
              success: true,
              leadCount: extraction.leadCount,
              stats: extraction.stats,
            });
          } else {
            log.error(`Upload failed: ${response?.error || 'Unknown error'}`);
            resolve({
              success: false,
              error: response?.error || 'Unknown error',
              leadCount: extraction.leadCount,
              stats: extraction.stats,
            });
          }
        },
      );
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log.error(`Extraction error: ${msg}`);
    return { success: false, error: msg };
  }
}

// ============== MULTI-PAGE EXTRACTION ==============

/** Wait for the lead table to appear in the DOM. */
async function waitForPageReady(): Promise<boolean> {
  log.debug('Waiting for page to be ready...');

  const maxWait = 15000;
  const checkInterval = 500;
  let waited = 0;

  while (waited < maxWait) {
    const rows = document.querySelectorAll('tr[data-row-id]');
    if (rows.length > 0) {
      log.debug(`Page ready: found ${rows.length} lead rows`);
      return true;
    }

    await new Promise<void>((r) => setTimeout(r, checkInterval));
    waited += checkInterval;
  }

  log.warn('Timeout waiting for page to load leads');
  return false;
}

/** Run extraction and report results back to service worker (multi-page mode). */
async function runExtractionAndReport(): Promise<void> {
  try {
    log.info('Running extraction for multi-page process...');

    await waitForPageReady();

    const extraction = await extractLeads();

    if (!extraction.success || !extraction.results) {
      log.error(`Extraction failed: ${extraction.error}`);
      return;
    }

    // Convert and send leads
    const leads = convertToLeads(extraction.results);
    const currentPage = new URL(window.location.href).searchParams.get('page') || '1';
    const tag = `sn-import-p${currentPage}-${Date.now()}`;

    chrome.runtime.sendMessage(
      {
        type: 'leads_extracted',
        leads,
        source: 'sales_navigator',
        tag,
      },
      (uploadResponse?: { success: boolean; error?: string }) => {
        if (uploadResponse?.success) {
          log.success(`Upload successful for page ${currentPage}`);
        } else {
          log.warn(`Upload failed: ${uploadResponse?.error || 'Unknown'}`);
        }
      },
    );

    // Get pagination info and report completion
    const pagination = getPaginationInfo();

    // Get tab ID from storage
    const { multiPageProcess } = await chrome.storage.local.get(['multiPageProcess']);
    const tabId = multiPageProcess?.tabId as number | undefined;

    const result: PageExtractionResult = {
      success: true,
      leadCount: extraction.leadCount || 0,
      stats: extraction.stats,
      hasNextPage: pagination.hasNextPage,
      nextPage: pagination.nextPage,
    };

    chrome.runtime.sendMessage({
      type: 'page_extraction_complete',
      tabId: tabId || 0,
      result,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log.error(`Extraction error: ${msg}`);
  }
}

// ============== MESSAGE HANDLER ==============

chrome.runtime.onMessage.addListener(
  (
    request: { action?: string; type?: string },
    _sender: chrome.runtime.MessageSender,
    sendResponse: (response: unknown) => void,
  ): boolean | void => {
    // Legacy action-based messages (for compatibility)
    if (request.action === 'extractLeads' || request.type === 'extract_leads') {
      runExtraction().then(sendResponse);
      return true;
    }

    if (request.action === 'extractAndReport' || request.type === 'extract_page') {
      log.info('Starting extraction for multi-page process...');
      runExtractionAndReport();
      sendResponse({ success: true, message: 'Extraction started' });
      return true;
    }

    if (request.action === 'checkPage' || request.type === 'check_page') {
      const isValidPage = window.location.href.includes('linkedin.com/sales');
      const leadCount = document.querySelectorAll('tr[data-row-id]').length;
      const pagination = getPaginationInfo();

      sendResponse({
        isValidPage,
        leadCount,
        currentPage: String(pagination.currentPage),
        totalPages: pagination.totalPages,
        hasNextPage: pagination.hasNextPage,
      });
      return true;
    }

    if (request.action === 'getNextPageInfo') {
      const pagination = getPaginationInfo();
      sendResponse({
        hasNextPage: pagination.hasNextPage,
        nextPage: pagination.nextPage,
        totalPages: pagination.totalPages,
      });
      return true;
    }

    if (request.action === 'goToNextPage' || request.type === 'go_to_next_page') {
      goToNextPage();
      sendResponse({ success: true });
      return true;
    }

    return false;
  },
);

// ============== AUTO-DETECT MULTI-PAGE ON LOAD ==============

(async function checkAndContinue() {
  try {
    const { multiPageProcess } = await chrome.storage.local.get(['multiPageProcess']);

    if (
      multiPageProcess &&
      multiPageProcess.active &&
      !multiPageProcess.stopped
    ) {
      log.info('Multi-page process detected on page load');
      // Background script will trigger extraction via tab listener
    }
  } catch {
    // Storage not available or other error
  }
})();

log.success('Sales Navigator content script loaded and ready');
log.info(`Page URL: ${window.location.href}`);
