-- init.sql (Corrigido)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS disciplinas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- REMOVIDO: A restrição 'UNIQUE' foi removida daqui
    nome VARCHAR(100) NOT NULL,
    vagas_totais INT NOT NULL,
    is_deleted BOOLEAN DEFAULT false,
    data_ultima_modificacao TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS matriculas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
    disciplina_id UUID REFERENCES disciplinas(id) ON DELETE CASCADE,
    nome_aluno VARCHAR(100) NOT NULL,
    timestamp_matricula TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    status VARCHAR(20) DEFAULT 'ACEITA',
    data_ultima_modificacao TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE TABLE IF NOT EXISTS deleted_disciplinas (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);
CREATE TABLE IF NOT EXISTS deleted_matriculas (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);