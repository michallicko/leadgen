# LinkedIn Safe Sending Limits (2026 Research)

> Research conducted: 2026-02-21
> Purpose: Conservative defaults for a Chrome extension that sends LinkedIn invites and messages on behalf of users without triggering account restrictions.
> Important context: Browser extensions carry ~60% higher detection risk than cloud-based platforms. Our defaults must be more conservative than cloud tool recommendations.

---

## Connection Requests

### Limits by Risk Tier

| Tier | Daily | Weekly | Use Case |
|------|-------|--------|----------|
| **Conservative (recommended default)** | 10-15/day | 50-70/week | New users, accounts < 6 months, SSI < 50 |
| **Moderate** | 15-25/day | 70-100/week | Established accounts (6+ months), SSI 50-70, acceptance rate > 30% |
| **Aggressive (not recommended)** | 25-40/day | 100-150/week | Premium/Sales Nav, SSI > 70, acceptance rate > 40% |

### Key Constraints

- **Hard ceiling**: LinkedIn enforces ~100 connection requests/week for most accounts. Premium and Sales Navigator users with high SSI (65+) and acceptance rates (40%+) can reach 200/week.
- **Acceptance rate floor**: Maintain 30%+ acceptance rate. Below 20% triggers spam detection. Below 15% risks account restriction.
- **Pending invites**: Withdraw pending invitations older than 14-21 days. A backlog of unanswered invites signals spam behavior.
- **3% rule**: Dux-Soup recommends sending no more than 3% of your total connections as new requests per day.

### Account Type Variations

| Account Type | Safe Daily Max | Safe Weekly Max | Notes |
|--------------|---------------|-----------------|-------|
| Free | 10-15 | 50-70 | Strictest monitoring |
| Premium Business | 15-25 | 70-100 | Slightly higher tolerance |
| Sales Navigator | 20-30 | 80-150 | Higher limits with good SSI |
| Recruiter | 25-35 | 100-175 | Most lenient |

### Warmup Schedule (New Accounts or First-Time Extension Users)

A minimum 14-day warmup is required before running at full safe limits. This reduces ban risk from 23% to ~5%.

| Week | Connection Requests/Day | Messages/Day | Profile Views/Day | Notes |
|------|------------------------|--------------|-------------------|-------|
| 1 | 3-5 | 5-10 | 30-50 | Manual-only, warm contacts only |
| 2 | 5-10 | 10-20 | 50-100 | Light automation OK (40% auto / 60% manual) |
| 3 | 10-15 | 20-30 | 100-200 | Increase cold outreach to 40% |
| 4 | 15-20 | 30-50 | 150-300 | Full safe operation |
| 5+ | 15-25 | 40-70 | 200-400 | Adjust based on acceptance rate |

**Warmup rules:**
- Accounts < 6 months old face stricter monitoring
- Wait 4-6 weeks before introducing automation on brand new accounts
- Maintain 60/40 warm-to-cold contact ratio during warmup
- If acceptance rate drops below 50% during warmup, reduce volume and rebalance toward warmer contacts
- Post-restriction recovery: 30 days manual-only, then gradual tool reintroduction

---

## Messages (to 1st-Degree Connections)

### Limits by Risk Tier

| Tier | Daily | Weekly | Notes |
|------|-------|--------|-------|
| **Conservative (recommended default)** | 20-30/day | 100-150/week | Safest for browser extension |
| **Moderate** | 30-50/day | 150-250/week | Established accounts with good history |
| **Aggressive (not recommended)** | 50-80/day | 250-400/week | Premium accounts only |

### Account Type Variations

| Account Type | Safe Daily Max | Notes |
|--------------|---------------|-------|
| Free | 30-50 | ~100/week hard guidance |
| Premium | 50-75 | ~150/week guidance |
| Sales Navigator | 75-150 | Higher tolerance |
| Recruiter | 100-200 | Most lenient |

### Message Best Practices

