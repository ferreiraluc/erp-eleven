# Impressão da Eleven no Windows

## Estado da implementação

Primeira etapa: agente Windows e API privada de fila implementados. API publicada
em 22/09/2026 (commit 96b0f4b, deploy dep-dap7f33rjlhs73fc004g). Dispositivo
c427707d-c8c0-416f-92a1-14f21ea3522e cadastrado; aguardando instalação da
credencial no Windows e confirmação de conexão. Não há ferramenta de impressão no Telegram nesta etapa.
A geração dos documentos a partir dos modelos do usuário é a próxima integração.
Não comunicar que o bot já imprime antes de concluir essa integração e um teste
real no Windows da loja.

O laptop de desenvolvimento não é o computador de impressão. O pacote em
`tools/eleven-print-agent` deve ser instalado exclusivamente no Windows da loja,
com SumatraPDF e o driver da **HP Laserjet M14-M17**. O usuário já imprimiu um PDF
com sucesso pelo Sumatra nesse computador.

## Regras confirmadas dos documentos

- Papel A4 comum, frente única.
- Paraguai: imprimir somente destinatário; não incluir remetente.
- Brasil: destinatário e um remetente escolhido entre os cadastrados.
- Cada trabalho deve ser um novo documento apenas com a seleção solicitada.
- O Word original contém destinatários históricos para copiar e colar, nunca
  deve ser impresso inteiro automaticamente.
- Modelos fornecidos: DESTINATARIOo.docx e declaração de conteúdo com remetente,
  destinatário, identificação dos bens, quantidades, valores, peso e assinatura.
- Dados de remetentes, CPFs e destinatários não devem ser inseridos no código,
  nos testes públicos ou no pacote de instalação.

## API e ativação

Migração `p6q7r8s9t0u1` cria `print_devices` e `print_jobs`.
Rotas sob `/api/printing`. Apenas ADMIN pode cadastrar/revogar dispositivos,
listar a fila e enviar PDFs. A credencial de dispositivo não autoriza nenhuma
consulta ao ERP além dos trabalhos da própria impressora.

1. Publicar e aplicar a migração.
2. ADMIN: POST `/devices` com `{ "name": "HP Laserjet M14-M17" }`.
3. Entregar o token retornado diretamente ao responsável pela instalação.
   A API guarda apenas seu SHA-256; o token não deve constar em logs ou URLs.
4. Executar Instalar.cmd no Windows e informar o token; DPAPI protege a cópia
   local. Nenhuma porta de entrada é aberta no computador.
5. Abrir o atalho Eleven Impressao e conferir `last_seen_at` em GET `/devices`.
6. Enviar PDF de teste A4 por POST `/jobs` multipart com `device_id`,
   `request_key` UUID novo e `file`. Repetições da mesma solicitação devem usar
   o mesmo request_key para não gerar uma segunda impressão.
7. Confirmar fisicamente o resultado com o usuário antes de integrar o bot.

## Entrega e recuperação

`pending` → `claimed` → `submitted` ou `uncertain`/`failed`.
`submitted` significa aceitação pelo renderizador/fila do Windows, não prova
que saiu papel. Trabalhos não coletados expiram em 24h. PDFs finalizados e
expirados são apagados; PDFs coletados sem retorno ficam disponíveis para
diagnóstico restrito a ADMIN/dispositivo até tratamento manual.

Claim usa bloqueio de linha e SKIP LOCKED no PostgreSQL. Não há reatribuição
automática de um claim, mesmo se a conexão cair antes de o agente receber a
resposta. Isso prefere um trabalho perdido/pendente de análise a cópias extras.
O agente mantém um diário em disco antes de chamar Sumatra. Na recuperação,
`started` vira `uncertain`; reenvia somente o resultado, nunca o PDF à HP.
Reimpressão exige conferir a fila local e criar um novo trabalho explicitamente.

O agente desta etapa precisa da sessão Windows e da janela abertas; não é um
serviço nem instala inicialização automática. O instalador é um script legível,
sem download ou execução automática de programas de terceiros. Usa PowerShell
somente no processo de instalação/execução, sem mudar a política permanente.

## Validação

Testes isolados cobrem autenticação, isolamento por dispositivo, revogação,
idempotência, expiração e confirmação de resultado. Teste físico e execução do
PowerShell dependem do Windows da loja; não foram executados no laptop macOS.

## Endereços pelo assistente

O assistente possui `preparar_impressao`, para endereço em texto, um destinatário por folha A4.
ADMIN/GERENTE com `can_register` recebe prévia e confirma na mesma conversa. A confirmação
cria o trabalho na mesma transação da ação; a chave é o UUID da ação, impedindo reenvio em retries.
PY nunca inclui remetente. BR exige UF, CEP e escolha de `debora` ou `mona`, cujos perfis
ficam em `print_senders` no banco (dados pessoais não pertencem ao código/instalador).
A prévia congela o perfil do remetente. PDF novo não inclui destinatários antigos do Word.
Esta etapa usa layout simples A4 e não emite declaração de conteúdo, SuperFrete nem lê fotos.
O bot informa envio à fila, sem afirmar impressão física. Agente Windows existente é compatível.

Teste físico inicial confirmado pelo responsável em 22/09/2026: papel A4 saiu na HP da loja.
