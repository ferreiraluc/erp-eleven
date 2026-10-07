# Impressão da Eleven no Windows

## Instalação e operação atuais

O bot Telegram, o gestor de endereços e as etiquetas compartilham o mesmo agente
Windows e a mesma fila. Em 07/10/2026 a loja informou a troca para **Samsung
SL-M2035W**, já imprimindo pelo Windows. O responsável confirmou a configuração do agente após a atualização.
O laptop de desenvolvimento é outra máquina; não instalar nele um segundo agente.

Pacote: `tools/eleven-print-agent/`, com `Instalar.cmd`, `Instalar.ps1`,
`Configuracao.ps1`, `Agente.ps1` e `LEIA-ME.txt`. Após a configuração da Samsung,
o painel de instalação/download foi retirado de Endereços a pedido do responsável.
O pacote continua no repositório e no endpoint administrativo autenticado
`/api/printing/agent-package`, que inclui somente esses cinco arquivos e nunca
credenciais ou configurações locais. O driver e o SumatraPDF devem estar instalados;
o instalador não baixa nem substitui drivers/programas de terceiros.

### Trocar a impressora no mesmo computador

1. Aguarde a impressão atual terminar e feche **Eleven Impressao**. O instalador
   recusa atualizar com o agente aberto, usando o mesmo lock local.
2. Extraia todos os arquivos do pacote atualizado em uma pasta, usando a mesma
   conta Windows que já executava o agente. Não apague `%LOCALAPPDATA%\ElevenPrint`.
3. Abra `Instalar.cmd` e selecione a fila da Samsung que já imprime no Windows.
   Uma única correspondência SL-M2035W é sugerida, mas ainda exige Enter; nomes de
   driver diferentes ou duas filas semelhantes exigem escolher o número da lista.
4. No campo da credencial, pressione **Enter para manter a existente**. O agente
   mantém o Sumatra e o diário local; cria backup da configuração protegida por DPAPI.
   Credencial de outro computador/usuário Windows não é reutilizada silenciosamente.
5. Abra **Eleven Impressao**. Ao conectar, `/api/printing/agent/connect` atualiza
   somente o nome do próprio dispositivo autenticado, conservando ID, credencial,
   fila, prévias e histórico. ERP e consultas/prévias novas do bot usam esse cadastro.
6. Confira o nome no gestor e peça uma impressão quando desejar validar o papel.
   A instalação não imprime; abrir o agente retoma trabalhos pendentes já autorizados.
   Trabalhos já enviados ou incertos não são reimpressos automaticamente.

