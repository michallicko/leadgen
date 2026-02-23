-- Migration 034: Tool execution audit log
-- Tracks every tool call made by the AI agent during chat conversations.
-- Supports the agentic loop in AGENT spec (agent-ready-chat.md).

CREATE TABLE IF NOT EXISTS tool_executions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID REFERENCES users(id),
    document_id     UUID REFERENCES strategy_documents(id),
    chat_message_id UUID REFERENCES strategy_chat_messages(id) ON DELETE SET NULL,
    tool_name       VARCHAR(100) NOT NULL,
    input_args      JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_data     JSONB DEFAULT '{}'::jsonb,
    is_error        BOOLEAN NOT NULL DEFAULT FALSE,
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_exec_tenant_time
    ON tool_executions(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_exec_chat_message
    ON tool_executions(chat_message_id);
