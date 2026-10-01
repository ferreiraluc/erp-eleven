# Documentação do ERP Eleven

O [README principal](../README.md) apresenta o sistema e os comandos essenciais.

| Documento | Quando consultar |
| --- | --- |
| [Escopo](ESCOPO.md) | Entender o que a loja usa e o que cada módulo faz |
| [Arquitetura](ARQUITETURA.md) | Localizar telas, APIs, tabelas, serviços e workers |
| [Desenvolvimento](DESENVOLVIMENTO.md) | Configurar um ambiente, validar mudanças e preparar migrações |
| [Operação](OPERACAO.md) | Publicar, configurar provedores e diagnosticar filas |
| [Ativação do assistente](ASSISTENTE_ATIVACAO.md) | Habilitar canais e vincular usuários |
| [Fluxos do assistente](ASSISTENTE_FLUXOS_OPERACIONAIS.md) | Rastreios, contexto, estoque e impressão de PDFs |
| [Endereços e SuperFrete](GESTOR_ENDERECOS_SUPERFRETE.md) | Cadastro único, impressão A4, CEP e emissão de etiquetas |
| [Impressão Windows](IMPRESSAO_WINDOWS.md) | Instalar e operar o agente na máquina da loja |
| [BI de vendas](sales-bi.md) | Interpretar totais, cobertura, correções e sincronização OneDrive |
| [Auditoria de manutenção](AUDITORIA_MANUTENCAO.md) | Evidências de limpeza e pendências técnicas |
| [Histórico](archive/README.md) | Entender decisões antigas; não é um manual de instalação |

Não duplicar listas detalhadas de endpoints em vários arquivos. O contrato
executável é o OpenAPI gerado por `backend/app/main.py` em `/docs` e `/openapi.json`.
As famílias de rotas e seus donos estão no mapa de arquitetura.
