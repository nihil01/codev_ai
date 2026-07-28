CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE company_knowledge_base_entries ADD COLUMN embedding vector(1536);