# Geração e revisão de remetentes

O gestor **Endereços e envios → Remetentes → Gerar pessoa · 4Devs** permite gerar uma pessoa sintética, revisar e editar seus dados e salvar um remetente somente após aprovação manual. O fluxo inteiro (gerar, importar e aprovar/salvar) é exclusivo do proprietário **Lucas (`lucas@eleven.com`, perfil ADMIN)**. O botão fica oculto para os demais usuários, e os três endpoints recusam não proprietários com HTTP 403. A equipe mantém o cadastro e a edição normais de remetentes, conforme as permissões do gestor (ADMIN/GERENTE). Não emite etiquetas, envia mensagens ou imprime documentos ao gerar ou salvar.

## Como usar

1. Abra **Gerar pessoa · 4Devs**. Escolha estado, sexo e idade opcional (18–90 anos) e solicite a geração.
2. Confira nome, documento, contato e endereço. A seção de dados completos permite visualizar e editar os demais campos retornados, como nascimento e filiação.
3. Revise a prévia do bloco impresso e a identificação do remetente. Marque a aprovação e clique em **Aprovar e salvar remetente**. Qualquer nova edição desmarca a aprovação.
4. O remetente passa a aparecer na lista, identificado como de **origem sintética**. A impressão e a emissão de frete continuam usando seus próprios passos de confirmação.

Os dados são sintéticos e não comprovam identidade ou titularidade de CPF, endereço ou telefone. A revisão é responsabilidade de quem aprova o cadastro; gerar um documento com formato válido não valida a identidade de um remetente. O ERP não mistura a geração com cadastros reais de clientes.

## Integração e alternativa manual

Em 30/09/2026, a [página oficial da API 4Devs](https://www.4devs.com.br/4devs_api) informa que a API ainda está em preparação. Esta implementação **não usa uma API pública documentada**: um adaptador chama o formulário web público do [gerador de pessoas](https://www.4devs.com.br/gerador_de_pessoas). Esse contrato pode mudar ou ficar indisponível.

A chamada usa exclusivamente `https://www.4devs.com.br/ferramentas_online.php`, uma pessoa por requisição, opções permitidas pelo formulário e identificação do ERP. Possui limites de tempo (5 segundos para conexão e 20 para leitura), resposta de até 64 KB e intervalo mínimo de 10 segundos por usuário/processo. Não aceita URL fornecida pelo cliente, não segue redirecionamentos e não envia cookies do navegador. Não há tentativas automáticas, contorno de CAPTCHA ou de bloqueios.

Se o site bloquear a integração, mudar o formulário ou estiver indisponível, use **Abrir gerador 4Devs**, faça a geração no site e cole o JSON de uma única pessoa na opção de importação. A importação leva à mesma revisão; não salva automaticamente. O ERP aceita somente campos conhecidos e valores textuais curtos, rejeita múltiplas pessoas, estruturas inesperadas e respostas grandes.

## Dados persistidos e autorização

- Gerar e importar retornam uma prévia com `Cache-Control: no-store`; não criam registros no banco.
- Somente Lucas pode autorizar o remetente gerado; ter outro e-mail ADMIN ou apenas o e-mail Lucas sem o perfil ADMIN não concede essa permissão.
- A gravação exige `approved=true` e uma chave UUID de requisição. Repetir a mesma aprovação com os mesmos dados e autor reutiliza o cadastro. Reutilizar a chave com outro conteúdo ou autor gera conflito.
- Apenas identificação, campos úteis de endereço/contato/documento, linhas de impressão, estado ativo e origem/revisor/data são salvos em `PrintSender`.
- Nascimento, filiação, RG, senha sintética e características pessoais exibidos na prévia não são persistidos. Também não são enviados ao bot ou ao serviço de frete ao salvar o remetente.
- A marca de origem sintética fica em `PrintSender.data._generator` e permanece ao editar posteriormente. A interface não oferece um controle para apagá-la.
- Não há migração adicional: o registro usa o campo JSON existente do remetente. A auditoria geral registra a operação; credenciais externas não são necessárias para esse adaptador.

## Código e validação

- Serviço: `backend/app/services/sender_generator.py`.
- Endpoints: `POST /api/address-manager/sender-generator/generate`, `/import` e `/save`.
- Interface: `SenderGeneratorModal.vue` e `services/senderGenerator.ts`.
- Testes: `backend/tests/test_sender_generator.py` cobre fornecedor simulado, limites, falhas, aprovação, idempotência, dados não persistidos e preservação da origem.

Os testes automatizados usam respostas simuladas. Em 30/09/2026, uma única verificação autorizada do formulário real retornou com sucesso uma prévia sintética com os campos completos; a pessoa ficou somente em memória, sem gravação no banco, emissão de etiqueta ou impressão. Essa verificação pontual não garante disponibilidade futura: o formulário depende do 4Devs e o caminho manual permanece disponível. Interface e mensagens do fluxo têm versões em português, espanhol e inglês.
