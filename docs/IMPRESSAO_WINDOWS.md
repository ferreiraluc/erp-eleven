# Impressão da Eleven no Windows

## Tickets do PDV — Zebra ZD220 (14/10/2026)

O agente **2026.10.14.2** possui dois perfis independentes. **Eleven Impressao**
continua em `%LOCALAPPDATA%\ElevenPrint`, para Samsung/A4. **Eleven Tickets** usa
`%LOCALAPPDATA%\ElevenPrintTickets`, outra credencial, configuração e diário.
Não reutilize a credencial da Samsung na Zebra. Ambos podem funcionar no mesmo Windows.

Configuração inicial autorizada: Zebra USB, térmica direta sem ribbon, etiquetas
separadas de **60 × 80 mm**. Confirme a orientação: largura é a dimensão atravessando
a cabeça de impressão; se a etiqueta estiver invertida, ajuste os dois valores no
ERP e no driver. O driver Zebra e SumatraPDF precisam estar instalados. O instalador
não instala driver, não altera a mídia e não calibra a impressora.

1. Lucas abre **PDV → Tickets**, confere largura/altura e salva. Começa desativado.
2. Copia a credencial exibida uma única vez; baixa **agente Windows para tickets**.
3. No Windows, extrai o ZIP e abre `Instalar.cmd`. Seleciona a Zebra e informa sua
   credencial exclusiva. O pacote chama `Instalar.ps1 -Profile tickets`.
4. Nas preferências da fila Zebra, configura o mesmo tamanho **60 × 80 mm**,
   orientação retrato e etiquetas com intervalo, conforme a mídia real. Faz a
   calibração pelo procedimento do fabricante se necessário.
5. Abre **Eleven Tickets** e aguarda Conectado. O agente confere o papel padrão
   do driver antes de despachar e imprime em tamanho real, sem a regra A4.
6. Em PDV → Tickets, ativa **Imprimir ao confirmar a venda, inclusive pelo celular**.
   A próxima venda confirmada nesse PDV enfileira uma cópia. A configuração sozinha
   não imprime e não cria vendas. O recibo mostra estado e atualização manual.

### Janela fecha ao abrir os arquivos baixados

Depois da instalação, abra o atalho **Eleven Tickets** da Área de Trabalho.
`Impressao.ps1` é uma biblioteca auxiliar e não inicia a fila. `Agente.ps1` na pasta
do download não possui a credencial/configuração, que fica em
`%LOCALAPPDATA%\ElevenPrintTickets`. Não copie `config.json` para o download.

A versão 2026.10.14.2 orienta esses dois casos, mantém erros iniciais visíveis e
cria o atalho com `-NoExit`, inclusive para falhas anteriores à execução do script.
O ZIP de tickets também fixa o perfil no próprio `Instalar.ps1`, para não selecionar
o perfil A4 quando aberto diretamente pelo PowerShell. Prefira **Extrair tudo →
Instalar.cmd**. Para atualizar, feche o agente do mesmo perfil e rode o instalador
novamente; Enter mantém a credencial. Configuração e diário existentes são preservados.

Vendas feitas no celular usam a fila no servidor; não precisam conectar-se por USB,
AirPrint ou à mesma rede local. Windows, agente, internet e impressora devem estar
ligados. O agente consulta a cada três segundos; isso não é garantia de prazo de
saída física. Trabalhos não coletados expiram em 24 horas. Não há serviço/início
automático nesta versão.

Cada etiqueta é uma página física. Tickets longos podem consumir várias etiquetas,
sempre identificadas pela venda e página, sem cortar conteúdo para forçar uma página.
Para bobina contínua, compre papel **térmico direto** compatível com a ZD220, sem
adesivo; o fabricante informa largura imprimível máxima 104 mm e rolo de até 127 mm
de diâmetro. Confira também núcleo/espessura e a configuração do sensor no driver.
Esta versão usa altura fixa configurável de 50–400 mm; não calcula corte automático
nem promete guilhotina. Trocar mídia exige ajustar driver e ERP, com fila vazia.

O ticket é um snapshot dos dados da venda na confirmação; a renderização PDF ocorre
no servidor quando o agente busca o trabalho. Nenhuma IA ou API paga é utilizada.
O snapshot permite preservar o comprovante mesmo depois de alterações no catálogo.
A fila é criada na mesma transação da venda: rollback não deixa um ticket órfão.
Sem impressora configurada/ativada, vender e imprimir pelo navegador continua possível.

Repetir o envio original devolve o mesmo trabalho. **Outra cópia** exige confirmação,
conserva a chave em falhas de rede e é bloqueada enquanto uma cópia está pendente ou
em processamento. `uncertain` não é reimpresso automaticamente. Confira o Windows e
o papel antes de confirmar nova cópia. Falha na geração marca o trabalho como falho
antes de imprimir e libera os trabalhos seguintes.

Somente Lucas configura tickets/credenciais; funcionários imprimem apenas vendas
que podem consultar. Tickets não entram na agenda de endereços nem nas consultas
de impressões do bot. O bot/SuperFrete continuam selecionando apenas impressoras A4.
Credencial perdida pode ser substituída explicitamente em PDV → Tickets; a anterior
para de funcionar e o instalador deve receber a nova. Não faça isso com trabalho
em processamento. ID e histórico do dispositivo são preservados.

**macOS ainda não está implementado no agente Eleven.** Na mudança do caixa, será
necessário preparar uma ponte compatível com CUPS e validar a fila real. O fluxo
celular → ERP → computador → Zebra será o mesmo; este ZIP é exclusivo do Windows.

