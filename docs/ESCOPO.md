# Escopo do produto

Referência: operação definida pelo responsável da loja e código revisado em 30/09/2026.

## Operação da loja

O ERP coordena logística, produtos, equipe e impressão. Os vendedores continuam
lançando vendas nas planilhas do OneDrive. O BI é um consumidor de resultados
salvos; não substitui a planilha por um caixa novo nem altera seus lançamentos.

O dashboard reúne estoque, rastreamentos, folgas, status do sistema e câmbio.
No celular (até 600px), os rastreios recentes acompanham a rolagem da página;
no tablet e desktop, a lista mantém rolagem interna. O módulo de contas a receber
se chama **Pagadores**; a rota `/fiado` e os registros financeiros são preservados. Os
cards de Endereços e Visão de vendas exibem resumos antes de abrir o módulo, com
atalhos que levam diretamente à fila, impressão, etiquetas, vendedor ou período.
O resumo de vendas usa o último mês disponível e identifica seu ano e moeda.

## Capacidades atuais

| Domínio | Implementado | Regra importante |
| --- | --- | --- |
| Estoque | Produtos, variantes, fornecedores, código de barras, estoque por local, movimentações, importação e contagem | Cada entrada deve manter saldo e movimentação coerentes |
| Clientes/pedidos | Contatos, tags, anexos, valores e estado dos pedidos | Clientes de pedidos e clientes de PDV são entidades distintas |
| Rastreamento | Busca por nome/código/período/status, atualização Wonca e associação com pedidos | Bot consulta o estado salvo, sem inventar eventos |
| Folgas/equipe | Consulta de calendário e cadastro confirmado pelo bot | Um nome ou apelido que identifica um único vendedor basta |
| Endereços | Brasil/Paraguai, remetentes, vínculo opcional a cliente, padrões A4 e CEP | Mesmo destinatário/local é reutilizado; diferenças reais não são fundidas |
| Impressão | Prévias, fila, histórico, novas cópias e agente Windows | `submitted` é envio ao Windows, não confirmação física do papel |
| SuperFrete | Cotação, serviço, pagamento confirmado, recuperação de PDF, rastreio e impressão | Cotação não compra; resultado incerto não autoriza pagar novamente |
| BI | Total mensal/ano, comparação entre anos, ranking por vendedor/semana e moedas | Fechamento salvo prevalece; diferenças são destacadas para revisão |
| Assistente | Linguagem natural, ferramentas autorizadas, memória confirmada e botões Telegram | Mensagem comum ou texto de terceiros não é autorização para executar |
| Acesso/auditoria | Sessões revogáveis, contas individuais, troca de senha e atividade por usuário | Só Lucas administra usuários e consulta auditoria; vendas pessoais são filtradas no backend |

## Endereços e documentos

- A4 comum, uma cópia por solicitação. PY usa somente os dados enviados, sem remetente nem exigência de rua.
- BR usa destinatário e remetente escolhido. CPF informado aparece ao final; CPF ausente ou omitido a pedido não gera zeros.
- ViaCEP pode completar rua, bairro, cidade e UF vazios. Divergências são mostradas; não se inventam número, apartamento ou documento.
- Máscara de CEP, caixa, acentos e abreviações reconhecidas não criam outra entrada da agenda. Documentos/vínculos conflitantes e locais diferentes exigem conferência.
- Cada pacote ou impressão constitui uma utilização do endereço. O histórico reúne etiquetas e A4 do bot/ERP; imprimir diretamente no Word fora da ponte não é capturado.
- Os PDFs A4 são gerados a partir dos dados/padrões do ERP. Não existe edição remota dos documentos Word originais.
- Um PDF avulso enviado ao Telegram pode ser impresso com confirmação, sem cadastro e sem arquivar seu conteúdo no ERP. Há referências técnicas temporárias para entrega, idempotência e limpeza; o original continua no Telegram.
- PDFs avulsos: até 5 MB, 1–30 páginas, sem senha. DOCX, áudio e fotos não entram nesse fluxo de impressão.
- Etiqueta SuperFrete é outro fluxo: exige os dados do provedor, peso, medidas e conteúdo reais; pagamento usa saldo da conta. O PDF emitido é persistido e pode ser enviado ao Telegram/impressora quando ficar pronto.
- O gerador de pessoa 4Devs usa o formulário público ou importação JSON. A pessoa é editável e somente os campos de remetente são cadastrados após aprovação manual. A origem sintética é preservada; CPF com formato válido não comprova identidade.

