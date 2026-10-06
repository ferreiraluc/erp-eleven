# Gestor de endereços e SuperFrete

Acesso: Dashboard → **Endereços e envios** (`/enderecos`), para ADMIN e GERENTE.

- **Endereços:** cadastros Brasil/Paraguai, com vínculo opcional a clientes de pedidos ou PDV, sem sobrescrever o cadastro original do cliente.
- **Impressões:** histórico do bot e do ERP, PDF, edição como nova cópia e cancelamento de trabalhos ainda não retirados pelo agente.
- **Remetentes:** endereço compartilhado entre impressão e frete. Blocos antigos são lidos automaticamente quando os campos são reconhecíveis. Confira os campos recuperados e complete apenas os ausentes; o bot também aceita complementos na conversa.
- **Padrões:** fonte, margens, título, campos e ordem dos modelos A4. Alterações afetam apenas novas solicitações; o histórico preserva os dados originais.
- **SuperFrete:** cotação, confirmação do pagamento, PDF recuperado automaticamente e impressão automática opcional no frontend (ativada no bot). Rastreios recebidos são registrados no ERP durante a consulta da etiqueta.

A edição é de dados e padrões dos PDFs gerados pelo ERP, não de Word ou PDFs externos. Arquivos avulsos antigos podem deixar de estar disponíveis após a limpeza da fila. PDFs SuperFrete são validados e guardados no banco assim que o provedor os disponibiliza.

## Frontend

1. Cadastre endereço brasileiro completo e remetente com dados estruturados.
2. No endereço, clique em **Frete**. Informe peso em kg, medidas em cm e conteúdo real. Informe a chave da nota fiscal ou selecione declaração de conteúdo quando o envio for não comercial.
3. Faça a cotação e selecione um dos serviços disponíveis: PAC, SEDEX ou Mini Envios.
4. Confira o preço final e clique em **Confirmar pagamento e emitir**. Essa etapa consome saldo SuperFrete.
5. A opção **Imprimir automaticamente quando o PDF estiver pronto** vem marcada. Desmarque antes do pagamento se quiser imprimir manualmente. O PDF aparece na tela automaticamente e pode ser baixado.

A impressão simples continua aceitando CPF ausente e dados parciais do Paraguai. A emissão de frete tem validações próprias da transportadora, incluindo CPF/CNPJ do destinatário.

## Bot

Exemplo: “Quero cotar uma etiqueta para este endereço: [dados]. Remetente [nome], pacote [peso e medidas], conteúdo [descrição, quantidade e valor], [nota fiscal ou envio não comercial].”

O bot aceita destinatário e remetente informados na conversa, sem exigir cadastro prévio do remetente. Pode também extrair os dados do bloco de impressão dos remetentes existentes; pede somente campos faltantes. Os dados ficam preservados na cotação sem sobrescrever o cadastro-base. Descrição, quantidade e valor unitário dos itens são usados na declaração informada pelo usuário. O bot apresenta serviços/valores. Após a escolha do serviço, pede confirmação do pagamento. Depois da confirmação do pagamento, busca o PDF, envia ao Telegram e coloca uma única cópia A4 na fila automaticamente. Não exige comandos com barra.

Confirmações pertencem ao usuário autorizado e à conversa de origem. Cotar não paga. Cancelar a impressão de uma etiqueta paga não cancela nem reembolsa a compra.

## Configuração

```dotenv
SUPERFRETE_TOKEN=seu_token
SUPERFRETE_CONTACT_EMAIL=contato_tecnico
SUPERFRETE_SANDBOX=false
```

Tokens de produção e Sandbox são diferentes. O padrão é Sandbox. No Render, o backend também carrega `/etc/secrets/superfrete.env`, preservando variáveis já definidas no ambiente. Nunca versionar tokens.

Migrações: `r8s9t0u1v2w3` e `s9t0u1v2w3x4`. Cria cadastros, padrões e fretes; adiciona anexos à entrega do bot e recupera conteúdo de impressões antigas vinculadas a ações do assistente.

## Operação

O agente Windows existente e o Sumatra continuam sendo usados. A máquina da loja precisa estar ligada com o agente aberto. “Enviado à impressora” indica aceitação pelo agente/Sumatra, não confirmação física do papel.

Impressões usam chaves de idempotência. Pagamentos são marcados antes da chamada externa. Uma resposta incerta bloqueia novo pagamento automático e permite consultar o estado. Se não houver identificador de frete, confira o painel SuperFrete antes de criar nova emissão.

Documentação oficial: https://superfrete.readme.io/reference/primeiros-passos