Referências: [Zebra ZD220](https://www.zebra.com/us/en/products/spec-sheets/printers/desktop/zd220.html),
[CUPS no macOS](https://support.zebra.com/article/000012134).

Validação: testes isolados de snapshot, acesso por vendedor, rollback, reenvio,
separação A4/tickets, mídia PDF e pacote; migração e concorrência em PostgreSQL
isolado; testes PowerShell sem spool físico. A saída na Zebra real depende da
instalação e conferência pelo responsável; teste automatizado não comprova papel.

## Instalação e operação atuais

O bot Telegram, o gestor de endereços e as etiquetas compartilham o mesmo agente
Windows e a mesma fila. Em 07/10/2026 a loja informou a troca para **Samsung
SL-M2035W**, já imprimindo pelo Windows. O responsável confirmou a configuração do agente após a atualização.
O laptop de desenvolvimento é outra máquina; não instalar nele um segundo agente.

Pacote: `tools/eleven-print-agent/`, com `Instalar.cmd`, `Instalar.ps1`,
`Configuracao.ps1`, `Agente.ps1`, `Impressao.ps1` e `LEIA-ME.txt`. Após a configuração da Samsung,
o painel de instalação/download foi retirado de Endereços a pedido do responsável.
O pacote continua no repositório e no endpoint administrativo autenticado
`/api/printing/agent-package`, que inclui somente esses seis arquivos e nunca
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

## Recuperação e diagnóstico — 13/10/2026

Versão do agente: **2026.10.13.1**. A atualização do servidor é compatível com o
agente anterior, mas não substitui os arquivos instalados na loja. O responsável
informou que fará a instalação depois. Entregar o ZIP completo e seguir os passos
acima, mantendo a credencial com Enter e preservando `journal` e `config.json`.
Não alterar a fila/driver que já imprime no Windows apenas porque o nome difere
do modelo comercial.

- `preparing`: diário salvo antes do download. Até três tentativas de download,
  tamanho máximo 5 MB, assinatura PDF e SHA-256 conferidos. Pode retomar após
  reinício, pois o Sumatra ainda não foi chamado.
- `started`: diário persistido imediatamente antes de chamar o renderizador.
  Reinício nessa fase vira `uncertain`; nunca repete o envio automaticamente.
- `failed`: erro conhecido antes do envio (download, integridade, configuração,
  spooler parado ou impossibilidade de iniciar Sumatra). Corrigir e solicitar
  nova cópia explicitamente; não reenfileirar antigos automaticamente.
- `submitted`: processo terminou com código 0, usando handle preservado até
  consultar `ExitCode`. Não comprova impressão física.
- `uncertain`: timeout de 120 segundos, erro do renderizador ou interrupção depois
  de iniciar. O timeout tenta encerrar somente o processo aberto para aquele
  trabalho; não limpa a fila nem fecha outras janelas Sumatra. PID e horário de
  criação evitam confundir um processo posterior. Enquanto esse processo ainda
  estiver ativo, o agente pausa novos trabalhos; confira o Windows.

O agente envia apenas código de diagnóstico, versão, duração e código de saída,
sem logs livres, caminhos, credenciais ou conteúdo do documento. ERP (Impressões)
e bot (`consultar_impressoes`/consulta de endereços) mostram a explicação. A migração
`g9b0c1d2e3f4` adiciona JSON opcional e não reescreve históricos. Resultados do agente
antigo seguem aceitos, mas não permitem descobrir retrospectivamente a causa.

Os registros consultados para o incidente mostraram nove A4 incertos na semana e
nove etiquetas aceitas; um A4 demorou aproximadamente 121 segundos e a nova cópia
posterior levou quatro segundos. O primeiro intervalo é compatível com timeout,
mas os logs antigos não comprovam a causa dos demais. O código anterior também
classificava falhas de download como incertas e descartava o motivo técnico.

A CI Windows testa download intermitente, PDF inválido, reinício, falha do spooler,
processos de teste com saída 0/erro e timeout, sem executar Sumatra ou imprimir.
A validação física continua pendente da instalação e de uma impressão solicitada
pelo responsável no computador da loja.

### Cinco apresentações A4

Em **Endereços e envios → Padrões**, escolha alternância automática (padrão) ou
um modelo fixo: Clássico, Tabela, Blocos, Colunas ou Ficha compacta. A escolha usa
uma distribuição determinística pela chave aleatória da solicitação: novas
solicitações podem variar, mas uma prévia/repetição técnica mantém o mesmo modelo.
O sorteio pode repetir um modelo em solicitações consecutivas. Não usa IA paga.

O bot informa o modelo na prévia com os botões de confirmação existentes. ERP e
bot guardam a escolha no snapshot; PDF histórico sem modelo mantém o Clássico.
A alternância altera apenas a apresentação, preservando o remetente escolhido e
todos os campos habilitados. PY continua sem remetente, CPF/RUC ausente é omitido.
Os formatos em duas colunas limitam a fonte a 15 pontos (remetente: 14) para caber
na folha; os demais respeitam a configuração. SuperFrete e PDFs avulsos não mudam.

### Reimpressão e apresentação do ticket

**Vendas → Ver venda → Ticket / PDF** reutiliza a fila Zebra e a confirmação de
nova cópia. O PDF em espanhol é gerado no servidor; a mudança visual não exige
reinstalar o agente. Baixar/visualizar é somente leitura, sem enviar à impressora.
O ticket inclui Code 128 com localizador de 10 caracteres e UUID completo impresso;
a busca e as restrições de acesso estão descritas em [Vendas PDV](VENDAS_PDV.md#consultar-baixar-e-reimprimir-tickets).
A etiqueta de 60 × 80 mm pode receber várias páginas; mantenha o formato igual no
ERP e no driver. O leitor foi validado por software a 203 dpi; legibilidade física
depende de mídia, escala e calibração da Zebra.
