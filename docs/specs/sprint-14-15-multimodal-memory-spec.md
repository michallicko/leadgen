# Sprint 14-15: Memory, Intelligence & Multimodal Processing

> Spec document — March 2026

## Overview

This spec covers 5 backlog items across 2 sprints:
- **Sprint 14 (Memory & Intelligence)**: BL-262, BL-263, BL-264
- **Sprint 15 (Multimodal Phase 1+2)**: BL-265, BL-266

---

## BL-262: RAG Long-Term Memory

### Problem Statement

The AI agent currently has no memory across chat sessions. When a user starts a new conversation, all prior context (decisions, preferences, company research, validated assumptions) is lost. The user must re-explain their situation every time. This contradicts the product vision of an AI that "gets smarter with every cycle."

### User Stories

1. As a founder, I want the AI to remember my previous research findings so I don't repeat the same questions every session.
2. As a founder, I want the AI to recall my ICP preferences from last week's session when I start a new conversation.
3. As a founder, I want the AI to build on previous strategy iterations without losing earlier context.

### Acceptance Criteria

**Given** a user has discussed their ICP targeting in a previous session,
**When** they start a new session and ask "What was our ICP?",
**Then** the agent retrieves and references the previously discussed ICP details.

**Given** a user uploads a competitor analysis in session 1,
**When** they discuss competitive positioning in session 2,
**Then** the agent has access to key findings from the competitor analysis.

**Given** the memory store has entries from multiple sessions,
**When** the agent retrieves context for a new turn,
**Then** only semantically relevant memories are injected (not all memories).

**Given** a tenant has accumulated many memories,
**When** retrieving context,
**Then** memories are filtered by tenant_id and relevance score, with a configurable token budget.

### Technical Approach (EM)

**Architecture**: Keyword-based retrieval with LLM re-ranking (MVP). Upgradeable to pgvector embeddings later.

**Files to create:**
- `api/services/memory/` directory
- `api/services/memory/__init__.py`
- `api/services/memory/rag_store.py` — core storage + retrieval logic
- `migrations/044_memory_facts.sql`
- `tests/unit/test_rag_store.py`

**Database schema** (`memory_facts` table):
```sql
CREATE TABLE memory_facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    playbook_id UUID REFERENCES strategy_documents(id),
    source_message_id UUID REFERENCES strategy_chat_messages(id),
    chunk_text TEXT NOT NULL,
    chunk_type VARCHAR(20) NOT NULL DEFAULT 'fact',
    keywords TEXT[] DEFAULT '{}',
    session_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_memory_facts_tenant ON memory_facts(tenant_id);
CREATE INDEX idx_memory_facts_keywords ON memory_facts USING gin(keywords);
```

**Flow:**
1. After each agent turn, extract key facts/decisions from the conversation
2. Store as text chunks with type classification (fact, decision, preference, research)
3. On new session/turn, query by tenant + keyword relevance
4. Inject top-K relevant memories into system prompt context layer
5. Token budget: max 1,500 tokens for memory injection per turn

**Dependencies**: None (uses existing PG + Anthropic client)

**Test plan:**
- Unit test: store fact -> retrieve by keyword -> verify ranking
- Unit test: tenant isolation
- Unit test: token budget enforcement
- Unit test: fact extraction from conversation messages

### Success Metrics
- Cross-session context retention rate > 80%
- Memory retrieval latency < 200ms
- Token overhead per turn < 1,500 tokens

---

## BL-263: Conversation Summarization

### Problem Statement

The current implementation includes the last 20 messages verbatim. This wastes tokens (2-4K per turn) and loses important early context after 20 messages.

### User Stories

1. As a founder, I want the AI to remember earlier discussion points even in long conversations.
2. As a founder, I want faster responses because the AI sends less data per request.

### Acceptance Criteria

**Given** a conversation with 25 messages,
**When** the agent processes a new turn,
**Then** messages 1-15 are represented as a compressed summary, and messages 16-25 are included verbatim.

**Given** a conversation summary exists,
**When** the user references a decision from message 5,
**Then** the summary preserves that decision and the agent can reference it.

**Given** a conversation with fewer than the window size messages,
**When** the agent processes a turn,
**Then** no summarization occurs.

### Technical Approach (EM)

**Files to create:**
- `api/services/memory/conversation_manager.py`
- `tests/unit/test_conversation_manager.py`

**Algorithm:**
1. Window size: `RECENT_WINDOW = 10` messages
2. When message count > RECENT_WINDOW: compress older messages via Claude Haiku
3. Summary preserves: decisions, preferences, findings, action items
4. Store summary in `StrategyChatMessage` with `role='system'` and `extra.type='conversation_summary'`
5. Re-summarize every 10 new messages after initial summary

