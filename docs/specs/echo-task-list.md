# Spec: Echo Task List — Living Prioritized Task Board (BL-053)

**Date**: 2026-02-23 | **Status**: Spec'd
**Priority**: Should Have | **Effort**: L
**Dependencies**: AGENT (agent-ready chat architecture)

---

## Problem Statement

The Echo tab is currently a placeholder ("Echo Analytics — outreach performance dashboard"). Meanwhile, users have no unified view of what to do next. Tasks come from multiple sources — the user's own intentions, AI-generated recommendations from strategy/enrichment/campaign analysis, and system events like enrichment completion or failed sends — but none of these surface as actionable items in the app.

This means:
- The AI strategist can advise, but cannot track whether advice was acted on.
- System events (enrichment done, campaign stalled, send failure) require the user to manually check each section.
- User intentions expressed in chat ("I need to follow up with Acme") are lost in conversation history.
- There is no feedback loop: the AI cannot learn which suggestions the user values.
- The founder has no single "what should I do next?" dashboard.

## User Stories

### Manual Tasks
1. As a founder, I want to type "remind me to follow up with Acme next Tuesday" in chat and have it appear as a task, so my intentions are captured without switching context.
2. As a founder, I want to manually create a task from the Echo tab with a title, description, and optional due date, so I have a quick-entry fallback.

### AI-Generated Tasks
3. As a founder, I want the AI to proactively suggest tasks based on my strategy (e.g., "Your ICP mentions SaaS companies but you have no outreach campaign targeting them"), so I get strategic nudges.
4. As a founder, I want the AI to generate tasks from enrichment results (e.g., "3 new Tier 1 companies discovered — review and start outreach"), so I act on new intelligence quickly.
5. As a founder, I want the AI to suggest tasks from campaign performance (e.g., "Reply rate dropped below 5% on DACH campaign — consider revising messaging"), so I catch performance issues early.

### System Alerts
6. As a founder, I want to see system-generated alerts as tasks (e.g., "Enrichment batch complete: 12 companies enriched, 3 failed"), so I know when pipeline stages finish.
7. As a founder, I want failed operations to appear as actionable tasks (e.g., "Email send failed for 2 contacts — review errors"), so nothing falls through the cracks.

### Task Management
8. As a founder, I want to see all tasks in a single prioritized list, sorted by urgency and strategic importance, so I always know what to do next.
9. As a founder, I want to mark tasks as done, snooze them, or dismiss them, so the list stays clean and actionable.
10. As a founder, I want to ask the AI "what should I focus on today?" and get a prioritized answer based on my task list and current context, so the AI acts as my executive assistant.

### Chat Integration
11. As a founder, I want to tell the AI "add a task to review the new enrichment results" and have it create the task, so task creation is conversational.
12. As a founder, I want the AI to reference my task list when giving advice (e.g., "You have 3 overdue follow-ups — want me to draft messages for them?"), so the strategist is aware of my commitments.

---

## Acceptance Criteria

### AC-1: Manual Task Creation via Chat

**Given** the AI chat has the `add_task` tool available
**When** a user says "remind me to call the Acme team on Thursday"
**Then** the AI:
1. Calls `add_task` with `{title: "Call the Acme team", due_date: "2026-02-26", source: "manual", priority: "medium"}`
2. Responds: "Added to your task list: 'Call the Acme team' — due Thursday. I'll bump it up on your list as the date approaches."

**Given** the user says "I need to review the Q1 campaign results"
**When** the AI processes this as an intention
**Then** it asks: "Want me to add 'Review Q1 campaign results' to your task list? I can set a priority based on your current workload."

### AC-2: Manual Task Creation via UI

**Given** the user is on the Echo tab
**When** they click the "Add Task" button and fill in title "Prepare board presentation" with due date next Friday
**Then** a new task appears in the list with source "manual", priority "medium", and the specified due date.

**Given** the task form is submitted with no title
**When** validation runs
**Then** an error message appears: "Task title is required."