## Assistente e memória

Telegram em grupo é o canal operacional atual. WhatsApp 1:1 via Twilio tem adaptador
e flags próprias; conta/remetente ainda dependem da habilitação externa. Meta direta
foi investigada, mas não foi implementada. Não há bot em grupo WhatsApp neste código.

O bot prioriza envios em trânsito ao pedir rastreio de um cliente; entregues exigem
pedido de histórico. Cada código de um destinatário identificado é enviado sozinho,
seguido dos detalhes em outra mensagem. Vários pacotes atuais podem gerar vários pares.

Prévias oferecem botões, seleção por nome e validade de 24h. O backend verifica autor,
conversa, permissões e execução única. Gestores habilitados podem cadastrar folgas,
produtos e entradas de estoque, preparar impressões e emitir etiquetas pelos fluxos
confirmados. Relatos de venda/devolução são ocorrências: não movimentam caixa ou estoque.

Memória compartilhada guarda ocorrências confirmadas, apelidos e catálogo de ferramentas.
O contexto bruto é limitado ao autor/canal/conversa. Dados atuais são consultados novamente.
Não há SQL livre nem permissão de administrador irrestrita para o modelo.
Contas com vendas pessoais não recuperam dados de colegas pelas consultas nem pelo
contexto anterior à restrição. Fotos de comprovantes postais JPG/PNG têm leitura
específica: códigos válidos, prévia e confirmação. A foto não é arquivada no ERP.

## Vendas e integrações financeiras

`/vendas` e a importação de lançamentos gravam em `vendas`; PDV/fiado usam tabelas
`pdv_*`; `/bi-vendas` usa snapshots de planilhas. São três fontes diferentes e não
podem ser somadas como se fossem o mesmo faturamento.

O PDV confere o estoque por local ao concluir, recusa saídas acima do saldo e
devolve ao local original ao cancelar. Quantidades de catálogo são inteiras;
avulsos não movimentam estoque. Limites, concorrência e pendências do cancelamento
financeiro estão no [guia de estoque](ESTOQUE_OCR.md#estoque-no-pdv).

Ajustes manuais incorporados nas células entram no resultado do BI sem expor fórmulas.
Arquivos mensais têm prioridade sobre a planilha corrente do mesmo período, evitando
contagem dupla. Um valor ausente permanece ausente; zero é um resultado válido.
Os lançamentos individuais permanecem ligados à planilha, aba e linha de origem.
Linhas iguais podem ser vendas diferentes: não são eliminadas por valor/nome iguais.
Dias/horas ausentes não são inferidos do horário da sincronização. Ajustes no total
mensal não são distribuídos artificialmente entre os lançamentos.

Denis, Sol e Junior consultam suas vendas; Lucas e Wissam consultam o geral.
O acesso operacional aos demais módulos continua disponível. Sessões antigas são
revogadas ao mudar permissões ou senha. O registro de tempo é uma estimativa de
atividade nas telas, não uma medida de jornada. Veja [Acesso](ACESSO_AUDITORIA.md).

A revisão manual autorizada dos arquivos históricos de setembro/2026 foi uma manutenção
pontual da origem, não uma capacidade de escrita do conector OneDrive.

## Limites e próximos trabalhos

Não estão implementados: Meta Cloud API direta, leitura de áudio ou fotos genéricas pelo assistente,
serviço Windows sem sessão aberta, sensor de impressão física, OCR geral de documentos
recebidos pelo bot, edição de Word e escrita automática em planilhas. O OCR do estoque
é um fluxo separado com o provedor de visão configurado. O bot não registra vendas PDV, reembolsos ou saídas
arbitrárias de estoque.

A cobertura técnica e as pendências de manutenção estão em
[AUDITORIA_MANUTENCAO.md](AUDITORIA_MANUTENCAO.md). Um módulo acessível não é código morto
só por ter pouco uso; sua retirada exige avaliar dados, referências e consumidores.