- Keep outreach messages to 300-500 characters
- Maximum 2 follow-ups per prospect
- Space follow-ups 3-7 days apart (vary naturally -- sometimes 2 days, sometimes 5)
- Wait 24-48 hours minimum after connection acceptance before first message
- Personalize: LinkedIn's AI detects copy-paste/templated messages at scale

### InMail Limits (for reference, not automated by our extension)

| Account Type | Monthly InMail Credits | Daily Soft Limit |
|--------------|----------------------|------------------|
| Premium Career | 5 | N/A |
| Premium Business | 15 | ~5 |
| Sales Navigator Core | 50 | ~25 |
| Recruiter Lite | 30 | ~15 |

Note: Cannot send another InMail to the same member until they respond. Credits refunded if recipient responds within 90 days.

---

## Timing and Scheduling

### Safe Operating Hours

- **Primary window**: 8:00 AM - 6:00 PM in the user's local timezone
- **Peak engagement**: 9:00 AM - 11:00 AM and 2:00 PM - 4:00 PM (Tuesday-Thursday)
- **Weekend policy**: Reduce activity to 20-30% of weekday volume, or pause entirely
- **Best days**: Tuesday, Wednesday, Thursday have highest engagement
- **Avoid**: Late night/early morning activity (midnight to 6 AM) is a dead giveaway for automation
- **24/7 activity is an instant red flag** -- the tool must sleep when the user sleeps

### Delays Between Actions

| Action | Minimum Delay | Recommended Range | Notes |
|--------|--------------|-------------------|-------|
| Between connection requests | 45 seconds | 60-180 seconds | Randomized, never uniform |
| Between messages | 30 seconds | 45-120 seconds | Randomized |
| Between profile views | 15 seconds | 20-60 seconds | Randomized |
| After profile view, before connect | 10 seconds | 15-45 seconds | Simulates reading the profile |
| After connect, before message | 24 hours | 24-72 hours | Wait for acceptance first |
| Between follow-up messages | 2 days | 3-7 days | Vary per prospect |

### Critical Timing Rules

1. **Never use uniform intervals** -- exactly 60 seconds between every action is a detection signature. Randomize with natural variance (e.g., 42s, 115s, 58s, 93s).
2. **Add micro-pauses** -- occasional 3-5 minute gaps simulate checking email or reading content.
3. **Burst avoidance** -- never send more than 5 connection requests in any 10-minute window.
4. **Session duration** -- limit active automation sessions to 2-4 hours with breaks between sessions.
5. **Daily distribution** -- spread actions across the full operating window, not clustered in one block.

---

## Warning Signals and Detection Triggers

### What Triggers LinkedIn's Automated Detection

**High-risk triggers (likely immediate restriction):**
1. Sudden volume spikes (e.g., 10 requests/day jumping to 100 overnight)
2. Mechanical timing patterns (identical intervals between actions)
3. 24/7 activity with no breaks
4. Multiple automation tools running simultaneously
5. Identical/templated messages sent to many users (copy-paste detection)
6. Connection acceptance rate below 15%

**Medium-risk triggers (accumulative risk):**
1. Sending connection requests to many unrelated/out-of-network users
2. High volume of pending (unanswered) invitations
3. Unusual login behavior (IP changes, geographic inconsistencies)
4. Browser fingerprint anomalies (missing expected signatures)
5. Action sequence patterns (always the same order: view profile, connect, message)
6. Weekend activity matching weekday volumes

**Low-risk triggers (can tip the scale):**
1. Generic connection notes ("I'd like to add you to my network")
2. Viewing many profiles without any follow-up action
3. Rapid profile viewing (50 profiles in one minute)
4. Connecting with profiles far outside your industry/geography

### LinkedIn's Detection Technology (2025-2026)

- **AI-powered pattern recognition** introduced in 2025 -- performs comprehensive behavioral analysis
- **Machine learning algorithms** identify repetitive behavior patterns across millions of accounts
- **Browser fingerprinting** to detect automation tools
- **Action velocity monitoring** -- speed at which actions are performed is the #1 detection signal
- LinkedIn cross-references action patterns against known automation tool signatures

### Warning Signs You're Approaching Limits