### AC-3: AI-Generated Strategy Tasks

**Given** the strategy document mentions "target SaaS companies in DACH region"
**When** the AI analyzes the strategy and finds no active campaign matching this criterion
**Then** a task is created: `{title: "Create outreach campaign for DACH SaaS companies", source: "ai_strategy", priority: "high", linked_entity_type: "strategy_document", description: "Your strategy targets DACH SaaS companies but no active campaign covers this segment."}`

**Given** an AI-generated task already exists for the same recommendation
**When** the AI would create a duplicate
**Then** no new task is created; the existing task's `updated_at` is refreshed.

### AC-4: System Alert Tasks

**Given** an enrichment pipeline run completes
**When** the system processes the completion event
**Then** a task is created: `{title: "Review enrichment results: 12 companies enriched, 3 failed", source: "system", priority: "medium", linked_entity_type: "pipeline_run", linked_entity_id: "<run_id>"}`

**Given** an email send fails for 2 contacts
**When** the failure is recorded
**Then** a task is created: `{title: "Fix failed email sends (2 contacts)", source: "system", priority: "high", linked_entity_type: "campaign", linked_entity_id: "<campaign_id>"}`

### AC-5: Task Prioritization

**Given** the user has 10 tasks (3 overdue, 2 high-priority, 5 normal)
**When** they view the Echo tab
**Then** tasks are ordered: overdue items first (sorted by how overdue), then high-priority by due date, then medium/low by due date.

**Given** the user asks the AI "what should I focus on today?"
**When** the AI calls `get_prioritized_tasks`
**Then** it responds with the top 3-5 tasks, explaining why each matters: "Here's your priority list for today: 1. **Follow up with Acme** (overdue by 2 days — they showed strong buying signals). 2. **Review enrichment results** (3 new Tier 1 companies found yesterday)..."

### AC-6: Task Lifecycle

**Given** a task exists with status "open"
**When** the user clicks "Done" on the task
**Then** the task status changes to "completed" and it moves to a "Recently Completed" section.

**Given** a task exists with status "open"
**When** the user clicks "Snooze" and selects "Tomorrow"
**Then** the task's `snoozed_until` is set to tomorrow 9:00 AM and it disappears from the active list until then.

**Given** a task exists with status "open"
**When** the user clicks "Dismiss"
**Then** the task status changes to "dismissed" and it is hidden from the active list (visible in "Dismissed" filter).

### AC-7: Chat Tool Integration

**Given** the AI has access to `add_task`, `update_task`, `complete_task`, `get_prioritized_tasks`, and `suggest_tasks` tools
**When** the user says "mark the Acme follow-up as done"
**Then** the AI calls `complete_task` with the matching task ID and responds: "Done! Marked 'Follow up with Acme' as completed. You have 7 remaining tasks."

**Given** the user says "reprioritize my tasks"
**When** the AI calls `suggest_tasks`
**Then** it analyzes the current task list against strategy, campaign status, and enrichment data, and suggests reordering with explanations.

### AC-8: Linked Entity Navigation

**Given** a task has `linked_entity_type: "company"` and `linked_entity_id: "<uuid>"`
**When** the user clicks the linked entity badge on the task
**Then** they navigate to the company detail view.

**Given** a task has `linked_entity_type: "campaign"` and `linked_entity_id: "<uuid>"`
**When** the user clicks the linked entity badge
**Then** they navigate to the campaign detail view.

---

## Data Model

