declare const __API_BASE__: string;
declare const __EXT_ENV__: string;

export const config = {
  /** Base URL for the leadgen API (injected at build time). */
  apiBase: __API_BASE__,

  /** Build environment: 'prod' or 'staging'. */
  environment: __EXT_ENV__ as 'prod' | 'staging',

  /** Refresh access token 60s before expiry. */
  tokenRefreshBuffer: 60_000,

  /** Periodic activity sync interval in minutes. */
  activitySyncInterval: 30,

  /** Maximum activity events per API call. */
  activityBatchSize: 50,

  /** Base delay between LinkedIn Sales API requests (ms). */
  leadEnrichDelay: 500,

  /** Max retries on 429 rate limit responses. */
  maxRetries: 3,

  /** Exponential backoff multiplier for rate limiting. */
  backoffMultiplier: 2,

  /** Maximum delay between requests (ms). */
  maxDelay: 5000,

  /** Cooldown delay after hitting rate limit (ms). */
  cooldownDelay: 10_000,

  /** Delay between LinkedIn API calls in activity monitor (ms). */
  activityApiDelay: 2000,

  /** Max conversations to fetch per activity sync. */
  maxConversationsPerSync: 10,

  /** Hard cap on LinkedIn API calls per activity sync. */
  maxApiCallsPerSync: 15,

  /** Minimum interval between tab-triggered syncs (ms). */
  minTabSyncInterval: 5 * 60 * 1000,

  /** Delay between multi-page navigation (ms). */
  multiPageDelay: 5000,

  /** Default last-sync date for initial activity sync. */
  defaultSyncDate: '2026-01-01T00:00:00.000Z',
} as const;
