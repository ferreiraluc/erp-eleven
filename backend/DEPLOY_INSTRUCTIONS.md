# Backend — implantação

O guia mantido está em [docs/OPERACAO.md](../docs/OPERACAO.md).

- API: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Configuração: `.env.example` e variáveis do serviço, sem segredos no repositório.
- Migrações: histórico em `alembic/versions`, preservado integralmente.
- Instalação local e limitação do banco vazio: [Desenvolvimento](../docs/DESENVOLVIMENTO.md).

Scripts SQL manuais anteriores ficam em `docs/archive/sql/` para consulta histórica;
não os executar como atualização do banco atual.
