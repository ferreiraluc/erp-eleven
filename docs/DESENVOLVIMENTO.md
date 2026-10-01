# Desenvolvimento e validação

## Ambiente

Use Python 3.11, Node 22 (`frontend/.nvmrc`) e PostgreSQL local ou de homologação.
O frontend usa Vue 3, TypeScript, Vite, Pinia, Axios e CSS por componente/Tailwind.
O backend usa FastAPI, SQLAlchemy 2, Alembic e Pydantic 2. As versões concretas ficam
em `requirements*.txt` e `frontend/package-lock.json`.

Não há instalação npm na raiz: todos os comandos Node pertencem a `frontend/`.
Use `npm ci --include=dev` para reproduzir o lockfile e incluir verificadores.

## Banco e primeira execução

**O histórico Alembic começa em um banco que já existia.** A primeira revisão altera
vendas/pedidos e remove tabelas do esquema anterior; `alembic upgrade head` isolado não
cria corretamente um banco vazio. Os SQLs antigos, agora em `docs/archive/sql/`, não são
um bootstrap atualizado. A API interrompe o startup se uma migração falhar;
não tenta continuar com um esquema parcialmente atualizado.

Para um ambiente completo de desenvolvimento, restaure em PostgreSQL local uma cópia
sanitizada e autorizada de uma base já migrada, incluindo `alembic_version`. Preserve a
origem e não restaure por cima de um banco usado pela loja. A criação de um bootstrap
vazio reproduzível está registrada na auditoria como pendência, sem alterar revisões
aplicadas em produção.

```sh
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# Edite DATABASE_URL para a base LOCAL e defina SECRET_KEY local.
alembic current
alembic heads
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

No PowerShell, ative com `venv\Scripts\Activate.ps1`. Gere um segredo local com
`python -c "import secrets; print(secrets.token_urlsafe(48))"` e salve-o no `.env`,
sem inserir o resultado na documentação ou no Git.

O primeiro administrador deve existir na cópia sanitizada. Novos usuários são criados
pela API autenticada de ADMIN; não há senha padrão de instalação nem cadastro público.
Assistente vem desabilitado, SuperFrete em Sandbox e provedores sem chaves no exemplo.

## Frontend

```sh
cd frontend
nvm use
npm ci --include=dev
cp .env.example .env.local
npm run dev
```

`VITE_API_BASE_URL=http://localhost:8000`; frontend em `http://localhost:3000`.
Em produção a variável aponta para a API pública e o router usa URLs com `/#/`.
Depois de mudar uma variável Vite, reinicie o servidor de desenvolvimento ou refaça o build.

Node 25 apresentou incompatibilidade com `vite-plugin-vue-devtools` no ambiente auditado.
Use Node 22; `--mode test` é útil apenas para uma prévia isolada sem esse plugin.
Não é necessário instalar outro framework de frontend.

## Verificações

Da raiz, em macOS/Linux:

```sh
PYTHONPATH=backend DATABASE_URL=sqlite:// backend/venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
npm --prefix frontend run lint
```

PowerShell, para os testes isolados:

```powershell
$env:PYTHONPATH = 'backend'
$env:DATABASE_URL = 'sqlite://'
backend\venv\Scripts\python -m pytest backend/tests -q
```

- O `DATABASE_URL=sqlite://` explícito é obrigatório nesse comando, pois o `.env` do desenvolvedor pode conter a conexão real.
- A suíte simula provedores e não requer chaves, Telegram, saldo SuperFrete ou impressão física.
- Tipagem e build são verificações distintas: Vite pode gerar um bundle mesmo com erros TypeScript.
- `lint` só verifica; `lint:fix` aplica correções. Há dívida antiga de `any` documentada; não desligue regras para fingir que foi resolvida.
- A CI executa Vitest, tipagem, build e testes do backend, incluindo migrações em PostgreSQL descartável. Não altera produção, compra etiquetas, imprime ou publica serviços.
- SQLite não valida extensões/enums, migrações ou concorrência PostgreSQL. Mudanças nessas áreas precisam de homologação PostgreSQL adicional.
- Alterações visuais devem ser conferidas em desktop/celular com dados de teste, incluindo estados vazio/erro/carregamento e permissões.

Os testes PostgreSQL usam `ACCESS_TEST_DATABASE_URL` adicional, apontando exclusivamente
para host local/serviço CI (`127.0.0.1`, `localhost` ou `postgres`). Criam um schema
temporário por teste e o removem ao terminar. Não passe a conexão real nessa variável.
Sem ela, esses testes ficam explicitamente ignorados; a suíte SQLite não os substitui.
Vitest usa jsdom e armazenamento de navegador isolado, sem chamar a API real.

## Migrações e mudanças

Preserve todos os arquivos em `backend/alembic/versions`. Crie nova revisão para
alterar esquema; verifique o diff gerado contra uma base de homologação, índices,
backfill e possibilidade de rollback. Algumas migrações de endereços importam rotinas
do aplicativo: não mova essas funções sem avaliar a execução do histórico.

Não executar SQLs arquivados, `stamp head`, `drop_all`, seeds de dados fictícios ou
comandos de limpeza no banco real como parte de uma revisão de código.

Antes de remover um arquivo, verifique importações diretas/dinâmicas, rotas, CLIs,
Docker/Render, testes, migrações e efeitos de registro. Um serviço pouco usado pode
continuar sendo contrato público. Não remover tabelas ou histórico ao remover UI morta.

Prefira alterações pequenas por domínio. Preserve valores corrigidos do BI, snapshots
históricos, chaves de idempotência e confirmações de pagamento/impressão. Atualize o
guia do módulo junto com a mudança. Evite reformatação global de arquivos grandes
quando ela dificulta identificar a alteração funcional.

## Docker opcional

`docker compose` mantém API, frontend e PostgreSQL locais; não é a topologia em produção.
A base precisa ser preparada conforme a seção anterior, inclusive antes de subir a API.
`VITE_API_BASE_URL` é argumento de build do frontend, não uma configuração dinâmica do servidor.
Os `.dockerignore` excluem `.env`, arquivos locais, dependências e artefatos.

```sh
docker compose up -d db
# Restaure a base sanitizada no banco local antes de iniciar a API.
docker compose up --build backend frontend
```

Não usar `docker compose down -v` sem avaliar o backup: isso elimina o volume local.
Os Dockerfiles/Compose não foram executados na auditoria macOS, que não tinha Docker instalado.
