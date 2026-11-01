# WhatsApp da equipe

O canal `whatsapp_web` usa uma sessão de aparelho conectado do WhatsApp por meio
do Baileys. Ele reutiliza o assistente, os usuários, as ferramentas, as prévias e
as confirmações do ERP. Telegram e WhatsApp/Twilio continuam independentes;
mensagens antigas de um canal não são reenviadas pelo outro.

Esta conexão não usa a API oficial da Meta nem Twilio. É uma integração não
oficial: mudanças do WhatsApp podem interrompê-la, exigir outro QR Code ou levar
à restrição do número. Não há garantia contra bloqueios. Recomenda-se um número
dedicado, mantido sob controle da empresa. A biblioteca é fixada em
`@whiskeysockets/baileys@7.0.0-rc14`; trata-se de uma versão candidata, não de uma
versão final. O lockfile, os testes e a auditoria de dependências são parte da
validação antes de atualizar essa versão.

## Funcionamento

- Conversas individuais e grupos explicitamente liberados pelo administrador.
- Cada autor deve estar vinculado ao usuário correto em **Assistente IA →
  Funcionários autorizados → WhatsApp da equipe**, com `whatsapp:+DDINUMERO`.
  Nome de perfil, apelido e números de identificadores `@lid` não autenticam ninguém.
- Nos grupos, o padrão é responder quando houver menção ao bot, resposta a ele ou
  prefixo `/eleven`. É possível optar por todas as mensagens dos funcionários
  autorizados. Adicionar o número a um grupo não libera automaticamente o ERP.
- As respostas de um grupo são visíveis aos membros daquele grupo. Libere apenas
  grupos internos cujos membros possam ver as informações da operação.
- Consultas, memória confirmada, folgas, cadastro/entrada de estoque, endereços,
  impressão e fretes usam as permissões e confirmações existentes. O bot não
  recebe permissão para lançar vendas, saídas ou reembolsos por esta integração.
- As escolhas do Telegram são apresentadas como opções em texto no WhatsApp.
  Os comandos dessas opções incluem `/eleven`, para funcionar também nos grupos
  que exigem menção. Para responder apenas “confirmo” nesses grupos, responda à
  mensagem da prévia ou use `/eleven confirmo`.
  “Confirmo” continua válido para uma única prévia do autor na mesma conversa;
  escolhas explícitas identificam a prévia correta quando há mais de uma.
- PDFs e fotos JPG/PNG de comprovantes, até 5 MB, mantêm validação e confirmação.
  Áudio, vídeo, leitura genérica de imagens e atendimento público a clientes não
  foram adicionados. O download de mídia só começa após verificar autor e conversa.
- Avisos de novos rastreios são opcionais e ficam desativados inicialmente.
  Quando habilitados, alcançam apenas os grupos autorizados. O código sai
  isoladamente, seguido dos detalhes.

## Instalação na nuvem

O arquivo [render.whatsapp.yaml](../render.whatsapp.yaml) cria **somente** um
Background Worker Node 24, de uma instância, com disco persistente de 1 GB.
Ele não redefine nem substitui os serviços existentes do ERP. É um serviço pago
adicional; o custo vigente de processamento e disco aparece no Render antes da
criação. O plano inicial é `0.5c-512mb` (512 MB de memória disponibilizada, não uma
medição do consumo real do agente).

1. Publique a revisão aprovada e espere o backend/frontend terminarem o deploy.
   A migração cria a configuração desabilitada e tabelas temporárias do canal.
2. Como administrador, abra **Assistente IA → WhatsApp da equipe**. Gere a
   credencial em **Configuração do agente na nuvem**. Ela aparece uma única vez.
3. Crie o worker a partir do Blueprint separado `render.whatsapp.yaml`, usando
   `main` com `autoDeployTrigger: checksPass`.
4. Preencha `ELEVEN_WHATSAPP_TOKEN` no ambiente secreto do worker com a credencial
   gerada. `ELEVEN_ERP_URL` aponta para a API HTTPS e
   `ELEVEN_WHATSAPP_STATE_DIR=/var/data/eleven-whatsapp` deve permanecer dentro do
   disco. Nunca use variável `VITE_*`, URL de consulta ou repositório para segredos.
5. Habilite o canal no ERP, clique **Mostrar QR Code** e use **WhatsApp →
   Aparelhos conectados → Conectar um aparelho** no telefone do número escolhido.
   O QR fica disponível somente ao administrador, expira e não aparece nos logs.
6. Cadastre os números da equipe, vinculando cada um ao respectivo usuário.
   Permissão de registro continua sendo uma concessão separada.
7. Adicione o número ao grupo desejado. O agente incorpora os eventos de entrada
   em grupos e o painel visível atualiza a lista a cada 10 segundos, preservando
   alterações ainda não salvas. Marque os grupos que poderão usar o assistente e
   salve a configuração. A descoberta não autoriza o grupo automaticamente.

Se o WhatsApp falhar ao consultar os grupos, o agente mantém os grupos conhecidos
e tenta novamente com intervalo limitado. Essa consulta não bloqueia a fila de
mensagens. Eventos de atualização da própria consulta não disparam consultas
completas em sequência. O painel informa quando a descoberta precisa tentar
novamente. A verificação completa periódica continua a cada cinco minutos.
Se um grupo adicionado antes de uma atualização ainda não aparecer, envie uma
nova mensagem nele. O agente consulta os metadados desse grupo, com limite de
duas consultas simultâneas e nova tentativa por grupo após 30 segundos. Essa
descoberta não executa a mensagem nem concede acesso aos dados do ERP.
Para testar em grupo, envie `/eleven ajuda` a partir de **outro número autorizado**;
mensagens do próprio número vinculado são ignoradas para evitar ciclos de respostas.

