# Impressão da Eleven no Windows

## Instalação e operação atuais

O bot Telegram e o gestor de endereços já enviam trabalhos para a HP LaserJet
M14-M17 no computador Windows da loja. O responsável confirmou impressão física
A4 em 22/09/2026. O laptop de desenvolvimento é outra máquina; não instalar nele
um segundo agente conectado à fila da loja.

Pacote: `tools/eleven-print-agent/`, com `Instalar.cmd`, `Instalar.ps1`, `Agente.ps1`
e `LEIA-ME.txt`. Requisitos: driver da HP, SumatraPDF funcionando e credencial do
dispositivo criada por ADMIN. O instalador não baixa programas de terceiros.

1. Instale o driver e o SumatraPDF no Windows; teste um PDF diretamente pelo Sumatra.
2. Obtenha uma credencial de dispositivo pelo fluxo administrativo `/api/printing/devices`.
3. Execute `Instalar.cmd` e informe os dados pedidos, incluindo a credencial. DPAPI protege a cópia local; o servidor guarda o hash.
4. Abra **Eleven Impressao**. Mantenha a janela, a sessão Windows e a conexão ativas.
5. Confira o último contato/conexão no ERP e envie uma solicitação explícita de teste. Verifique o papel antes de considerar a instalação concluída.

O agente consulta a API por HTTPS; não precisa abrir porta de entrada no computador.
Não é um serviço do Windows nem configura inicialização automática. Uma credencial
permite buscar e concluir apenas trabalhos daquele dispositivo, não consultar o ERP inteiro.

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