### `tasks` Table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | `uuid_generate_v4()` | Primary key |
| `tenant_id` | UUID (FK tenants) | NO | — | Multi-tenant isolation |
| `user_id` | UUID (FK users) | YES | — | Creator (null for system tasks) |
| `title` | TEXT | NO | — | Short task description |
| `description` | TEXT | YES | — | Detailed description/context |
| `source` | TEXT | NO | `'manual'` | One of: `manual`, `ai_strategy`, `ai_enrichment`, `ai_campaign`, `system` |
| `priority` | TEXT | NO | `'medium'` | One of: `critical`, `high`, `medium`, `low` |
| `status` | TEXT | NO | `'open'` | One of: `open`, `completed`, `dismissed`, `snoozed` |
| `due_date` | DATE | YES | — | Optional deadline |
| `snoozed_until` | TIMESTAMPTZ | YES | — | When to resurface a snoozed task |
| `linked_entity_type` | TEXT | YES | — | Entity type: `company`, `contact`, `campaign`, `pipeline_run`, `strategy_document`, `message` |
| `linked_entity_id` | UUID | YES | — | ID of the linked entity |
| `ai_context` | JSONB | YES | `'{}'` | AI reasoning for why this task was created/prioritized |
| `dedup_key` | TEXT | YES | — | Prevents duplicate AI/system tasks (unique per tenant) |
| `completed_at` | TIMESTAMPTZ | YES | — | When the task was completed |
| `created_at` | TIMESTAMPTZ | NO | `now()` | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Last update timestamp |

**Indexes:**
- `idx_tasks_tenant_status` on `(tenant_id, status)` — main list query
- `idx_tasks_tenant_dedup` UNIQUE on `(tenant_id, dedup_key)` WHERE `dedup_key IS NOT NULL` — prevent duplicates
- `idx_tasks_due_date` on `(tenant_id, due_date)` WHERE `status = 'open'` — prioritization queries

**SQLAlchemy model:**

```python
class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    source = db.Column(db.Text, nullable=False, default="manual")
    priority = db.Column(db.Text, nullable=False, default="medium")
    status = db.Column(db.Text, nullable=False, default="open")
    due_date = db.Column(db.Date)
    snoozed_until = db.Column(db.DateTime(timezone=True))
    linked_entity_type = db.Column(db.Text)
    linked_entity_id = db.Column(UUID(as_uuid=False))
    ai_context = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    dedup_key = db.Column(db.Text)
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
```

---

## API Contracts

### `GET /api/tasks`

List tasks for the current tenant. Supports filtering and pagination.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `open` | Filter: `open`, `completed`, `dismissed`, `snoozed`, `all` |
| `source` | string | — | Filter by source type |
| `priority` | string | — | Filter by priority level |
| `linked_entity_type` | string | — | Filter by linked entity type |
| `limit` | int | 50 | Max results (1-100) |
| `offset` | int | 0 | Pagination offset |

**Response (200):**
```json
{
  "tasks": [
    {
      "id": "uuid",
      "title": "Follow up with Acme",
      "description": "They showed interest in the AI automation pitch",
      "source": "manual",
      "priority": "high",
      "status": "open",
      "due_date": "2026-02-25",
      "snoozed_until": null,
      "linked_entity_type": "company",
      "linked_entity_id": "uuid",
      "ai_context": {},
      "created_at": "2026-02-23T10:00:00Z",
      "updated_at": "2026-02-23T10:00:00Z"
    }
  ],
  "total": 42,
  "has_more": true
}
```

**Sort order:** Overdue first (by days overdue DESC), then by priority (critical > high > medium > low), then by due_date ASC (soonest first), then by created_at DESC.

### `POST /api/tasks`

Create a new task.

**Request Body:**
```json
{
  "title": "Review enrichment results",
  "description": "3 new Tier 1 companies found in batch-5",
  "source": "manual",
  "priority": "medium",
  "due_date": "2026-02-25",
  "linked_entity_type": "pipeline_run",
  "linked_entity_id": "uuid",
  "dedup_key": "enrichment_complete_batch5"
}
```

**Response (201):** The created task object.

**Dedup behavior:** If `dedup_key` is provided and a task with the same `tenant_id` + `dedup_key` already exists with status `open`, return 200 with the existing task (updated `updated_at`). This prevents duplicate system/AI tasks.

### `PATCH /api/tasks/<id>`

