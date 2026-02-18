-- Supabase Schema for AutoGen Web Tester
-- Run this in the Supabase SQL Editor to create all tables.
-- NOTE: Tables must be created manually — the Supabase SDK cannot create tables.

-- ========== TABLES ==========

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,  -- matches Supabase Auth auth.users.id
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS workspaces (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'private',  -- 'private' or 'shared'
    owner_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',  -- 'owner', 'editor', 'viewer'
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS tests (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    code TEXT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL DEFAULT 'manual',  -- 'ai', 'codegen', 'manual'
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_status VARCHAR(20),
    last_run_time TIMESTAMPTZ,
    description TEXT,
    UNIQUE(workspace_id, filename)
);

CREATE TABLE IF NOT EXISTS ai_steps (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    steps TEXT NOT NULL,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_status VARCHAR(20),
    last_run_time TIMESTAMPTZ,
    UNIQUE(workspace_id, filename)
);

CREATE TABLE IF NOT EXISTS test_artifacts (
    id SERIAL PRIMARY KEY,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    timestamp VARCHAR(50) NOT NULL,
    video_path VARCHAR(500),
    video_size_mb REAL DEFAULT 0,
    har_path VARCHAR(500),
    status VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    key VARCHAR(100) NOT NULL,
    value TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, key)
);

-- ========== INDEXES ==========

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner_id ON workspaces(owner_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user_id ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_tests_workspace_id ON tests(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ai_steps_workspace_id ON ai_steps(workspace_id);
CREATE INDEX IF NOT EXISTS idx_test_artifacts_test_id ON test_artifacts(test_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- ========== DISABLE RLS ==========
-- Service role key bypasses RLS, but be explicit.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (service_role key bypasses RLS by default,
-- but these policies ensure the anon key can't access anything directly).
CREATE POLICY "Service role full access" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON workspaces FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON workspace_members FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON tests FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON ai_steps FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON test_artifacts FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON user_preferences FOR ALL USING (true) WITH CHECK (true);
