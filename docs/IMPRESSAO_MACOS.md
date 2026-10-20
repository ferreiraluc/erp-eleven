# Tickets no iMac — 3nStar RPT006W

Implementação **2026.10.20.1**, inicialmente em preparação. Publicar esta versão
não troca o destino automático, revoga credenciais nem instala programas na loja.
A validação física e a ativação devem ser feitas no iMac do caixa pelo responsável.
Samsung/A4, etiquetas e agentes Windows continuam com suas próprias filas.

## Arquitetura

`Venda confirmada (iMac/celular) → print_jobs no ERP/Render → HTTPS consultado pelo
agente do iMac → TCP local 9100 → 3nStar`.

O agente Swift nativo usa Foundation, CoreGraphics, CryptoKit e Security do macOS.
Não depende de Python, Homebrew, Sumatra, CUPS, janela do Terminal ou serviço externo.
Binário universal para **Intel e Apple Silicon, macOS 12+**. `LaunchAgent` executa
na sessão do caixa e reinicia o processo se ele encerrar. Inicia automaticamente
**após login nessa conta**, não antes do login/FileVault. O Mac deve permanecer
ligado, acordado e conectado; o instalador não altera suspensão ou rede.

A fila e o snapshot financeiro são os mesmos do PDV. O PDF de uma página, em
espanhol, é convertido em imagem monocromática ESC/POS (`GS v 0`, bandas de até
128 linhas). Papel de 80 mm, largura útil de 576 pontos, conteúdo proporcional
sem cortar margens. Há avanço e um corte parcial ao final (`GS V`), configurável
por `cut` no arquivo local. Acentos e código de barras não dependem de tabelas de
caracteres da impressora. O limite do gerador compartilhado permanece **991 mm**;
acima disso o ERP recusa o documento em vez de dividir silenciosamente.

## Rede e segurança

- Impressora: **192.168.123.100:9100**, Ethernet direta.
- Origem da conexão: **192.168.123.10**, Ethernet do iMac.
- O agente vincula o socket ao IP de origem; uma configuração ausente aguarda
  reconexão. Não reconfigura interfaces, DNS, gateway, firewall ou roteador.
- Internet para o Render pode permanecer pelo Wi-Fi. Preserve a rede direta já
  testada; não coloque gateway nessa interface se isso desviar a conexão à internet.
- Só são aceitos IPs IPv4 privados e porta 9100. Não há servidor HTTP/TCP local,
  porta aberta de entrada nem encaminhamento da porta 9100 para a internet.
- A URL HTTPS do ERP é fixa; redirecionamentos são recusados. A credencial do
  dispositivo só acessa seus trabalhos. Windows e macOS não compartilham tokens.
- Token no **Chaves do macOS**, serviço `com.eleven.tickets.escpos`; nunca em
  argumento de processo, ZIP, log ou frontend persistente.
- Pasta local `~/Library/Application Support/ElevenTickets`, permissão 700.
  Diário/configuração/PDF temporário têm permissão 600. Logs técnicos giram em
  64 KiB com uma cópia e não contêm documento, credencial ou resposta bruta do ERP.

## Instalar e validar sem substituir a Zebra antecipadamente

1. Entre como Lucas em **PDV → Tickets → Preparar 3nStar no Mac**. Isso cria
   `driver=escpos_tcp`, `purpose=tickets`, 80 mm contínuos, impressão automática
   **desativada**. Repetir a preparação reutiliza o dispositivo, sem duplicá-lo.
2. Guarde a credencial exibida e baixe o pacote macOS pelo mesmo painel.
3. No iMac do caixa, extraia todo o ZIP e abra **Instalar.command** como o usuário
   que usará o caixa, sem `sudo`. Cole a credencial exclusiva do Mac.
4. O instalador verifica SHA-256/assinatura ad hoc, preserva o diário e instala
   `~/Library/LaunchAgents/com.eleven.tickets.plist`. Ao terminar, pode fechar
   o Terminal. O Chaves pode pedir autorização de acesso na primeira execução.
5. No ERP, confira o último contato e clique explicitamente em
   **Imprimir teste na 3nStar**. É um documento de conferência, sem venda/estoque.
   Confira início/fim, largura, acentos, código de barras e corte.
6. **Atualizar estado** somente consulta. Quando o teste estiver enviado,
   marque **Conferi o papel** e clique **Ativar 3nStar para as próximas vendas**.
   Só Lucas pode fazer isso. A API exige teste enviado da própria impressora,
   contato recente (até 2 minutos), confirmação e ausência de pendentes/coletados
   no destino anterior. Não confunde aceite TCP com conferência física.