Update a task's fields.

**Request Body (partial):**
```json
{
  "status": "completed",
  "priority": "high",
  "due_date": "2026-02-28"
}
```

**Response (200):** The updated task object.

**Status transitions:**
- `open` -> `completed` (sets `completed_at`)
- `open` -> `dismissed`
- `open` -> `snoozed` (requires `snoozed_until`)
- `snoozed` -> `open` (clears `snoozed_until`)
- `completed` -> `open` (clears `completed_at`, reopens)
- `dismissed` -> `open` (reopens)

### `DELETE /api/tasks/<id>`

Hard-delete a task. Only the task creator or tenant admin can delete.

**Response (204):** No content.

### `POST /api/tasks/prioritize`

AI-powered reprioritization of the task list. Analyzes all open tasks against strategy, campaign status, enrichment data, and due dates.

**Request Body:**
```json
{
  "context": "optional additional context from user"
}
```

**Response (200):**
```json
{
  "suggestions": [
    {
      "task_id": "uuid",
      "current_priority": "medium",
      "suggested_priority": "high",
      "reason": "Acme Corp just completed L2 enrichment and scored Tier 1 — follow up while fresh"
    }
  ]
}
```

---

## Chat Tool Definitions

Tools are registered in the agent-ready chat framework (depends on BL-011 / AGENT). Each tool is callable by the AI during conversation.

### `add_task`

**Description:** Create a new task on the user's task list.

**Parameters:**
```json
{
  "title": {"type": "string", "required": true, "description": "Short task description"},
  "description": {"type": "string", "description": "Detailed context"},
  "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"], "default": "medium"},
  "due_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD deadline"},
  "linked_entity_type": {"type": "string", "enum": ["company", "contact", "campaign", "pipeline_run", "strategy_document", "message"]},
  "linked_entity_id": {"type": "string", "format": "uuid"}
}
```

**Returns:** The created task object.

### `update_task`

**Description:** Update an existing task (priority, due date, description, status).

**Parameters:**
```json
{
  "task_id": {"type": "string", "format": "uuid", "required": true},
  "title": {"type": "string"},
  "description": {"type": "string"},
  "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
  "due_date": {"type": "string", "format": "date"},
  "status": {"type": "string", "enum": ["open", "snoozed"]},
  "snoozed_until": {"type": "string", "format": "datetime"}
}
```

**Returns:** The updated task object.

### `complete_task`

**Description:** Mark a task as completed.

**Parameters:**
```json
{
  "task_id": {"type": "string", "format": "uuid", "required": true}
}
```

**Returns:** The completed task object with `completed_at` set.

### `get_prioritized_tasks`

**Description:** Get the user's prioritized task list with context for AI reasoning.

**Parameters:**
```json
{
  "limit": {"type": "integer", "default": 10, "description": "Max tasks to return"},
  "include_completed": {"type": "boolean", "default": false}
}
```

**Returns:** Array of task objects sorted by priority algorithm.

### `suggest_tasks`

**Description:** Analyze the user's strategy, campaigns, enrichment results, and current task list to suggest new tasks or reprioritize existing ones.

**Parameters:**
```json
{
  "focus_area": {"type": "string", "enum": ["strategy", "enrichment", "campaigns", "all"], "default": "all"}
}
```

**Returns:** Array of suggested tasks (not yet created) and priority adjustment recommendations for existing tasks. The AI presents these to the user for approval before creating.

---

## UI Wireframes (Text Descriptions)

### Echo Tab — Task Board Layout

