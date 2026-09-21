# ERP Eleven - Sistema de Gestão Empresarial

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen.svg)

## Sumário

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Configuração e Instalação](#-configuração-e-instalação)
- [API Endpoints](#-api-endpoints)
- [Banco de Dados](#-banco-de-dados)
- [Regras de Negócio](#-regras-de-negócio)
- [Deploy](#-deploy)
- [Desenvolvimento](#-desenvolvimento)

## Visão Geral

### Assistente Eleven — WhatsApp e Telegram

O projeto inclui uma primeira versão do assistente DeepSeek para WhatsApp individual (Twilio) e grupo Telegram: consultas de rastreio, avisos automáticos no Telegram, registros operacionais confirmados e memória compartilhada entre os canais. O painel fica em **Dashboard → Assistente IA**, restrito a administradores.

A integração vem desabilitada e exige credenciais, migração e worker separado. Consulte [o guia de ativação](docs/ASSISTENTE_ATIVACAO.md) e [o estudo técnico](docs/ASSISTENTE_DEEPSEEK_WHATSAPP.md). Registros desta versão não movimentam vendas, estoque ou pagamentos; impressão e leitura de mídia ainda não estão integradas ao bot.

O **ERP Eleven** é um sistema completo de gestão empresarial desenvolvido para lojas de roupas, com foco em:

- **Gestão de Vendas**: Controle completo de vendas com suporte a múltiplas moedas
- **Rastreamento de Entregas**: Sistema manual de gestão de envios com integração aos Correios
- **Gestão de Usuários**: Sistema de autenticação com diferentes níveis de acesso
- **Dashboard Analítico**: Painéis com métricas e indicadores de performance
- **Câmbio e Transferências**: Gestão de taxas de câmbio e transferências de dinheiro

### Tecnologias

#### Backend
- **FastAPI** - Framework web moderno e rápido
- **PostgreSQL** - Banco de dados relacional
- **SQLAlchemy** - ORM para Python
- **Pydantic** - Validação de dados
- **JWT** - Autenticação segura

#### Frontend
- **Vue.js 3** - Framework JavaScript reativo
- **TypeScript** - Tipagem estática
- **Pinia** - Gerenciamento de estado
- **Tailwind CSS** - Framework de estilização
- **Vite** - Build tool moderno

## Arquitetura

### Estrutura do Projeto

```
ERP-Eleven/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── api/            # Endpoints da API
│   │   ├── models/         # Modelos SQLAlchemy
│   │   ├── schemas/        # Schemas Pydantic
│   │   ├── services/       # Lógica de negócio
│   │   └── main.py         # Aplicação principal
│   ├── migrations/         # Scripts de migração
│   └── requirements.txt    # Dependências Python
├── frontend/               # Aplicação Vue.js
│   ├── src/
│   │   ├── components/     # Componentes reutilizáveis
│   │   ├── views/          # Páginas da aplicação
│   │   ├── stores/         # Gerenciamento de estado
│   │   └── services/       # Serviços HTTP
│   └── package.json        # Dependências Node.js
└── README.md              # Esta documentação
```

### Padrões Arquiteturais

- **Clean Architecture**: Separação clara entre camadas
- **Repository Pattern**: Abstração de acesso a dados
- **Dependency Injection**: Injeção de dependências no FastAPI
- **JWT Authentication**: Autenticação stateless
- **RESTful API**: Endpoints seguindo padrões REST

## Configuração e Instalação

### Pré-requisitos

- **Python 3.8+**
- **Node.js 16+**
- **PostgreSQL 12+**
- **Git**

### 1. Clonagem do Repositório

```bash
git clone <repository-url>
cd ERP-Eleven
```

### 2. Configuração do Backend

```bash
# Navegar para o diretório backend
cd backend

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
```

#### Configuração do .env

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/eleven
SECRET_KEY=your-super-secret-key-here-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
TIMEZONE=America/Sao_Paulo
```

### 3. Configuração do Banco de Dados

```bash
# Criar banco de dados PostgreSQL
createdb eleven

# Executar migrações
psql -U postgres -d eleven -f migrations/001_init_database.sql
```

### 4. Configuração do Frontend

```bash
# Navegar para o diretório frontend
cd frontend

# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.example .env
```

### 5. Execução do Sistema

#### Backend (Terminal 1)
```bash
cd backend
source venv/bin/activate  # ou venv\Scripts\activate no Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```

### 6. Acesso ao Sistema

- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **API Redoc**: http://localhost:8000/redoc

## 🔗 API Endpoints

### Autenticação
```http
POST   /api/auth/login           # Login do usuário
POST   /api/auth/logout          # Logout do usuário
GET    /api/auth/me              # Dados do usuário logado
```

### Usuários
```http
GET    /api/users/               # Listar usuários
POST   /api/users/               # Criar usuário
GET    /api/users/{id}           # Obter usuário
PUT    /api/users/{id}           # Atualizar usuário
DELETE /api/users/{id}           # Remover usuário
```

### Vendas
```http
GET    /api/vendas/              # Listar vendas
POST   /api/vendas/              # Criar venda
GET    /api/vendas/{id}          # Obter venda
PUT    /api/vendas/{id}          # Atualizar venda
DELETE /api/vendas/{id}          # Remover venda
GET    /api/vendas/relatorio     # Relatório de vendas
```

### Vendedores
```http
GET    /api/vendedores/          # Listar vendedores
POST   /api/vendedores/          # Criar vendedor
GET    /api/vendedores/{id}      # Obter vendedor
PUT    /api/vendedores/{id}      # Atualizar vendedor
DELETE /api/vendedores/{id}      # Remover vendedor
GET    /api/vendedores/{id}/comissoes  # Comissões do vendedor
```

### Rastreamento
```http
GET    /api/rastreamento/        # Listar rastreamentos
POST   /api/rastreamento/        # Criar rastreamento
GET    /api/rastreamento/{id}    # Obter rastreamento
PUT    /api/rastreamento/{id}    # Atualizar rastreamento
DELETE /api/rastreamento/{id}    # Remover rastreamento
GET    /api/rastreamento/resumo/dashboard  # Resumo para dashboard
```

### Câmbio
```http
GET    /api/exchange-rates/      # Listar taxas de câmbio
POST   /api/exchange-rates/      # Criar taxa de câmbio
PUT    /api/exchange-rates/{id}  # Atualizar taxa
DELETE /api/exchange-rates/{id}  # Remover taxa
```

### Transferências
```http
GET    /api/money-transfers/     # Listar transferências
POST   /api/money-transfers/     # Criar transferência
GET    /api/money-transfers/{id} # Obter transferência
PUT    /api/money-transfers/{id} # Atualizar transferência
```

### Dashboard
```http
GET    /api/dashboard/resumo     # Resumo geral do dashboard
GET    /api/dashboard/vendas     # Métricas de vendas
GET    /api/dashboard/vendedores # Performance dos vendedores
```

### Sistema
```http
GET    /                        # Informações da API
GET    /health                  # Health check
```

## Banco de Dados

### Principais Tabelas

#### usuarios
```sql
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'USER',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### rastreamentos
```sql
CREATE TABLE rastreamentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_rastreio VARCHAR(100) NOT NULL UNIQUE,
    status rastreamento_status DEFAULT 'PENDENTE',
    servico_provedor VARCHAR(100),
    ultima_atualizacao TIMESTAMP,
    descricao TEXT,
    destinatario VARCHAR(200),
    origem VARCHAR(200),
    destino VARCHAR(200),
    historico_eventos JSONB DEFAULT '[]'::jsonb,
    pedido_id UUID,
    data_criacao DATE DEFAULT CURRENT_DATE,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID
);
```

### Scripts SQL Úteis

#### Criar Usuário Administrador
```sql
INSERT INTO usuarios (email, hashed_password, full_name, role, is_active)
VALUES (
    'admin@eleven.com',
    '$2b$12$ejemplo_hash_aqui',  -- Use a API para gerar o hash
    'Administrador',
    'ADMIN',
    true
);
```

#### Verificar Status dos Rastreamentos
```sql
SELECT 
    status,
    COUNT(*) as total,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER()), 2) as percentual
FROM rastreamentos 
WHERE ativo = true 
GROUP BY status;
```

#### Relatório de Rastreamentos por Período
```sql
SELECT 
    DATE(created_at) as data,
    status,
    COUNT(*) as quantidade
FROM rastreamentos 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    AND ativo = true
GROUP BY DATE(created_at), status
ORDER BY data DESC, status;
```

#### Limpar Rastreamentos Antigos (mais de 6 meses)
```sql
UPDATE rastreamentos 
SET ativo = false 
WHERE created_at < CURRENT_DATE - INTERVAL '6 months'
    AND status IN ('ENTREGUE', 'ERRO');
```

### Backup e Restore

#### Backup
```bash
pg_dump -U postgres -h localhost eleven > backup_eleven_$(date +%Y%m%d).sql
```

#### Restore
```bash
psql -U postgres -h localhost -d eleven < backup_eleven_20240101.sql
```

## Regras de Negócio

### Sistema de Rastreamento

1. **Códigos Únicos**: Cada código de rastreio deve ser único no sistema
2. **Status Válidos**: PENDENTE, EM_TRANSITO, ENTREGUE, ERRO, NAO_ENCONTRADO
3. **Integração Correios**: Links diretos para rastreamento nos Correios
4. **Edição Manual**: Status pode ser alterado manualmente pelos usuários
5. **Histórico**: Manter histórico de eventos em formato JSON

### Sistema de Usuários

1. **Roles Disponíveis**: ADMIN, GERENTE, VENDEDOR, OPERACIONAL, USER
2. **Hierarquia**: ADMIN > GERENTE > OPERACIONAL > VENDEDOR > USER
3. **Autenticação**: JWT com expiração configurável
4. **Senhas**: Hash bcrypt com salt rounds mínimo de 12

### Sistema de Vendas

1. **Múltiplas Moedas**: Suporte a G$, R$, U$, EUR
3. **Auditoria**: Log completo de todas as operações

## Deploy

### Variáveis de Ambiente (Produção)

```env
DATABASE_URL=postgresql://user:password@host:5432/eleven
SECRET_KEY=super-secret-production-key-256-bits
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
TIMEZONE=America/Sao_Paulo
ENVIRONMENT=production
```

### Docker (Opcional)

```bash
# Build da aplicação
docker build -t erp-eleven-backend ./backend
docker build -t erp-eleven-frontend ./frontend

# Executar com docker-compose
docker-compose up -d
```

### Render.com Deploy

1. Conectar repositório ao Render
2. Configurar serviços:
   - **Database**: PostgreSQL
   - **Backend**: Web Service (FastAPI)
   - **Frontend**: Static Site (Vue.js)
3. Configurar variáveis de ambiente
4. Deploy automático via Git

##  Desenvolvimento

### Comandos Úteis

#### Backend
```bash
# Executar testes
pytest

# Lint do código
flake8 app/

# Formatação
black app/

# Verificar tipos
mypy app/
```

#### Frontend
```bash
# Executar em modo desenvolvimento
npm run dev

# Build para produção
npm run build

# Preview da build
npm run preview

# Lint do código
npm run lint

# Testes
npm run test
```


### Debug

#### Backend
```bash
# Executar com debug
uvicorn app.main:app --reload --log-level debug

# Logs detalhados
export LOG_LEVEL=DEBUG
```

#### Frontend
```bash
# Vue DevTools
npm install -g @vue/devtools

# Debug em produção
NODE_ENV=development npm run build
```


**ERP Eleven v1.0** - Sistema de Gestão Empresarial
*Documentação atualizada em: $(date +%Y-%m-%d)*
