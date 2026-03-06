# Sprint 14-15: Multimodal Processing & Memory/Context Management

## Overview

This spec covers five backlog items that add document processing, long-term memory,
conversation summarization, and intent-aware tool routing to the leadgen pipeline.

---

## BL-262: RAG Long-Term Memory

### Problem
The AI agent has no memory across sessions. Users must re-explain preferences,
past decisions, and approved strategies every time they start a new conversation.
This breaks the "AI gets smarter with every cycle" vision principle.

### User Stories
- As a user, I want the AI to remember my approved strategies so I don't repeat myself.
- As a user, I want the AI to recall past decisions when making new recommendations.

### Acceptance Criteria

**Given** a user has approved a strategy in a previous session
**When** they start a new conversation about strategy
**Then** the agent retrieves the past approval as relevant context

**Given** the memory store has > 100 entries for a tenant
**When** a similarity search is performed
**Then** only the top-K most relevant results are returned (K=5 default)

**Given** a conversation contains an important decision
**When** the auto-save logic evaluates the message
**Then** it stores the decision with metadata (topic, decision_type, timestamp)

### Data Model

```sql
-- migrations/045_memory_embeddings.sql
CREATE TABLE memory_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'decision',
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    source_message_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_memory_embeddings_tenant ON memory_embeddings(tenant_id);
CREATE INDEX idx_memory_embeddings_vector ON memory_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### API Contracts

- `POST /api/memory/search` — `{query: str, top_k: int, filters: {content_type: str}}` -> `{results: [{content, score, metadata}]}`
- `POST /api/memory/save` — `{content: str, content_type: str, metadata: dict}` -> `{id: str}`

### Content Types
- `decision` — User approved or rejected a strategy/approach
- `preference` — User stated a preference (tone, industry focus, etc.)
- `insight` — AI-generated insight the user confirmed
- `constraint` — Business constraint or rule the user specified

---

## BL-263: Conversation Summarization

### Problem
Long conversations exhaust the context window. After ~15 messages, older context
gets truncated, losing important decisions and preferences from earlier in the chat.

### User Stories
- As a user, I want the AI to maintain context even in long conversations.
- As a developer, I want to keep token costs manageable for long sessions.

### Acceptance Criteria

**Given** a conversation with 16+ messages
**When** the summarization trigger fires
**Then** the oldest 10 messages are replaced with a ~200-token summary

**Given** a summary is generated
**When** it replaces older messages
**Then** it preserves: user decisions, approved strategies, rejected suggestions, key constraints

**Given** a conversation grows past 30 messages
**When** re-summarization triggers
**Then** the previous summary + next batch of messages are compacted into a new summary

### Design
- Trigger: message count > 15 in current thread
- Summarize: oldest 10 messages -> ~200 token summary
- Preserve in summaries: decisions, strategies, constraints, preferences
- Drop from summaries: filler, intermediate drafts, tool execution details
- Store summary in conversation metadata (JSONB field on strategy_chat_messages or separate column)
- Re-summarize when conversation grows past threshold again

---

## BL-264: Intent-Aware Tool Routing

### Problem
Every agent call sends all 24+ tool schemas (~2,500 tokens). Most turns only need
5-8 tools. This wastes tokens and can confuse the model with irrelevant options.

### User Stories
- As a developer, I want to reduce tool schema tokens from ~2.5K to ~600-1K per call.
- As a user, I want faster, more focused responses.

### Acceptance Criteria

**Given** a user message about strategy ("help me define my ICP")
**When** the intent classifier runs
**Then** only strategy-phase tools (12 tools) are included in the API call

**Given** a user message about contacts ("show me contacts in Germany")
**When** the intent classifier runs
**Then** only contact-phase tools (9 tools) are included

**Given** an ambiguous message
**When** the intent classifier runs
**Then** it defaults to the full tool set (no filtering)

### Intent -> Tool Mapping
- `strategy`: get_strategy, save_strategy, get_strategy_feedback, analyze_company_portfolio, analyze_contact_portfolio, count_contacts, count_companies, list_contacts, list_companies, web_search, search_memory, save_insight
- `contacts`: count_contacts, count_companies, list_contacts, list_companies, analyze_contact_portfolio, analyze_company_portfolio, search_memory, web_search, save_insight
- `messages`: generate_messages, review_messages, search_memory, save_insight
- `campaign`: create_campaign, update_campaign, get_campaign_stats, search_memory, web_search, save_insight
- `general`: all tools (fallback)

### Implementation
- Keyword + heuristic classifier (no LLM call for classification)
- Falls back to full tool set on ambiguity
- Integrates as a filtering step in the tool registry

---

## BL-265: PDF + Image Processing

### Problem
Users have business documents (PDFs, images) containing ICP definitions, market
research, competitor analysis, etc. They must manually copy-paste content into chat.

### User Stories
- As a user, I want to upload a PDF and have the AI extract and use its content.
- As a user, I want to upload screenshots/images for the AI to analyze.

### Acceptance Criteria

**Given** a user uploads a 10-page PDF with text
**When** extraction completes
**Then** the full text is extracted and a summary is generated

**Given** a user uploads an image-heavy PDF (< 100 chars/page)
**When** extraction runs
**Then** it falls back to Claude vision API for those pages

**Given** a user uploads a file > 50MB
**When** the upload endpoint is called
**Then** it returns 413 with a clear error message

**Given** a user uploads an unsupported file type (.exe, .zip)
**When** the upload endpoint is called
**Then** it returns 415 with supported formats listed

**Given** a file is being processed
**When** the user checks status
**Then** they see: pending, processing, completed, or failed

### Data Model

```sql
-- migrations/044_file_uploads.sql
CREATE TABLE file_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(127) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE extracted_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES file_uploads(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL DEFAULT 'full_text',
    content_text TEXT,
    content_summary TEXT,
    page_range VARCHAR(50),
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_file_uploads_tenant ON file_uploads(tenant_id);
CREATE INDEX idx_file_uploads_status ON file_uploads(processing_status);
CREATE INDEX idx_extracted_content_file ON extracted_content(file_id);
```

### API Contracts

- `POST /api/files/upload` — multipart/form-data with `file` field -> `{file_id, filename, status}`
- `GET /api/files/<file_id>` — get file metadata + extraction status
- `GET /api/files/<file_id>/content` — get extracted content (summary by default, full with `?detail=full`)
- `GET /api/files` — list uploaded files for tenant
- `DELETE /api/files/<file_id>` — delete file and extracted content

### Processing Pipeline
1. Upload: validate size (< 50MB), validate mime type, store to local `/uploads` (dev) or S3 (prod)
2. Extract: dispatch by mime type -> PDF extractor, image extractor
3. Summarize: LLM summarization of extracted text -> ~500 token summary
4. Store: save full text + summary to extracted_content table
5. Inject: when referenced in chat, inject L1 summary; L2 full text via tool call

### Progressive Detail Levels
- L0: mention (~20 tokens) — "User uploaded quarterly-report.pdf (10 pages)"
- L1: summary (~500 tokens) — key findings, data points, conclusions
- L2: full text (on-demand via tool) — complete extracted content

### Token Budget
- Multimodal content <= 8K tokens total per agent call
- If multiple files referenced, distribute budget proportionally

---

## BL-266: HTML + Word Processing

### Problem
Users also have Word documents and web pages with relevant business content
(competitor pages, industry reports, proposals).

### User Stories
- As a user, I want to upload .docx files for the AI to analyze.
- As a user, I want to paste a URL and have the AI fetch and analyze the page.

### Acceptance Criteria

**Given** a user uploads a .docx file
**When** extraction completes
**Then** text and tables are extracted as markdown with structure preserved

**Given** a user provides a URL
**When** the fetch-and-process pipeline runs
**Then** the page content is extracted (boilerplate removed) and summarized

**Given** a URL returns a 404 or timeout
**When** processing fails
**Then** the error is recorded and the user sees a clear failure message

### Processing
- Word: `python-docx` for text/table extraction -> markdown output
- HTML: `trafilatura` for content extraction with boilerplate removal
- URL auto-fetch: detect URL in upload -> fetch -> extract -> summarize
- Same storage pipeline as BL-265 (file_uploads + extracted_content tables)

### Supported MIME Types (combined BL-265 + BL-266)
- `application/pdf` — PDF extraction
- `image/jpeg`, `image/png`, `image/webp`, `image/gif` — Image analysis
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` — Word
- `text/html` — HTML content extraction
- `application/octet-stream` — detected by file extension

---

## Error Handling (all items)

| Error | HTTP Status | Response |
|-------|-------------|----------|
| File too large (> 50MB) | 413 | `{"error": "File too large. Maximum size is 50MB."}` |
| Unsupported format | 415 | `{"error": "Unsupported file type. Supported: PDF, DOCX, JPEG, PNG, HTML"}` |
| Extraction failure | 500 | `{"error": "Failed to extract content from file."}` + logged |
| No embedding API key | 503 | `{"error": "Embedding service not configured."}` |
| pgvector not installed | 503 | `{"error": "Vector search not available."}` |

## Security
- File uploads validated: size, mime type, filename sanitization
- Files stored with UUID filenames (no user-controlled paths)
- All endpoints require JWT auth + tenant isolation
- URL fetching has timeout (10s) and size limit (10MB response)
- No executable files accepted