O histórico consultável pelo bot inclui endereços impressos. Pedidos de frete consultam novamente os cadastros antes de responder; recusas antigas sobre remetentes não configurados não são reaproveitadas. Mensagens do usuário cujo processamento falhou permanecem disponíveis no contexto, para não perder complementos de endereço.

## Botões, nomes e memória

Prévias do Telegram têm botões de confirmação/cancelamento. Havendo várias, o bot mostra uma lista paginada pelo nome e dados da solicitação. `confirmar impressão "Juan"` executa apenas se houver uma prévia inequívoca desse autor nessa conversa; homônimos abrem opções. Botões antigos continuam sujeitos a validade de 24 horas, permissões e execução única.

`consultar_equipe` lê os vendedores ativos e resolve nomes sem diferenciar acentos. `Lembre que Juninho é o Junior` prepara um apelido; confirmar salva em `assistant_knowledge`. O catálogo de ferramentas também é persistido e sincronizado a cada versão. Saldos, rastreios e agenda são consultados de novo; a memória não congela fatos operacionais.

## Recuperação automática dos PDFs

O worker de etiquetas roda em uma thread separada, inclusive quando o assistente está pausado. Consulta a SuperFrete com intervalo progressivo até cinco minutos, persiste o PDF validado e usa uma chave única por frete para a impressão automática. Não repete pagamento. Depois de 400 tentativas sem conclusão, sinaliza falha; **Consultar** no gestor reinicia a recuperação. Problemas temporários da impressora não impedem salvar/enviar o PDF.

Para ativar notificações, execute **no servidor**, após o deploy:

```sh
python -m app.assistant_setup telegram-webhook --url https://SEU-BACKEND/api/assistant/webhooks/telegram
python -m app.superfrete_setup --url https://SEU-BACKEND/api/freight/webhooks/superfrete
```

Telegram precisa de `allowed_updates` com `message` e `callback_query`. A SuperFrete usa `order.generated`; o webhook valida HMAC-SHA256 sobre o corpo original, agenda uma consulta autenticada e nunca paga nem confia em URLs do evento. A assinatura fica cifrada em `freight_webhooks` com a chave do servidor; opcionalmente pode ser fornecida por `SUPERFRETE_WEBHOOK_SECRET`. A consulta periódica continua mesmo sem webhook.

Etiquetas antigas pagas são recuperadas sem imprimir de novo. Para as antigas cujo PDF faltava, o canal original recebe o documento ao ficar pronto. Mantenha o agente Windows da loja aberto; não é necessário reinstalá-lo.

