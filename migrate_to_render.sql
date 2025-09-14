-- 0) segurança: rodar em bloco, mas NÃO usar transação única se houver CREATE EXTENSION
-- 1) Ajustar owner de tipos / tabelas / functions / sequences para eleven_t7jn_user (idempotente)
DO $$
BEGIN
  -- Tipos (adapte o array abaixo se tiver mais)
  PERFORM 1 FROM pg_type WHERE typname = 'currencypair';
  IF FOUND THEN
    EXECUTE 'ALTER TYPE public.currencypair OWNER TO eleven_t7jn_user';
  END IF;
  -- repetir para outros tipos:
END $$;

-- 2) Ajustar owner de funções (se existirem)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'generate_pedido_numero') THEN
    EXECUTE 'ALTER FUNCTION public.generate_pedido_numero() OWNER TO eleven_t7jn_user';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
    EXECUTE 'ALTER FUNCTION public.update_updated_at_column() OWNER TO eleven_t7jn_user';
  END IF;
  -- UUID functions são da extensão; geralmente não altere
END $$;

-- 3) Ajustar owner de sequences
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'seq_pedido_numero') THEN
    EXECUTE 'ALTER SEQUENCE public.seq_pedido_numero OWNER TO eleven_t7jn_user';
  END IF;
END $$;

-- 4) Garantir defaults em rastreamentos (evita alterar sem checar)
DO $$
BEGIN
  -- adiciona default no id
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN id SET DEFAULT public.uuid_generate_v4();

  -- status default
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN status SET DEFAULT 'PENDENTE'::public.rastreamento_status;

  -- historico_eventos default
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN historico_eventos SET DEFAULT '[]'::jsonb;

  -- data_criacao, ativo, created_at, updated_at defaults
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN data_criacao SET DEFAULT CURRENT_DATE;
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN ativo SET DEFAULT true;
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
  ALTER TABLE IF EXISTS public.rastreamentos
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
EXCEPTION WHEN others THEN
  RAISE NOTICE 'Erro ao ajustar defaults em rastreamentos: %', SQLERRM;
END $$;

-- 5) Criar índices novos (IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_rastreamentos_ativo ON public.rastreamentos USING btree (ativo);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_codigo ON public.rastreamentos USING btree (codigo_rastreio);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_created_at ON public.rastreamentos USING btree (created_at);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_status ON public.rastreamentos USING btree (status);

-- 6) Criar unique index para codigo_rastreio se não existir
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE c.relkind = 'i' AND c.relname = 'ix_rastreamentos_codigo_rastreio') THEN
    EXECUTE 'CREATE UNIQUE INDEX ix_rastreamentos_codigo_rastreio ON public.rastreamentos (codigo_rastreio)';
  END IF;
END$$;

-- 7) Adicionar constraint FK / PK se não existirem
DO $$
BEGIN
  -- PK rastreamentos
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid = 'public.rastreamentos'::regclass AND contype = 'p'
  ) THEN
    EXECUTE 'ALTER TABLE ONLY public.rastreamentos ADD CONSTRAINT rastreamentos_pkey PRIMARY KEY (id)';
  END IF;

  -- exemplo: fk pedido_id -> pedidos(id)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'rastreamentos' AND c.contype = 'f' AND c.conname = 'rastreamentos_pedido_id_fkey'
  ) THEN
    EXECUTE 'ALTER TABLE ONLY public.rastreamentos ADD CONSTRAINT rastreamentos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id)';
  END IF;

  -- Exemplo: fk folgas.vendedor_id -> vendedores(id)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'folgas' AND c.contype = 'f' AND c.conname = 'folgas_vendedor_id_fkey'
  ) THEN
    EXECUTE 'ALTER TABLE ONLY public.folgas ADD CONSTRAINT folgas_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id) ON DELETE CASCADE';
  END IF;
END $$;

-- 8) Garantir triggers de updated_at (verifica função antes)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
    RAISE NOTICE 'Função update_updated_at_column() não encontrada; crie-a antes de criar triggers.';
  ELSE
    -- create trigger folgas
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_folgas_updated_at') THEN
      EXECUTE 'CREATE TRIGGER update_folgas_updated_at BEFORE UPDATE ON public.folgas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column()';
    END IF;
  END IF;
END $$;

-- 9) Grants (pg_trgm / uuid) para eleven_t7jn_user - idempotente
DO $$
BEGIN
  -- exemplo grant para uuid_generate_v4
  EXECUTE 'GRANT ALL ON FUNCTION public.uuid_generate_v4() TO eleven_t7jn_user';
  -- e para algumas funções do pg_trgm (adapte se necessário)
  EXECUTE 'GRANT ALL ON FUNCTION public.show_trgm(text) TO eleven_t7jn_user';
  EXECUTE 'GRANT ALL ON TYPE public.gtrgm TO eleven_t7jn_user';
EXCEPTION WHEN others THEN
  RAISE NOTICE 'Algumas grants podem falhar (permissions): %', SQLERRM;
END $$;
