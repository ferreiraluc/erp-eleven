# Histórico — não usar como configuração atual

Estes materiais explicam a evolução do ERP. Contêm planos que foram substituídos,
resultados de testes datados e estruturas de banco antigas. Não são instruções de
instalação, nem indicação do estado atual de contas externas.

- [Escopo inicial](ESCOPO_INICIAL.md): proposta anterior ao frontend Vue e aos fluxos atuais.
- [Estudo dos canais do assistente](ASSISTENTE_DEEPSEEK_WHATSAPP.md): alternativas avaliadas em setembro/2026.
- [Testes iniciais de integração](ASSISTENTE_TESTES_INTEGRACAO.md): verificações pontuais, não monitoramento contínuo.
- [Incidente Twilio 63058](TWILIO_SUPORTE_63058.md): contexto para suporte; identificadores operacionais foram retirados.
- `sql/`: esquemas/procedimentos manuais anteriores ao fluxo atual de migrações, incluindo `manual-migrations/`.

**Não executar esses SQLs automaticamente**, nem usar como substituto de
`backend/alembic/versions/`. Eles podem criar estruturas incompatíveis, dados de exemplo,
alterar permissões ou remover dados. Nenhum foi executado durante a limpeza.

O ponto de entrada atual é o [README principal](../../README.md), com
[desenvolvimento](../DESENVOLVIMENTO.md) e [operação](../OPERACAO.md).