Referências: [botões Telegram](https://core.telegram.org/bots/api#inlinekeyboardmarkup), [eventos e assinatura SuperFrete](https://superfrete.readme.io/reference/webhook).

## Endereço único e histórico de utilização

A agenda mantém um cadastro por destinatário e local de entrega. Acentos, maiúsculas, espaços, pontuação e a máscara do CEP são normalizados para reconhecer repetições. Apartamentos numerados também aceitam as formas “Apartamento”, “apto”, “apt” e “ap” como equivalentes. Nome, número, complemento, cidade ou outro local diferente continuam sendo cadastros distintos. Em endereços mínimos do Paraguai, o telefone ajuda na identificação. Blocos vazios ou somente com nome não são consolidados automaticamente.

O bot, o cadastro manual e as impressões usam a mesma rotina de reutilização. Solicitações concorrentes são serializadas e um índice único protege o cadastro. Diferenças de CPF/CNPJ ou vínculos com clientes distintos exigem conferência, para não misturar pessoas.

No cartão de cada endereço, **Histórico** mostra cotações, etiquetas e impressões, com data, responsável, estado, rastreio e dados do endereço usado na ocasião. Permite filtrar por tipo, paginar, abrir o frete e consultar o PDF da impressão. Uma cotação não comprova um pacote enviado. Repetir uma mesma requisição técnica não cria outra utilização; solicitar outro pacote cria outro frete, reutilizando o endereço.

As migrações `t0u1v2w3x4y5` e `u1v2w3x4y5z6` consolidam duplicatas já existentes, incluindo abreviações de apartamentos. Os IDs antigos ficam preservados como referências ao cadastro principal; fretes, impressões e snapshots não são excluídos nem reescritos. Históricos de cópias antigas aparecem no endereço consolidado. Referências antigas continuam resolvendo para o endereço principal; editores abertos antes da consolidação precisam atualizar a agenda.

### Variações de avenida e bairro

Em endereços BR, a agenda também reconhece `Av`, `Av.` e `Avenida` no início da rua. Bairros como `Jardim Exemplo`, `Jd. Exemplo` e `Exemplo` podem representar o mesmo cadastro somente quando destinatário, CEP de oito dígitos, cidade, UF, rua, número e complemento coincidem. É necessário um número estruturado em pelo menos um dos cadastros; o outro pode conter esse mesmo número no bloco de impressão. Um número no nome da rua não é tratado como número da casa.

Essa comparação local não consulta nem presume uma confirmação dos Correios/ViaCEP. Ela exige um único candidato; diferenças reais de bairro, número, complemento, documento ou cliente não são descartadas. Dois candidatos compatíveis exigem revisão na agenda. As chaves de identidade antigas continuam válidas, e atualizar o sistema não consolida automaticamente cadastros já existentes.

### Manutenção de um par revisado

A ferramenta abaixo simula a união de dois IDs explicitamente escolhidos. Use o cadastro que deve continuar visível como `--target`; o cadastro duplicado torna-se uma referência histórica para ele. Não há varredura nem consolidação geral.

```sh
PYTHONPATH=backend backend/venv/bin/python -m app.address_maintenance merge \
  --target ID_PRINCIPAL --source ID_DUPLICADO
```

A simulação retorna versões, campos que serão completados, contagens do histórico e `plan_token`, sem exibir CPF ou endereço em claro. Revise o resultado antes de aplicar o mesmo par:

```sh
PYTHONPATH=backend backend/venv/bin/python -m app.address_maintenance merge \
  --target ID_PRINCIPAL --source ID_DUPLICADO \
  --apply --expected-plan TOKEN_DA_SIMULACAO
```

Alterações entre a simulação e a aplicação invalidam o plano. Documentos/clientes conflitantes, locais diferentes ou outro candidato compatível fora do par bloqueiam a operação. O cadastro principal conserva seus campos preenchidos e recebe somente os ausentes, incluindo documento e vínculo com cliente quando compatíveis. O estado ativo é preservado se qualquer um dos dois estiver ativo. IDs antigos, aliases, fretes, impressões, PDFs e snapshots permanecem intactos; o histórico do principal passa a reunir suas utilizações. A ferramenta não imprime nem emite etiquetas.

### Impressões de endereços A4 no histórico

Os modelos simples enviados pelo bot ou pelo ERP aparecem no mesmo **Histórico** das etiquetas. O resumo mostra endereços A4 impressos, etiquetas emitidas e total enviado à impressora. A contagem de impressão usa somente trabalhos `submitted`; fila, cancelamento, expiração, falha ou resultado incerto permanecem na lista, mas não aumentam o total. A data de conclusão do agente aparece em destaque, com a data da solicitação abaixo. Isso registra o envio à impressora, não um sensor de saída do papel.

A migração `w3x4y5z6a7b8` recupera impressões antigas com endereço no snapshot que estavam sem vínculo com a agenda. Reutiliza o endereço existente ou cria um único cadastro a partir dos dados originais, preservando datas, responsável, resultado e documento histórico. Não cria trabalhos nem reimprime. Blocos brasileiros sem bairro podem usar um cadastro mais completo quando nome, cidade, UF, CEP e rua/número/complemento identificam um único endereço. Conflitos de documento ou candidatos ambíguos não são associados automaticamente. PDFs avulsos da ponte temporária continuam fora da agenda.

### Consulta de CEP

O bot (`consultar_cep` e prévias de impressão), o cadastro e a cotação usam o ViaCEP por CEP brasileiro. O formulário consulta ao sair do campo CEP ou pelo botão de conferência. Somente o CEP é enviado ao provedor; não é necessário token adicional.

A consulta preenche rua, bairro, cidade e UF vazios quando os campos informados concordam. Divergências preservam o endereço informado e aparecem na prévia e na cotação. Número, complemento, telefone e CPF nunca são inferidos. CEP geral pode não informar rua/bairro; indisponibilidade não apaga dados nem bloqueia um endereço completo. PY permanece livre de exigências de CEP.

O cache em memória dura 24h para resultados encontrados, 1h para inexistentes e 30s para falhas (limite 512 CEPs). Não há varredura automática da agenda. Cadastros BR com mesmo destinatário/localização/CEP e bairro ausente reutilizam o endereço único compatível; conflitos de CPF, cliente ou múltiplos bairros continuam exigindo conferência. A migração `y5z6a7b8c9d0` consolida pares existentes com bairro ausente, mantendo IDs antigos como redirecionamentos e os históricos intactos.

### Geração revisada de remetentes

Para Lucas (`lucas@eleven.com`, ADMIN), a aba **Remetentes** inclui **Gerar pessoa · 4Devs**. Geração, importação e aprovação são exclusivas do proprietário no backend; o cadastro normal de remetentes continua disponível à equipe autorizada. O formulário permite gerar uma pessoa completa, revisar/editar a prévia e aprovar manualmente a gravação dos campos úteis de remetente. A origem sintética fica identificada e permanece após edições. Gerar/importar não salva, imprime ou emite frete. Há alternativa de importar o JSON do site quando o formulário externo estiver indisponível; a API oficial 4Devs ainda não está disponível. Veja o contrato, os limites e os dados persistidos em [Geração e revisão de remetentes](REMETENTES_GERADOS.md).

### Idiomas do gestor

O gestor, os formulários de endereço, o histórico de utilizações, o gerador e o card do dashboard acompanham a preferência PT/ES/EN. Datas são exibidas no fuso de Brasília, com formatação do idioma; valores de frete continuam em BRL, sem conversão monetária. Nomes, ruas, conteúdo, modelos salvos e demais dados inseridos pelo usuário não são traduzidos nem regravados por mudar o idioma.

Erros conhecidos de validação, CEP, pagamento e recuperação de PDF apresentam orientações traduzidas. Divergências de CEP mantêm os valores originais e os retornados pelo ViaCEP. Respostas desconhecidas/indisponíveis da API recebem uma mensagem segura no idioma escolhido, sem exibir detalhes internos. O gestor não contém exportação CSV; os PDFs mantêm o conteúdo operacional escolhido pelo usuário.

## Recuperação de solicitações e diagnóstico

A revisão de outubro/2026 diferencia dados recusados, acesso à conta recusado,
indisponibilidade temporária e resultado externo incerto. O CPF/CNPJ brasileiro é
conferido antes de cotar: dígitos inválidos pedem correção, sem inventar documento e
sem apresentar isso como indisponibilidade. Essa validação não torna CPF obrigatório
na impressão A4 nem altera documentos do Paraguai.

Cotações interrompidas por indisponibilidade ficam salvas e são consultadas novamente.
A criação só é repetida quando a falha comprova que a operação não foi aceita
(limite de requisições ou timeout antes de estabelecer conexão). Respostas incertas
na criação são conciliadas por uma identificação única enviada em `options.tags`,
consultando a listagem e os detalhes oficiais. Mesmo nome/endereço não basta para
associar um frete, e ausência na listagem não autoriza criar outro. A consulta é
limitada aos 100 pedidos mais recentes; solicitações antigas sem identificação
precisam de conferência no painel SuperFrete.

O worker existente de etiquetas executa essa recuperação, com intervalo progressivo
até cinco minutos e limite de 144 tentativas. O gestor mostra a próxima consulta.
Quando a cotação ou a preparação é recuperada, o Telegram recebe um aviso na conversa
vinculada, com opções para continuar. O preço ainda exige confirmação humana;
a recuperação não executa checkout. O fluxo de PDF/impressão após um pagamento
confirmado continua funcionando como antes. Usuário/identidade sem permissão
interrompe a recuperação; origem e permissão também são conferidas antes de entregar
as notificações.

A aba consulta a disponibilidade da API, com cache de um minuto, e distingue falha
na conta, indisponibilidade e impossibilidade de verificar. O retorno da conexão é
sinalizado na tela. Não há garantia de disponibilidade da compra apenas porque o
endpoint de consulta respondeu. Erros de dados exibem orientação específica. A
migração aditiva `c9d0e1f2a3b4` preserva pedidos existentes sem agendar emissões antigas.

Referências oficiais: [criar frete](https://superfrete.readme.io/reference/adicionar-frete-carrinho),
[listar etiquetas](https://superfrete.readme.io/reference/listar-etiquetas-na-superfrete)
e [consultar pedido](https://superfrete.readme.io/reference/tag-informa%C3%A7%C3%B5es-do-pedido).

### Documento do Paraguai

Formulário, padrões, prévia e PDF usam **RUC/C.I** para PY. É opcional, aceita até
20 caracteres e preserva letras, pontos e hífen. A chave interna `cpf` permanece
para compatibilidade com modelos e históricos, sem validação de CPF brasileiro.
Ausência ou pedido explícito sem documento omite a linha. A impressão PY continua
sem remetente e sem exigir rua. Documentos diferentes impedem a fusão dos cadastros,
inclusive quando têm os mesmos números e letras distintas.

### Cliente associado ao endereço

Salvar/cotar um endereço ou confirmar sua impressão também associa um cliente existente
ou cria o cadastro em Clientes. Endereços ambíguos mostram um aviso para conferir o
vínculo; selecionar o cliente no editor confirma a revisão. A impressão mantém as
mesmas confirmações e não ganha exigências de rua/CPF para PY. O histórico de Clientes
reúne A4 e etiquetas de todos os seus endereços, preservando os registros originais.
Regras e conciliação: [Clientes, pedidos e pacotes](CLIENTES_PEDIDOS_RASTREIOS.md).