O agente só inicia conexões de saída HTTPS/WebSocket. Não precisa de porta
pública, túnel, navegador Chromium ou acesso direto ao banco do ERP. Seu token
não é uma credencial de usuário administrador e só acessa os endpoints da ponte.

## Persistência, falhas e privacidade

O banco do ERP conserva a fila e a procedência das ações. O agente conserva a
sessão criptográfica e seu diário em SQLite local, dentro do disco persistente.
Sem esse disco, um deploy perderia a sessão e exigiria novo vínculo. Não rode
duas instâncias com a mesma sessão nem clone esse disco para outro agente ativo.
Deploys desse worker podem interromper brevemente a conexão; isso não interrompe
a API, o Telegram, o PDV ou os agentes de impressão.

O encerramento diário das sessões do painel às 21h não encerra o bot: a ponte
usa uma credencial própria, independente do login do navegador. O painel distingue
início, reconexão, recuperação automática e situações que precisam de revisão.
Desconexões temporárias tentam reconectar preservando a sessão e a fila.

O código de desconexão `500` pode ser recuperável. O agente tenta reutilizar a
sessão até cinco vezes, com espera entre tentativas; atingir esse limite pausa
a recuperação e pede revisão, sem apagar a sessão nem solicitar automaticamente
outro QR Code. O contador só é reiniciado após cinco minutos conectado, evitando
um ciclo infinito de conexões que caem logo em seguida. Confira o serviço e a
persistência antes de decidir reiniciar o agente ou refazer o vínculo.

Outros encerramentos exigem ações diferentes:

- `401`: o WhatsApp encerrou o vínculo; use **Refazer vínculo do WhatsApp** para
  preparar outro QR Code.
- `440`: outra conexão substituiu a atual. Confira se há mais de um agente com
  a mesma sessão, mantenha apenas um ativo e preserve o vínculo antes de reiniciar.
- `403`: o WhatsApp recusou o acesso; confira a situação da conta no telefone.
- `411`: incompatibilidade de sessão; revise versão e configuração do agente.

Nesses casos, o agente pausa a reconexão automática. Os registros técnicos mostram
somente o código da desconexão, sem mensagens brutas do provedor, chaves ou dados
da sessão. Estados antigos sem código não comprovam que seja necessário refazer
o vínculo. Uma resposta real confirmada pela equipe valida a recuperação; o estado
**Conectado** sozinho não comprova entrega de uma mensagem.

Cada mensagem recebida é identificada pelo ID do WhatsApp **e pela conversa**.
Reentregas não repetem ações. Histórico sincronizado, mensagens enviadas pelo
próprio número, status e newsletters não entram como comandos novos. Identificadores
LID sem correspondência confiável com o telefone são ignorados.

A resposta só é enviada depois de retirada durável e nova verificação da
autorização. O agente registra o resultado antes de avisar o ERP. Se houver
queda entre envio e confirmação, o estado é **incerto**: não há repetição cega.
“Aceito pelo provedor” não confirma que a pessoa recebeu ou leu a mensagem.
Mensagens pausadas permanecem na fila; autor revogado, grupo removido e prévia
expirada impedem novas operações. Alterar a senha não substitui a revogação do
acesso do bot; suspenda sua identidade no painel quando necessário.

Se precisar refazer o vínculo, use **Refazer vínculo do WhatsApp** no painel.
Isso apaga somente a sessão do aparelho no agente e preserva filas e histórico.
Se o disco do agente for perdido, substitua a credencial no painel e configure-a
na nova instância: retiradas ainda não iniciadas voltam à fila; envios iniciados
ficam incertos para conferência, sem repetição automática.

Mídias recebidas são temporárias: até 24 horas, 25 MB por usuário e 100 MB no total
da ponte. Fotos são verificadas e normalizadas; PDFs passam pela validação já
usada na impressão. Nenhum arquivo vira cadastro, rastreio ou impressão só por
ser recebido. A confirmação e o hash do documento permanecem obrigatórios.
O conteúdo temporário não é mostrado na auditoria nem nos registros de falha.
A eliminação do banco operacional não apaga retroativamente backups externos.

## Validação antes do uso

Os testes automatizados usam banco isolado, transporte simulado e arquivos
fictícios. Cobrem remetentes/grupos negados, duplicidade, permissões revogadas,
confirmação por outro autor/conversa, mídia, expiração, recuperação de sessão e
envio incerto. Não enviam mensagens reais, não compram frete e não imprimem.

Após vincular o número, faça primeiro uma consulta sem efeitos, como “O que você
consegue fazer?”. Confira o mesmo resultado de rastreio no ERP e teste uma prévia
cancelada antes de autorizar uma operação real. A validação física do WhatsApp
depende do número vinculado e de um teste humano; compilação e simulações não
comprovam conexão com a conta.

Comandos do agente e detalhes locais estão em
[tools/eleven-whatsapp-agent/README.md](../tools/eleven-whatsapp-agent/README.md).

Fontes: [Baileys oficial](https://github.com/WhiskeySockets/Baileys),
[documentação Baileys](https://baileys.wiki/),
[processos em segundo plano no Render](https://render.com/docs/background-workers),
[discos persistentes](https://render.com/docs/disks) e
[Blueprints](https://render.com/docs/blueprint-spec).
