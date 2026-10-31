# Eleven WhatsApp — agente de conexão

Conecta um número pelo WhatsApp Web ao mesmo assistente do ERP, sem API Meta/Twilio e sem abrir porta de entrada. O backend continua validando usuários, permissões e confirmações. O número só responde a funcionários vinculados e a grupos explicitamente permitidos.

Esta conexão usa a biblioteca não oficial Baileys. Pode exigir novo pareamento, parar após mudanças do WhatsApp ou sofrer restrições da conta. Não há garantia de disponibilidade equivalente à API oficial. O agente não é destinado a disparos em massa nem ao atendimento de clientes externos com acesso às ferramentas internas.

## Ambiente

- Node.js 24 LTS ou posterior.
- Uma única instância do agente por número e diretório de estado.
- Diretório persistente privado. Não use o filesystem efêmero de um serviço para guardar a sessão.
- Somente saída HTTPS para o ERP e conexões de saída do WhatsApp. Nenhuma porta pública, túnel ou webhook direto para o agente.

```text
ELEVEN_ERP_URL=https://erp-eleven-backend.onrender.com
ELEVEN_WHATSAPP_TOKEN=<credencial criada no painel do ERP>
ELEVEN_WHATSAPP_STATE_DIR=/var/data/eleven-whatsapp
```

No Render, configure os dois primeiros valores como variáveis de ambiente do worker e monte um disco persistente em `/var/data`. O token não deve aparecer em comandos, repositório ou logs. O comando de instalação é `npm --prefix tools/eleven-whatsapp-agent ci --ignore-scripts --omit=dev`; o de execução é `npm --prefix tools/eleven-whatsapp-agent start`.

O pacote Baileys está fixado em `7.0.0-rc14`, versão publicada na tag `latest` pelo mantenedor na verificação inicial. Apesar dessa tag, o nome é uma release candidate. O lockfile fixa as dependências. Atualizações devem passar pelos testes do agente e pela auditoria; não instale diretamente a branch do GitHub.

## Ativação

1. Crie a credencial da ponte no painel de assistente do ERP e configure o worker.
2. Vincule os números dos funcionários aos seus usuários ERP. Use DDI; o identificador `@lid` do WhatsApp não é um telefone.
3. No painel administrativo, leia o QR com **Aparelhos conectados** no aplicativo do número escolhido. O QR aparece por tempo limitado apenas para administradores e não é escrito nos logs.
4. Habilite o canal e selecione os grupos desejados. O padrão exige menção ao bot, resposta a uma mensagem dele ou prefixo `/eleven`. A opção para todas as mensagens vale apenas para integrantes autorizados.
5. Valide primeiro uma consulta sem escrita. Cadastros, compras e impressões continuam exigindo a confirmação individual existente. Não use uma impressão ou compra fictícia para testar a conexão.

O status conectado não comprova que um ticket físico foi impresso ou que uma mensagem foi lida. O agente distingue mensagem aceita pelo envio de entrega física/leitura.

## Estado e recuperação

O SQLite local usa transações e gravação durável para credenciais, chaves Signal, mensagens recebidas e respostas. Diretório com permissão `0700`, banco com `0600` e trava de instância impedem processos concorrentes. Faça backup protegido do disco, pois a sessão permite atuar como o número conectado. Não compartilhe o banco ou o QR.

- Falhas de rede usam reconexão com intervalo crescente, limitado a aproximadamente um minuto, e variação para evitar reconexões simultâneas.
- Logout, sessão inválida ou conexão substituída interrompem reconexão automática. Confira **Aparelhos conectados** e use **Vincular novamente** no painel administrativo. Após confirmação, o agente encerra a conexão anterior, troca apenas as credenciais/chaves e apresenta outro QR; o histórico local de prevenção de duplicidades é preservado. Não apague o banco para resolver uma indisponibilidade temporária.
- Recebimentos são deduplicados. Histórico antigo, mensagens enviadas pelo próprio número, status, newsletters e contatos não autorizados são ignorados.
- Uma resposta interrompida durante o envio fica **incerta**. O agente não a envia de novo automaticamente. Quando o WhatsApp aceitou o envio e apenas a confirmação ao ERP falhou, repete somente a confirmação ao ERP.
- Imagens JPG/PNG e PDFs de até 5 MB são transferidos em memória e guardados no journal somente enquanto pendentes, por no máximo 24 horas. Os bytes são removidos após o ERP aceitar. O backend aplica sua própria validação e retenção.
- Falhas temporárias ao buscar uma mídia recebem até cinco tentativas, com intervalo crescente. Outras conversas continuam andando; a ordem da conversa afetada é preservada. Mídia indisponível ou inválida é descartada.
- Não há download de documentos de URLs arbitrárias enviadas pela IA. PDFs de saída vêm embutidos pelo backend autorizado.
- Logs contêm estados e códigos de erro, sem texto das conversas, telefones, tokens ou QR. A saída direta de `console` das dependências de protocolo é silenciada para impedir que avisos internos exponham chaves de sessão.

As opções dos botões do Telegram são apresentadas como instruções de texto no WhatsApp. Não há equivalência visual de teclados nativos entre os canais.

## Execução local opcional

Pode usar um JSON privado indicado por `ELEVEN_WHATSAPP_CONFIG`, com `erp_url`, `token` e `state_dir`. O arquivo deve ter permissão `0600`; as variáveis de ambiente prevalecem. O funcionamento em nuvem é o caminho preparado para operação contínua. Em um computador local ele precisa permanecer ligado e conectado; este pacote não instala serviços de sistema locais automaticamente.

## Verificação sem mensagens reais

```text
npm --prefix tools/eleven-whatsapp-agent test
npm --prefix tools/eleven-whatsapp-agent run check
npm --prefix tools/eleven-whatsapp-agent audit --omit=dev
```

Os testes usam transporte simulado, armazenamento isolado e não abrem uma sessão WhatsApp, não enviam mensagens a pessoas nem executam impressão/pagamento.

Referências primárias: [Baileys](https://github.com/WhiskeySockets/Baileys), [persistência da sessão](https://baileys.wiki/authentication/session-management), [identificadores e LIDs](https://baileys.wiki/concepts/jids), [grupos](https://baileys.wiki/features/groups) e [mídia](https://baileys.wiki/messaging/media-messages).
