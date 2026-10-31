# Cadastro de rastreios por foto do comprovante

O Telegram e o WhatsApp Web conectado para a equipe aceitam uma foto, JPG ou PNG de comprovante postal acompanhada de
“Cadastre os rastreios deste comprovante”. Também é possível enviar a foto e pedir
o cadastro na mensagem seguinte. No Telegram, também é possível responder à própria foto. A foto isolada apenas
recebe uma orientação; nada é cadastrado automaticamente.

No Telegram, se a mensagem trouxer uma foto ou documento novo, esse anexo tem prioridade sobre
o da mensagem respondida. O bot só reutiliza o anexo da resposta quando não há
anexo atual, mantendo as restrições de autor, conversa e tópico. Isso evita gerar
a prévia de um comprovante antigo ao enviar uma foto nova como resposta.

## Conferência e gravação

1. O servidor valida o formato e remove metadados. No Telegram o download ocorre
   em memória; no WhatsApp a ponte autenticada entrega a imagem para armazenamento
   temporário protegido, vinculado ao autor e à conversa.
2. O serviço de visão extrai até 20 códigos postais e, quando legíveis e associados
   ao objeto, destinatário, cidade e UF. Não extrai CPF, cartão, preço nem texto bruto.
3. O backend verifica o formato de 13 caracteres e o dígito verificador S10. Não
   troca letras por números, completa código cortado ou corrige dígitos automaticamente.
4. A prévia mostra os dados lidos e eventual pedido sugerido. O autor confere a foto
   original e usa **Cadastrar rastreios** ou **Cancelar**; a prévia vale por 24 horas.
5. Confirmar grava os objetos em `/rastreamento`, com autor e status **Pendente**.
   Os eventos/status de transporte vêm das consultas normais do ERP; a foto não
   comprova entrega nem altera automaticamente o status administrativo do pedido.

Os códigos já existentes, inclusive inativos e variantes legadas de caixa/espaços,
são ignorados. A confirmação repetida não cria outra entrada nem reativa registros.
Quando um código é cadastrado por outro fluxo entre prévia e confirmação, ele também
é ignorado, sem sobrescrever destinatário ou associações. A notificação de rastreio
cadastrado segue o mesmo outbox usado pelo restante do ERP.

## Vínculos com pedidos e clientes

A prévia pode sugerir um pedido aberto quando o código já está informado nele ou
quando o nome completo lido corresponde exatamente a um único pedido aberto ainda
sem rastreio. A sugestão e seu motivo aparecem antes da confirmação; nomes parciais,
vários pedidos ou destinatário ilegível permanecem sem vínculo automático.

O cliente é herdado do pedido explicitamente mostrado na prévia, por ID. Não se cria
cliente pelo nome da foto. Mudanças no pedido, código ou cliente após a prévia fazem
a confirmação parar antes de cadastrar o lote, para uma nova conferência. Pedidos
entregues/cancelados não são escolhidos. Mais de um pacote pode compartilhar o pedido
conferido; o campo de código principal não é sobrescrito por cada novo pacote.

## Operação e privacidade

- Exige identidade do canal vinculada, ativa, permissão `can_register` e perfil
  ADMIN/GERENTE, igual às demais ações operacionais confirmadas do assistente.
- Foto do próprio autor, na mesma conversa/tópico, recebida nas últimas 24 horas.
- Até 5 MB, JPG/PNG estático, 32–8000 pixels por lado e até 20 megapixels.
- No Telegram, a referência de download é removida após extrair uma prévia válida
  ou pela limpeza normal de anexos após 24 horas. Bytes da foto não são gravados.
- No WhatsApp, os bytes normalizados ficam temporariamente no banco por até 24 horas
  desde o recebimento; são apagados imediatamente após preparar a prévia. Há limites
  de 25 MB por usuário e 100 MB globais, compartilhados com os PDFs temporários.
  Anexos vencidos não podem ser lidos mesmo antes da próxima limpeza periódica.
- A ação conserva apenas os dados mínimos propostos, IDs e resultado da confirmação.
  O original continua no aplicativo de mensagens conforme as regras do canal.
- A imagem é transmitida ao provedor configurado em `VISION_PROVIDER`. O padrão
  `auto` usa a chave DeepSeek existente e `DEEPSEEK_VISION_MODEL=deepseek-flash`;
  se não houver chave DeepSeek, usa Anthropic com `ANTHROPIC_API_KEY` e
  `claude-haiku-4-5`. Também é possível escolher explicitamente `deepseek` ou
  `anthropic`. Uma falha na chamada não provoca reenvio a outro provedor.
  Sem a chave do provedor escolhido, o bot explica a configuração faltante.
- Não há pagamento, impressão, consulta externa do rastreio nem efeito em estoque
  durante a extração. A auditoria de mutações existente registra a confirmação.

## Limites e validação

OCR pode falhar; checksum não prova que um pacote existe e não impede toda troca
de caracteres. A conferência humana continua obrigatória. Foto borrada, códigos
conflitantes ou lote parcialmente ilegível são recusados em conjunto; envie recortes
mais nítidos. Não há interpretação de PDF, áudio ou vídeo neste fluxo; PDFs
continuam pertencendo à ponte de impressão avulsa. O WhatsApp via Twilio antigo
não recebe este suporte a anexos.

Código: `services/receipt_vision.py` valida mídia/extração e `receipt_tracking.py`
prepara/confirma o cadastro. Os adaptadores e controles usam as tabelas existentes
de mensagens e ações. `assistant_whatsapp_media` mantém apenas os anexos temporários
autorizados da ponte WhatsApp. O vínculo de cliente usa
o serviço comum `customer_links.validate_tracking_links`.

```sh
PYTHONPATH=backend DATABASE_URL=sqlite:// backend/venv/bin/python -m pytest backend/tests/test_receipt_tracking.py -q
```

Os testes substituem Telegram e os provedores de visão, verificam permissões, isolamento, prévias,
duplicação, mudanças de vínculos e validação dos bytes/códigos. Não enviam imagens
reais a provedores. SQLite não demonstra os advisory locks/concorrência PostgreSQL.
`test_receipt_attachment_precedence.py` cobre a seleção do anexo desde a mensagem
Telegram até a prévia, incluindo respostas a documentos anteriores.

Uma verificação adicional com a API real DeepSeek leu um comprovante sintético,
reconhecendo o objeto e destinatário, sem escrever no banco ou enviar mensagens.
Isso confirma a conexão, não a precisão para todas as fotografias reais.

Referências oficiais: [visão da DeepSeek](https://api-docs.deepseek.com/guides/vision/),
[visão da Anthropic](https://platform.claude.com/docs/en/build-with-claude/vision),
[Telegram getFile](https://core.telegram.org/bots/api#getfile) e
[padrão postal S10 da UPU](https://www.upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf).