7. A troca desativa apenas `auto_receipts` do destino anterior, atomicamente,
   preservando o cadastro Zebra, credencial e histórico. Novas vendas, inclusive
   pelo celular, passam à 3nStar. Tickets antigos não são movidos nem reenviados.

O binário tem assinatura ad hoc para integridade, **não Developer ID/notarização
Apple**. Se o Gatekeeper bloquear o pacote baixado, use a abertura explícita pelo
menu de contexto/Privacidade e Segurança para este pacote. Não desative proteções
globais. Uma distribuição notarizada pode ser adicionada quando houver certificado
Developer ID disponível.

Para suspender novos tickets, use **Desativar impressão automática de novas vendas**.
Trabalhos já confirmados continuam na fila; isso não cancela impressões.

Para voltar ao Windows, conclua a fila do Mac, abra o agente Windows e use
**Retornar à impressora Windows → Confirmar retorno ao Windows**. A mesma trava
de fila impede abandonar trabalhos. Etiquetas/A4 não participam dessa troca.

## Reconexão, resultado incerto e recuperação

- Uma conexão TCP é aberta **antes** de coletar um novo ticket. Sem impressora,
  o trabalho permanece no ERP. Nova tentativa em 30 segundos.
- Tickets macOS pendentes **não expiram automaticamente** por ficarem offline.
  O comportamento de expiração dos agentes Windows permanece igual.
- Antes de coletar, o agente persiste uma chave UUID. A API guarda `claim_key`;
  perder a resposta HTTP e repetir a chave retorna o mesmo trabalho. Uma segunda
  chave não coleta outro trabalho enquanto houver um claim anterior pendente.
- Download e preparação podem ser repetidos; SHA-256, assinatura PDF, dimensões,
  página única e limite de 5 MB são conferidos antes do envio.
- O estado `sending` é gravado com flush antes do primeiro byte. Reiniciar nessa
  fase, ou falhar durante transmissão, vira `uncertain`, sem reenvio automático.
  A porta 9100 não fornece garantia transacional de impressão física.
- O aceite TCP gera `submitted`; confira o papel. Perder a resposta do resultado
  repete apenas a confirmação ao ERP, nunca o envio à impressora.
- Depois de o ERP aceitar o resultado, remove o PDF e o diário concluído local.
  Snapshot/histórico permanecem no ERP. Diário corrompido não é sobrescrito.
- Credencial rejeitada, conflito de claim ou erro de diário ficam no log; preserve
  os arquivos e consulte o suporte. Não apague o diário para tentar destravar.
- Uma nova cópia de venda é solicitada em **Vendas → Ticket/PDF**, com a confirmação
  e idempotência já existentes, depois de conferir impressora e papel.

`Iniciar.command`, `Parar.command` e `Diagnostico.command` são copiados para a
pasta instalada. Parar durante um envio pode gerar resultado incerto. Não instalar
a mesma credencial em dois Macs. Para atualizar, aguarde o ticket atual terminar
e execute o instalador novo; Enter mantém o token no Chaves.

## Código, publicação e validação

- Agente: `tools/eleven-ticket-agent-macos/Core.swift` e `main.swift`.
- Pacote universal: `bash tools/eleven-ticket-agent-macos/build.sh /tmp/Eleven-Tickets-macOS`.
- Testes nativos: `bash tools/eleven-ticket-agent-macos/test.sh`.
- A CI `macos-agent` testa sem rede real/impressora/Chaves/launchd e produz o ZIP.
  O artefato aprovado é publicado na release `print-macos-2026.10.20.1`; o painel
  aponta para esse pacote imutável. Não versionar binários/configurações da loja.
- API: `printing.py`, `receipt_printer_setup.py`, `pdv_receipts.py`. Migração
  `n6c7d8e9f0a1` acrescenta `driver` com padrão Windows e `claim_key` opcional único;
  não altera dados históricos nem o destino ativo.
- Cobertura: respostas perdidas de claim/resultado, reconexão antes do envio,
  envio parcial, reinício, diário corrompido, falha de gravação, PDF inválido,
  orientação das bandas, protocolo/rede, permissões, troca e preservação A4/Zebra.
  Migração/concorrência são verificadas em PostgreSQL isolado.
- Automação não comprova saída física, disponibilidade do firmware ESC/POS/corte,
  leitura do código pelo leitor real ou autorizações do macOS do caixa. Essas
  verificações fazem parte do teste explícito antes de ativar.

Referências: [3nStar RPT006 e ESC/POS](https://3nstar.com/product/direct-thermal-receipt-printer-80mm-3-rpt006/),
[Apple LaunchAgents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html),
[comando raster GS v 0](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lv_0.html),
[corte GS V](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_cv.html).