1. **"Weekly invitation limit reached"** notice -- stop immediately, wait for reset
2. **CAPTCHA challenges** appearing more frequently
3. **"Unusual activity detected"** banner
4. **Email verification requests** during normal use
5. **Phone number verification** prompts
6. **Temporary feature restrictions** (search, messaging disabled for hours)
7. **Profile view count dropping** -- may indicate shadow throttling

### Restriction Severity Tiers

| Tier | Duration | Recovery Rate | Typical Trigger |
|------|----------|---------------|-----------------|
| Tier 1 (soft) | 1-24 hours | 95%+ | Minor velocity spike, CAPTCHA failure |
| Tier 2 (medium) | 3-14 days | ~89% | Repeated violations, ID verification required |
| Tier 3 (permanent) | Indefinite | < 15% | Extreme abuse, multiple Tier 2 violations |

### Recovery Protocol If Warned

**Immediate (0-24 hours):**
1. Stop all automation immediately -- disable the extension
2. Screenshot the violation notice for reference
3. Complete any identity verification LinkedIn requests
4. Do NOT appeal yet -- wait for the restriction period

**Short-term (24-72 hours):**
1. File a professional appeal emphasizing understanding of policies
2. Use LinkedIn manually with very light activity (2-3 actions per session)
3. Post organic content (articles, comments) to rebuild trust signals

**Recovery (1-4 weeks):**
1. Manual-only activity for minimum 30 days
2. Keep daily actions under 10 total
3. Focus on warm contacts and organic engagement
4. Gradually reintroduce automation after 30+ days

**Post-recovery (month 2-3):**
1. Re-warmup as if it were a new account (Week 1 schedule above)
2. Use more conservative limits than before the restriction
3. Monitor acceptance rates closely -- target 40%+

---

## Recommended Extension Defaults

Based on the research above, here are the recommended defaults for our Chrome extension:

### Default Configuration

```json
{
  "connection_requests": {
    "daily_limit": 12,
    "weekly_limit": 60,
    "warmup_start_daily": 3,
    "warmup_increment_per_week": 3
  },
  "messages": {
    "daily_limit": 25,
    "weekly_limit": 125,
    "max_followups_per_prospect": 2,
    "followup_delay_days_min": 3,
    "followup_delay_days_max": 7,
    "post_accept_delay_hours_min": 24,
    "post_accept_delay_hours_max": 72
  },
  "timing": {
    "active_hours_start": "08:00",
    "active_hours_end": "18:00",
    "active_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "weekend_volume_pct": 20,
    "delay_between_actions_sec_min": 60,
    "delay_between_actions_sec_max": 180,
    "micro_pause_chance_pct": 15,
    "micro_pause_duration_sec_min": 180,
    "micro_pause_duration_sec_max": 300,
    "max_actions_per_10min": 5,
    "session_max_duration_min": 180,
    "session_break_min": 30
  },
  "safety": {
    "min_acceptance_rate_pct": 25,
    "pause_on_captcha": true,
    "pause_on_warning": true,
    "auto_withdraw_pending_days": 14,
    "warmup_enabled": true,
    "warmup_duration_weeks": 4
  }
}
```

### Why These Defaults Are Extra-Conservative

1. **Browser extension tax**: Browser extensions are ~60% more detectable than cloud tools. We compensate with ~40% lower limits than cloud tool recommendations.
2. **User protection first**: A user who gets banned loses their entire LinkedIn network and professional identity. The cost of being too conservative (slower outreach) is far lower than the cost of a ban.
3. **23% ban rate context**: Research shows 23% of automation users experience restrictions within 90 days. Our warmup + conservative limits aim to keep this under 5%.
4. **Acceptance rate monitoring**: The extension should automatically throttle if acceptance rate drops below 25%, as this is the strongest predictor of restrictions.

---

## Account Health Scoring (SSI)

LinkedIn's Social Selling Index (SSI) significantly impacts what limits are safe:

