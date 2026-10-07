# Frontend Eleven

Vue 3 + TypeScript + Vite + Pinia. Este é o frontend do ERP em produção, não um template.

Os 15 módulos roteados usam `components/ModuleHeader.vue`: voltar ao dashboard,
título e ações, sem textos promocionais. O componente centraliza tipografia,
espaçamento e botões compactos (34px no desktop, 32px até 600px), permitindo quebra
de linha quando necessário. A página continua responsável pelas permissões,
visibilidade e eventos das ações. `showBack` preserva o bloqueio de navegação na
troca obrigatória de senha; o slot `meta` mantém a identificação em Minha conta.
Dashboard e login conservam seus cabeçalhos próprios. Novos módulos devem reutilizar
esse componente, sem copiar os estilos antigos de cabeçalho.

```sh
nvm use
npm ci --include=dev
cp .env.example .env.local
npm run dev                # http://localhost:3000
npm run type-check         # verificação TypeScript
npm run build              # bundle em dist/
npm run preview            # prévia do build em localhost:4173
npm run lint               # apenas verifica; dívida de any registrada na auditoria
npm run lint:fix           # modifica arquivos
```

`VITE_API_BASE_URL` é pública e definida no build. Nunca colocar segredos nela.
O router usa history no desenvolvimento e hash em produção.

- `src/views`: páginas declaradas no router.
- `src/components`: componentes dos módulos; `dashboard/` contém os resumos de endereços/vendas.
- `src/services`: Axios e contratos; `stores`: estado Pinia.
- `src/assets/main.css`: estilos globais; CSS de componentes fica junto deles.
- `src/locales`: pt/es/en. Parte das telas operacionais ainda possui textos fixos em português.
- `env.d.ts`: tipagem de ambiente Vite e da notificação global.
- `server.js` e `Dockerfile`: alternativa local em container. Render publica `dist` diretamente.

O mapa dos módulos e os critérios de mudança estão em
[Arquitetura](../docs/ARQUITETURA.md) e [Desenvolvimento](../docs/DESENVOLVIMENTO.md).