```
+------------------------------------------------------------------+
| Echo                                                    [+ Add]  |
+------------------------------------------------------------------+
| Filters: [All] [Overdue] [High Priority] [AI Suggested] [System] |
+------------------------------------------------------------------+
|                                                                    |
| OVERDUE (2)                                              [Collapse]|
| +--------------------------------------------------------------+ |
| | ! Follow up with Acme Corp              Due: Feb 21 (2d ago) | |
| |   Source: Manual | Priority: HIGH | [Company: Acme Corp ->]  | |
| |   [Done] [Snooze v] [Dismiss]                                | |
| +--------------------------------------------------------------+ |
| | ! Review failed email sends (2 contacts)    Due: Feb 22 (1d) | |
| |   Source: System | Priority: HIGH | [Campaign: DACH Q1 ->]   | |
| |   [Done] [Snooze v] [Dismiss]                                | |
| +--------------------------------------------------------------+ |
|                                                                    |
| TODAY (3)                                                          |
| +--------------------------------------------------------------+ |
| | * Create outreach for DACH SaaS companies      Due: Today    | |
| |   Source: AI Strategy | Priority: HIGH                        | |
| |   "Your strategy targets DACH SaaS but no campaign exists"   | |
| |   [Done] [Snooze v] [Dismiss]                                | |
| +--------------------------------------------------------------+ |
| | * Review enrichment: 12 companies enriched      Due: Today   | |
| |   Source: System | Priority: MEDIUM | [Pipeline Run ->]      | |
| |   [Done] [Snooze v] [Dismiss]                                | |
| +--------------------------------------------------------------+ |
| | * Prepare messaging for Tier 1 prospects        Due: Today   | |
| |   Source: AI Campaign | Priority: MEDIUM                      | |
| |   [Done] [Snooze v] [Dismiss]                                | |
| +--------------------------------------------------------------+ |
|                                                                    |
| UPCOMING (5)                                                       |
| +--------------------------------------------------------------+ |
| | Review Q1 campaign performance           Due: Feb 28          | |
| | Call board advisor re: pricing           Due: Mar 1           | |
| | ...                                                           | |
| +--------------------------------------------------------------+ |
|                                                                    |
| RECENTLY COMPLETED (3)                            [Show all ->]   |
| +--------------------------------------------------------------+ |
| | [check] Set up DACH campaign sequence    Completed: 2h ago    | |
| | [check] Import LinkedIn connections      Completed: Yesterday | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

### Task Card Components

Each task card shows:
- **Priority indicator**: Red dot (critical), orange (high), blue (medium), gray (low)
- **Title**: Bold, truncated at 80 chars
- **Source badge**: Color-coded pill — "Manual" (gray), "AI Strategy" (purple), "AI Campaign" (cyan), "System" (amber)
- **Due date**: Relative ("Today", "Tomorrow", "Feb 28") with red styling if overdue
- **Linked entity**: Clickable badge linking to company/campaign/contact detail
- **AI context**: Collapsed by default; expandable to show AI reasoning
- **Actions**: Done (check icon), Snooze (clock dropdown: tomorrow, next week, next month, custom), Dismiss (x icon)

### Add Task Modal

```
+------------------------------------------+
| Add Task                            [X]  |
+------------------------------------------+
| Title *                                   |
| [________________________________]       |
|                                          |
| Description                               |
| [________________________________]       |
| [________________________________]       |
|                                          |
| Priority    [Medium v]                    |
| Due Date    [__ / __ / ____]             |
|                                          |
| Link to     [None v]  [Select entity...] |
|                                          |
|              [Cancel]  [Add Task]        |
+------------------------------------------+
```

---

## Integration Points

### Enrichment Pipeline -> Tasks

**Trigger:** `PipelineRun` completes (status changes to `completed` or `failed`).
**Task created:**
- Title: "Review enrichment results: {done} companies enriched, {failed} failed"
- Source: `system`
- Priority: `high` if failures > 0, `medium` otherwise
- Linked entity: `pipeline_run`
- Dedup key: `pipeline_complete_{run_id}`

### Campaign Performance -> Tasks

**Trigger:** Daily analysis job (or on-demand via `suggest_tasks` tool).
**Conditions checked:**
- Reply rate below threshold -> "Campaign '{name}' reply rate dropped to {rate}% — review messaging"
- Campaign stuck in draft > 7 days -> "Campaign '{name}' has been in draft for {days} days — ready to launch?"
- All messages generated -> "Campaign '{name}' has {count} messages ready for review"

### Strategy Analysis -> Tasks

**Trigger:** Strategy document update (debounced, max once per hour) or on-demand via `suggest_tasks`.
**Conditions checked:**
- ICP defined but no matching campaign -> "Create campaign targeting {segment}"
- Strategy section empty/placeholder -> "Complete the {section} section of your strategy"
- Strategy mentions competitors not in enrichment data -> "Research competitor: {name}"

### Email/LinkedIn Send -> Tasks

**Trigger:** `EmailSendLog` or `LinkedInSendQueue` entry with status `failed`.
**Task created:**
- Title: "Fix failed {channel} send for {contact_name}"
- Source: `system`
- Priority: `high`
- Linked entity: `message`
- Dedup key: `send_fail_{message_id}`

---

## Edge Cases

### Empty Task List
When no tasks exist, show an empty state:
- Illustration + "All clear! No tasks right now."
- Subtitle: "Tasks will appear here as you work — from your conversations with the AI, enrichment results, and campaign activity."
- CTA button: "Add your first task" (opens modal)

### Too Many Tasks (> 50 open)
- Group by priority section (Critical, High, Medium, Low) with collapse/expand
- Show count per section in section headers
- AI proactively suggests: "You have {count} open tasks. Want me to help prioritize and dismiss stale ones?"

### Stale Tasks
- Tasks open for > 14 days without activity get a "Stale" badge
- AI can suggest: "You have {count} tasks older than 2 weeks. Review and close or snooze?"

### Conflicting Priorities
- When the AI suggests a priority different from the user's, it explains but defers to the user
- User can always manually override AI priority suggestions

### Duplicate Prevention
- `dedup_key` prevents identical system/AI tasks
- For AI-generated tasks, dedup_key format: `{source}_{entity_type}_{entity_id}_{intent_hash}`
- Manual tasks have no dedup_key (users can create duplicates)

### Snoozed Task Resurfacing
- Background job (or on-request check) moves snoozed tasks back to `open` when `snoozed_until <= now()`
- Alternatively: query filters snoozed tasks at read time (`WHERE status = 'open' OR (status = 'snoozed' AND snoozed_until <= now())`)

### Task Created for Deleted Entity
- If the linked entity is deleted, the task remains but the entity link shows "Entity removed"
- Task can still be completed/dismissed normally

---

## Migration

**Migration number:** Next available (e.g., `032_echo_task_list.sql`)

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    due_date DATE,
    snoozed_until TIMESTAMPTZ,
    linked_entity_type TEXT,
    linked_entity_id UUID,
    ai_context JSONB DEFAULT '{}'::jsonb,
    dedup_key TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_tenant_status ON tasks(tenant_id, status);
CREATE UNIQUE INDEX idx_tasks_tenant_dedup ON tasks(tenant_id, dedup_key) WHERE dedup_key IS NOT NULL;
CREATE INDEX idx_tasks_due_date ON tasks(tenant_id, due_date) WHERE status = 'open';
```

---

## Implementation Notes

- **No Airtable dependency**: Tasks table is PostgreSQL-only.
- **Follows existing patterns**: UUID PKs, `tenant_id` FK, `created_at`/`updated_at`, JSONB for flexible data.
- **Chat tools depend on AGENT (BL-011)**: The tool definitions above are designed to plug into the agent-ready chat architecture. Until AGENT is built, manual task creation via UI and system alerts can ship independently.
- **System task generation can be phased**: Phase 1 (manual + UI), Phase 2 (system alerts from pipeline/send events), Phase 3 (AI-generated suggestions from strategy/campaign analysis).
- **Prioritization algorithm is deterministic first**: Start with simple sort (overdue > priority > due date > created). AI-powered reprioritization (`/api/tasks/prioritize`) is an enhancement.