O nome mostrado no ERP é o nome real da fila do Windows; pode ser diferente do nome
comercial do modelo. A4, uma cópia, preto e branco e frente única continuam iguais.
Referência do fabricante: [Samsung SL-M2035W](https://www.samsung.com/sec/support/model/SL-M2035W/).
Se a impressora já imprime pelo Windows, não é necessário reinstalar seu driver.

### Primeira instalação

1. Instale o driver e o SumatraPDF no Windows; teste um PDF diretamente pelo Sumatra.
2. Obtenha uma credencial de dispositivo pelo fluxo administrativo `/api/printing/devices`.
3. Execute `Instalar.cmd`, selecione a impressora e informe a credencial. DPAPI protege a cópia local; o servidor guarda o hash.
4. Abra **Eleven Impressao**. Mantenha a janela, a sessão Windows e a conexão ativas.
5. Confira o último contato/conexão no ERP e envie uma solicitação explícita de teste. Verifique o papel antes de considerar a instalação concluída.

O agente consulta a API por HTTPS; não precisa abrir porta de entrada no computador.
Não é um serviço do Windows nem configura inicialização automática. Uma credencial
permite atualizar o nome do próprio dispositivo e buscar/concluir apenas seus trabalhos,
não consultar o ERP inteiro.

## Documentos

- Papel A4 comum; cada solicitação gera somente o documento solicitado, uma cópia.
- PY: somente destinatário e dados fornecidos, sem remetente ou campos de endereço obrigatórios.
- BR: destinatário e remetente cadastrado escolhido; UF/CEP e dados do fluxo são validados.
- CPF é opcional na impressão simples. Quando fornecido aparece ao final; ausente, zeros ou pedido “sem CPF” omitem a linha.
- Remetentes e padrões ficam no banco e são editados no gestor. Não há nomes, CPFs ou endereços reais no instalador.
- Modelos Word fornecidos originalmente serviram de referência; o ERP gera um PDF novo. Não imprime o documento histórico inteiro nem edita o Word remoto.
- ViaCEP completa campos vazios compatíveis e informa divergências, preservando os dados enviados.
- SuperFrete gera outro PDF, com requisitos próprios, e pode imprimir automaticamente após a emissão confirmada e liberação do arquivo.

## Solicitar no bot ou no ERP

Pelo Telegram, envie os dados e peça a impressão em linguagem natural. ADMIN/GERENTE
habilitado recebe prévia e botões; confirmar cria um trabalho na mesma transação da
ação. Várias prévias podem ser selecionadas por nome ou pela lista de botões.

No dashboard, **Gerar endereço** abre a preparação. No gestor é possível consultar
PDF, editar como nova cópia, escolher remetente/impressora e enviar. O histórico de
utilização reúne A4 e etiquetas, vinculados ao endereço único da agenda.

Para um documento avulso, envie **PDF** ao Telegram e peça para imprimir. Limites:
5 MB, 1–30 páginas, sem senha. Há confirmação e referência técnica temporária, sem
extrair texto, enviar conteúdo à IA ou armazenar o PDF no ERP. O Windows usa arquivo
temporário e o remove após processamento/retorno; a recuperação conclui a limpeza
quando necessário. Detalhes em [Fluxos do assistente](ASSISTENTE_FLUXOS_OPERACIONAIS.md).

## Estado e recuperação

`pending` → `claimed` → `submitted`, `uncertain` ou `failed`; também existem
`cancelled` e `expired`. **Enviado à impressora não significa papel fisicamente impresso.**

A API usa locks e a chave da solicitação para impedir execução duplicada. Não há
reatribuição automática de um claim perdido. O diário local é salvo antes de chamar
Sumatra; se o agente reiniciar após iniciar impressão, informa resultado incerto e
não reenvia o mesmo arquivo automaticamente.

Trabalhos não coletados expiram em 24h. A retenção depende da origem: conteúdo avulso
temporário é limpo, PDFs A4 podem ser regenerados pelos snapshots e etiquetas SuperFrete
persistidas continuam disponíveis no gestor. Não apagar filas ou snapshots para tentar
“destravar” uma impressão. Confira a fila do Windows antes de solicitar nova cópia.

Se não imprimir, confira: agente aberto, credencial válida, último contato, impressora
selecionada, Sumatra e estado do trabalho. Uma nova cópia deve ser uma ação explícita
com nova chave; repetir a mesma requisição técnica não deve imprimir outra folha.

## Validação

Os testes isolados cobrem credenciais, isolamento/revogação por dispositivo,
idempotência, expiração, recuperação e geração de documentos. Execução PowerShell e
saída física exigem o computador Windows da loja; testes em macOS/SQLite não os substituem.
Nenhuma impressão é enviada automaticamente só por rodar a suíte de testes.

Veja também [Gestor de endereços e SuperFrete](GESTOR_ENDERECOS_SUPERFRETE.md) e
[Operação](OPERACAO.md).

O pacote é montado a partir de `tools/eleven-print-agent` no checkout completo do
Render. Instalações Docker contendo apenas `backend/` não incluem esse diretório e
retornam 503 no download; nesses ambientes distribua o ZIP a partir do repositório.

### Validação da atualização Samsung — 07/10/2026

- Testes locais: 693 backend passaram (32 ignorados por dependerem de condições
  externas/ambientes específicos), 177 frontend passaram, tipagem e build aprovados.
- API: trocar o nome preserva ID, hash da credencial e trabalhos; repetição não cria
  dispositivo nem recolhe um trabalho. Credenciais revogadas e troca de ID são recusadas.
- Pacote: lista fixa de cinco arquivos, acesso ADMIN, sem `.env`, token, configurações
  locais ou diário. Download pela UI chegou à API com resposta 200; o navegador
  integrado não reportou evento de download, portanto o salvamento pelo navegador
  continua dependendo do suporte do navegador utilizado. O ZIP separado foi validado.
- Painel conferido em 320/384/1280px sem overflow horizontal. Nenhum envio real.
- CI agora executa `tools/eleven-print-agent/tests/Configuracao.Tests.ps1` no Windows
  PowerShell: análise sintática, escolha de fila, DPAPI, backup e preservação do diário,
  sem chamar Sumatra nem enviar trabalhos. Esse job passou para o commit `85ab59d`.
- O responsável confirmou a configuração no computador da loja após a entrega.
  Não foi feita impressão física durante os testes automatizados.
- Publicação confirmada Live: frontend `dep-db32gobl550s73cd7u50`, backend
  `dep-db32gobl550s73cd7to0`, ambos no commit `85ab59d`. O [CI completo](https://github.com/ferreiraluc/erp-eleven/actions/runs/37612169262)
  passou nos três jobs: backend, frontend e agente Windows.