| SSI Range | Account Health | Recommended Limit Multiplier |
|-----------|---------------|------------------------------|
| < 30 | Poor | 0.5x (half the defaults) |
| 30-50 | Below average | 0.75x |
| 50-70 | Good | 1.0x (use defaults as-is) |
| 70-85 | Strong | 1.25x |
| 85+ | Excellent | 1.5x |

**How to check SSI**: `https://www.linkedin.com/sales/ssi`

Average LinkedIn user scores ~25. Sales professionals should target 70-80+. An SSI above 65 combined with an acceptance rate above 40% and account age of 6+ months allows the most headroom.

---

## Sources

- [PhantomBuster: LinkedIn Automation Safe Limits 2026](https://phantombuster.com/blog/linkedin-automation/linkedin-automation-safe-limits-2026/) -- warmup schedule, daily limits by account age, profile view limits
- [Evaboot: LinkedIn Limits for Connection Requests & Messages 2026](https://evaboot.com/blog/linkedin-limits) -- weekly caps, character limits, bypass strategies
- [Dux-Soup: LinkedIn Automation Safety Guide 2026](https://www.dux-soup.com/blog/linkedin-automation-safety-guide-how-to-avoid-account-restrictions-in-2026) -- 3% rule, account type limits, detection triggers
- [Growleads: Is LinkedIn Automation Safe in 2026? The 23% Ban Risk Explained](https://growleads.io/blog/linkedin-automation-ban-risk-2026-safe-use/) -- ban risk percentages, restriction tiers, recovery protocol
- [Botdog: LinkedIn Warm-Up Strategy: Build Account Health in 30 Days](https://www.botdog.co/blog-posts/how-to-warm-up-linkedin-account) -- 4-week warmup plan, acceptance rate targets
- [LeadLoft: LinkedIn Limits in 2026 (Complete Breakdown)](https://www.leadloft.com/blog/linkedin-limits) -- comprehensive limit overview
- [LinkedSDR: LinkedIn Limits 2026 Complete Guide](https://www.linkedsdr.com/blog/linkedin-limits-complete-guide-to-connection-message-view-restrictions) -- view, connection, and message restrictions
- [LinkBoost: LinkedIn Automation Daily Limits & Guidelines 2026](https://blog.linkboost.co/linkedin-automation-daily-limits-guidelines-2026/) -- daily limit guidelines, timing
- [Expandi: LinkedIn Connections Limit](https://expandi.io/blog/linkedin-connections-limit/) -- connection limits, SSI impact
- [Closely: LinkedIn Automation Daily Limits 2025](https://blog.closelyhq.com/linkedin-automation-daily-limits-the-2025-safety-guidelines/) -- daily limits, warming protocols
- [SalesRobot: 42 LinkedIn Limits in 2026](https://www.salesrobot.co/blogs/linkedin-limits) -- comprehensive limit catalog
- [JoinValley: How Many LinkedIn Messages Can You Send Daily in 2025](https://www.joinvalley.co/blog/how-many-linkedin-messages-can-you-send-daily-in-2025) -- message limits by account type
- [Salesflow: Ultimate Guide to Safe LinkedIn Automation 2025](https://salesflow.io/blog/the-ultimate-guide-to-safe-linkedin-automation-in-2025) -- compliance tips
- [BearConnect: LinkedIn Automation Warning: What Triggers It in 2025](https://bearconnect.io/blog/linkedin-automation-tool-warning/) -- detection triggers
- [LinkedIn Help: Automated Activity on LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1340567) -- official policy
- [LinkedIn Help: Account Restrictions](https://www.linkedin.com/help/linkedin/answer/a1340522) -- official restriction info
- [LinkedIn Help: InMail Credits and Renewal](https://www.linkedin.com/help/linkedin/answer/a543695/inmail-message-credits-and-renewal-process) -- official InMail credit policy
- [Botdog: LinkedIn Premium Connection Request Limit 2026](https://www.botdog.co/blog-posts/linkedin-premium-connection-request-limit) -- premium-specific limits
- [Expandi: LinkedIn SSI Score](https://expandi.io/blog/linkedin-boost-ssi/) -- SSI thresholds and impact
