# Idiomas da interface

O ERP oferece português (`pt`), espanhol (`es`) e inglês (`en`). O idioma fica no
dispositivo e acompanha a sessão pelas opções da interface. `setLocale` atualiza
Vue I18n, `localStorage` e o atributo `lang` do documento. O fallback é português.

## Onde ficam os textos

- `frontend/src/locales/{pt,es,en}.json`: chaves existentes (`$t`/`t`), incluindo
  autenticação, conta, auditoria, administração e câmbio.
- `frontend/src/locales/uiText.json`: textos explícitos das telas operacionais,
  organizados pela frase original. `$tr('Salvar')` funciona no template;
  `uiText('Salvar')` funciona no script. Ambos usam a mesma função.
- `frontend/src/components/sales/`: catálogos locais do BI e dos lançamentos,
  usados com `useI18n({ useScope: 'local', messages })`.

A tradução é explícita no código. Não existe tradução automática do DOM, de
respostas inteiras da API ou de registros do usuário. Nome de cliente, descrição de
produto, código de rastreio, motivo de folga, anexo e texto escrito na planilha
continuam como foram informados. Erros textuais recebidos da API ou de provedores
externos preservam o original; as mensagens de fallback da interface são traduzidas.
Valores de enums, filtros e payloads da API
permanecem estáveis; somente seus rótulos recebem tradução.

## Mensagens e formatação

`uiText` aceita parâmetros para mensagens variáveis:

```ts
uiText('Tem certeza que deseja remover o rastreamento {0}?', {
  0: rastreamento.codigo_rastreio,
})
```

Os parâmetros são inseridos uma única vez, sem executar HTML nem traduzir seu
conteúdo. Continue exibindo o resultado por interpolação Vue, sem `v-html`.
Mensagens desconhecidas de provedores externos permanecem na origem; o catálogo
não deve tentar interpretar nomes ou informações operacionais nelas.

`uiLocale()` fornece `pt-BR`, `es-PY` ou `en-US` para `Intl`, datas e números.
`uiNumber(value, digits)` é exclusivo da exibição: não envie o texto formatado em
payloads numéricos. Máscaras/documentos, moeda escolhida e timezone da operação
não mudam junto com o idioma. Preserve `America/Sao_Paulo` onde o horário exige
Brasília.

Listas de rótulos que dependem do idioma devem ser `computed` ou calculadas durante
o render. Um `const` com rótulos traduzidos na inicialização fica preso ao idioma
anterior. Calendários usam `Intl` para os nomes de meses e dias da semana; chaves
dos dias devem ser índices/datas, pois iniciais repetidas não identificam colunas.

## Validação

`frontend/src/i18n/uiText.test.ts` verifica paridade PT/ES/EN e parâmetros do
catálogo operacional, referências literais e chaves dos 23 módulos operacionais,
interpolação segura, formatos numéricos e troca de calendário, paleta de cores,
comprovante e formulário de clientes sem reload. Os testes também verificam que
nomes de clientes/produtos e payloads permanecem intactos ao trocar o idioma.
Os stores de moeda e rastreio usam o mesmo catálogo; códigos e cálculos não mudam.
`utils/datetime.test.ts` verifica mudança de idioma, tempo relativo e virada de
dia em Brasília.
`frontend/src/components/sales/salesBi.test.ts` cobre o BI, seu card e a visão
pessoal sem ranking global.

```sh
npm --prefix frontend test
npm --prefix frontend run type-check
```

Ao traduzir outra tela, cubra também erros, confirmações, estados vazios, títulos
de botões/ícones, CSV e gráficos. Acrescente o módulo à verificação de referências
e teste a troca de idioma depois que seus dados já estiverem carregados.
