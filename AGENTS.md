# ERP Eleven — orientação de trabalho

- Comece por `README.md`, `docs/ARQUITETURA.md`, `docs/ESCOPO.md` e pelo guia do módulo afetado.
- Preserve o estilo Vue existente, a navegação por perfil e a validação efetiva no backend.
- Vendas de planilha (BI), vendas operacionais e PDV/fiado são fluxos distintos.
- O BI lê resultados corrigidos; sincronização diária às 18h Brasília ou botão manual. Não iniciar sync ao consultar dashboard.
- Código de rastreio individual sai isolado, seguido dos detalhes. PY não exige endereço completo/remetente; CPF ausente não vira zeros.
- Impressão/compra exigem as confirmações do produto, identidade e idempotência existentes. Não simular pagamento/print para validar UI.
- Não remover migrações aplicadas, snapshots, cadastros consolidados ou histórico operacional durante limpeza de código.
- `assistant_events` registra listeners por import; CLIs `assistant_setup` e `superfrete_setup` são entradas ativas, mesmo sem importadores.
- Credenciais ficam em `.env`/ambiente. Não imprimir seus valores, não commitá-los e não ler produção para testes de rotina.
- Testes Python: `PYTHONPATH=backend DATABASE_URL=sqlite:// backend/venv/bin/python -m pytest backend/tests -q`.
- Frontend: `npm --prefix frontend run type-check` e `npm --prefix frontend run build`; lint é leitura, lint:fix modifica.
- Para mudanças PostgreSQL, validar em base isolada; SQLite não comprova locks/migrações.
- SQLs e estudos em `docs/archive/` são históricos, não scripts de instalação.
- Não fazer upgrades amplos de dependências ou reformatação global incidentalmente.
- Atualize o guia correspondente quando mudar comportamento; registre limitações reais sem prometer suporte não implementado.
- `main` é protegida: publique por branch `codex/` e PR, com backend/frontend/print-agent/python-security aprovados. Não contorne a proteção nem faça deploy manual de revisão sem validação.
