-- 035_chat_persistence.sql: Add page_context and thread_start to strategy_chat_messages
-- for persistent app-wide chat with thread boundaries.

BEGIN;

-- Store which page the user was on when sending a message
ALTER TABLE strategy_chat_messages
    ADD COLUMN IF NOT EXISTS page_context VARCHAR(50);

-- Thread boundary marker: when set, this message starts a new conversation
-- Old messages before this point are retained but not shown in the active thread
ALTER TABLE strategy_chat_messages
    ADD COLUMN IF NOT EXISTS thread_start BOOLEAN NOT NULL DEFAULT FALSE;

-- Index for efficient "get current thread" queries
CREATE INDEX IF NOT EXISTS idx_strategy_chat_thread_start
    ON strategy_chat_messages(document_id, thread_start, created_at DESC)
    WHERE thread_start = TRUE;

COMMIT;