**Integration**: Modify `playbook_service.py` `format_messages_for_api()` to use floating window.

**Test plan:**
- Unit test: messages below window -> no summarization
- Unit test: messages above window -> summary + recent preserved
- Unit test: summary preserves key decisions (mock LLM)
- Unit test: re-summarization trigger

### Success Metrics
- Token reduction: 40-60% on conversations > 20 messages
- Context preservation: key decisions in 95%+ of summaries

---

## BL-264: Intent-Aware Tool Routing

### Problem Statement

Every agent call includes all 24 tool definitions (~2,500 tokens). Most turns need 5-8 tools. Irrelevant tools waste tokens and confuse the model.

### User Stories

1. As the system, I want to send only relevant tools to reduce token cost by ~60%.
2. As a founder in the strategy phase, I want the AI to focus on strategy tools.

### Acceptance Criteria

**Given** a user is in the "strategy" phase,
**When** the agent processes a turn,
**Then** only strategy tools are included; campaign tools excluded.

**Given** a user is in the "contacts" phase,
**When** the agent processes a turn,
**Then** only contacts tools are included.

**Given** any phase,
**When** the agent needs cross-phase tools,
**Then** universal tools (web_search, get_strategy_document) are always available.

### Technical Approach (EM)

**Files to create:**
- `api/services/tool_router.py`
- `tests/unit/test_tool_router.py`

**Phase-to-tools mapping** + universal tools always included. Router function filters `get_tools_for_api()` by phase + page_context.

**Integration**: Replace `get_tools_for_api()` in chat route with `get_tools_for_context(phase, page_context)`.

**Test plan:**
- Unit test: strategy phase -> only strategy tools
- Unit test: contacts phase -> only contacts tools
- Unit test: universal tools always present
- Unit test: page_context override
- Unit test: unknown phase -> universal only

### Success Metrics
- Tool schema tokens reduced from ~2,500 to ~800-1,200
- No regression in tool availability

---

## BL-265: PDF + Image Processing

### Problem Statement

The agent operates on text only. B2B research involves PDFs, images, and visual content that users must manually describe.

### User Stories

1. As a founder, I want to upload a PDF and have the AI analyze it.
2. As a founder, I want to upload an image and get AI analysis.
3. As a founder, I want cost estimates before expensive visual processing.

### Acceptance Criteria

**Given** a text-heavy PDF upload,
**When** processed,
**Then** text and tables extracted via pdfplumber, summary generated.

**Given** a scanned PDF,
**When** text extraction yields < 100 chars/page,
**Then** falls back to Claude vision API.

**Given** an image upload (PNG/JPEG),
**When** processed,
**Then** sent to Claude vision API for analysis.

### Technical Approach (EM)

**Files to create:**
- `api/services/multimodal/` directory
- `api/services/multimodal/__init__.py`
- `api/services/multimodal/pdf_processor.py`
- `api/services/multimodal/image_processor.py`
- `api/services/multimodal/document_store.py`
- `api/tools/__init__.py`
- `api/tools/multimodal_tools.py`
- `migrations/045_file_uploads.sql`
- `tests/unit/test_pdf_processor.py`
- `tests/unit/test_image_processor.py`

**Database**: `file_uploads` + `extracted_content` tables.

**Dependencies**: `pdfplumber`, `Pillow`

### Success Metrics
- PDF text extraction accuracy > 90%
- Processing latency < 10s for 10-page PDF

---

## BL-266: HTML + Word Processing

### Problem Statement

Users frequently want the AI to analyze competitor websites and Word documents but must copy-paste content manually.

### User Stories

1. As a founder, I want to paste a URL and have the AI analyze the page.
2. As a founder, I want to upload a .docx and have the AI extract key info.

### Acceptance Criteria

**Given** a URL to a website,
**When** processed,
**Then** main content extracted (boilerplate removed), summarized.

**Given** a .docx upload,
**When** processed,
**Then** paragraphs, tables, and headings extracted as markdown.

### Technical Approach (EM)

**Files to create:**
- `api/services/multimodal/html_processor.py`
- `api/services/multimodal/word_processor.py`
- `tests/unit/test_html_processor.py`
- `tests/unit/test_word_processor.py`

**Dependencies**: `trafilatura`, `python-docx`

SSRF protection: reuse existing validation (test_ssrf_validation.py exists).

### Success Metrics
- HTML extraction accuracy > 85%
- Word parsing covers paragraphs, tables, headings

---

## Implementation Order

1. BL-264 (Tool Router) — no dependencies, immediate savings
2. BL-263 (Conversation Summarization) — no dependencies
3. BL-262 (RAG Memory) — builds on conversation patterns
4. BL-265 (PDF + Image) — needs migration, file storage
5. BL-266 (HTML + Word) — extends multimodal from BL-265
