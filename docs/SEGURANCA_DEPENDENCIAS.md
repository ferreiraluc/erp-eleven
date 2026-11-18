# Segurança de dependências

## Verificação e atualização

As mudanças passam por PR, com as validações protegidas existentes. Dependabot
consulta semanalmente o npm do frontend e do agente WhatsApp, o pip do backend e
as versões das GitHub Actions. Abre até duas PRs de versão por ecossistema,
agrupando atualizações minor/patch; não mescla nem publica automaticamente.
Alertas e atualizações de segurança do próprio GitHub dependem também das opções
habilitadas no repositório. A configuração não garante ausência de vulnerabilidades
entre uma consulta e outra.

O backend mantém `pip-audit`; o agente WhatsApp mantém `npm audit`. No frontend,
`node scripts/audit-dependencies.mjs` executa uma consulta npm nova de **todas** as
dependências, incluindo ferramentas de desenvolvimento, depois do build. O JSON
original permanece nos logs. Erro de rede, JSON inválido, advisory desconhecido ou
relatório incompatível bloqueiam a validação. Achados fora da exceção abaixo,
inclusive de menor severidade, exigem análise/correção.

Para repetir localmente, a partir de `frontend/`:

```sh
npm ci --include=dev
node --test scripts/audit-dependencies.test.mjs
npm run build
node scripts/check-build.mjs
node scripts/audit-dependencies.mjs
```

## Revisão de 17/11/2026 — frontend

- A família transitiva `typescript-eslint` passou de `8.71.1` para `8.73.0`.
  Ela usa `minimatch` `11.0.9`, corrigindo o
  [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
  As instâncias `3.1.5` de ESLint estão fora da faixa afetada desse advisory.
- Não foram feitos downgrades de Vite/Vitest para aparentar remoção de alertas
  transitivos. O npm pode sugerir versões antigas com outros compromissos; isso
  não substitui a avaliação da causa do alerta.

### Exceção temporária: picomatch

**Risco conhecido, não corrigido.**
[GHSA-fc5q-39xc-vjpf / CVE-2026-112366](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
descreve negação de serviço por expressão glob maliciosa. Na revisão, o registry
publica `4.0.7` como última versão e o advisory não indica versão corrigida. A
[tentativa upstream #235](https://github.com/micromatch/picomatch/pull/235) foi
fechada sem merge; não incorporamos patch experimental nem renomeamos a biblioteca
para ocultá-la do scanner.

Aceite técnico limitado até **01/12/2026 às 00:00 UTC**, expresso em
`frontend/scripts/audit-dependencies.mjs`, sob estas condições verificadas no CI:

1. Somente o advisory exato acima, com a severidade/faixa revisadas, e suas cadeias
   transitivas podem passar. As versões revisadas são `2.3.2`, `4.0.4` e `4.0.7`.
   Qualquer outro advisory, nova versão publicada de picomatch ou expiração bloqueia.
2. O build precisa ser recente (até 30 minutos) e corresponder ao hash do lock
   atual. Um plugin Vite registra os pacotes dos módulos realmente emitidos em
   `dist/security-build-report.json`, sem caminhos locais nem conteúdo dos produtos.
   As compilações independentes dos workers também usam o plugin e entram no
   relatório, pois o Vite as inclui como assets no bundle principal.
3. O bundle não pode incluir picomatch ou os intermediários glob revisados, nem
   imports externos não analisados. O servidor Node opcional também tem seus
   imports e dependências transitivas percorridos; se alcançar glob, falha.
4. O destino documentado continua sendo o frontend **estático** do Render. O Node
   com essas ferramentas roda no desenvolvimento/build/CI, não atende as buscas
   dos clientes. Os padrões dessas ferramentas vêm do código/configuração revisados
   no repositório; o ERP não recebe globs de usuários para executar nelas.

Isso não afirma que picomatch seja seguro em outros usos. Um autor de código de
build pode introduzir padrão malicioso e provocar travamento do processo de build.
CI tem tempo limitado; revisão de código continua necessária. Não habilitar um
servidor Vite para atender produção nem adicionar buscas com globs fornecidos pelo
usuário sem nova revisão. A classificação npm `dependencies`/`devDependencies`
sozinha não prova alcance em produção; por isso o guard verifica o artefato real.

Ao sair uma correção, atualize as dependências de origem/lock e execute os testes
e a auditoria. Remova o aceite específico de `temporaryPicomatchRisk` e os casos
de teste correspondentes quando o relatório não listar mais o advisory. O teste
de validade impede renovação silenciosa: se ainda não houver correção na data,
é necessária uma nova análise documentada; não estender automaticamente o prazo.

Os testes do guard cobrem expiração, versão nova, advisory novo, falha de consulta,
lock divergente, relatório antigo e entrada direta/transitiva da biblioteca no
runtime. Essa exceção não muda a proteção da branch nem dispensa o check frontend.

## Revisão de 17/11/2026 — Android e Swift

A revisão adicional examinou os manifests dos plugins Capacitor, os scripts
Gradle, os pacotes Swift e as versões declaradas pelos módulos nativos. Foram
consultadas 41 versões na API pública OSV (37 Maven, incluindo ferramentas e
testes, e quatro SwiftURL). Depois das correções abaixo, as 41 respostas não
listaram advisories para essas versões. Esse resultado se limita ao que estava
publicado/indexado na consulta; não certifica ausência de vulnerabilidades.
Referência do formato: [OSV querybatch](https://google.github.io/osv.dev/post-v1-querybatch/).

| Componente | Resultado e mudança |
| --- | --- |
| Gradle Wrapper | `8.14.3` → `8.14.7`, com SHA-256 oficial fixado; permanece na linha 8.14 |
| Kotlin Gradle Plugin | `2.2.20` → `2.4.20`, pela propriedade compartilhada `kotlin_version` |
| JSON-java nos testes JVM do Capacitor | `20250517` → `20260719`, somente configurações cujo nome contém `test`; nenhuma inclusão desse JAR no runtime do APK |
| Capacitor Android/iOS/Swift | `8.6.2`, já fora das faixas do advisory de proxy HTTP interno |
| Câmera | Plugin npm `8.2.6`, biblioteca Android `ioncamera-android:1.0.2`; provider restrito ao cache privado do app e armazenamento legado desativado |

O Gradle `8.14.7` corrige os advisories
[injeção em catálogos de versões](https://github.com/gradle/gradle/security/advisories/GHSA-3cfg-jpcr-gfp3),
[registro do daemon](https://github.com/gradle/gradle/security/advisories/GHSA-gqrr-4j89-5267) e
[porta reutilizada por outro processo](https://github.com/gradle/gradle/security/advisories/GHSA-pcp8-98xm-c6pr),
além dos ajustes anteriores da mesma linha. A integridade da distribuição usa
o [hash publicado pelo Gradle](https://services.gradle.org/distributions/gradle-8.14.7-all.zip.sha256).
Esses riscos são do ambiente de compilação, não de uma biblioteca embarcada no APK.

A atualização do Kotlin atende ao
[GHSA-r937-wjx7-w2jp](https://github.com/advisories/GHSA-r937-wjx7-w2jp), relativo
à desserialização do cache de compilação. Foi escolhida a
[versão estável 2.4.20](https://github.com/JetBrains/kotlin/releases/tag/v2.4.20).
A [matriz oficial de compatibilidade](https://kotlinlang.org/docs/gradle-configure-project.html)
inclui o Gradle 8.14.7 e o Android Gradle Plugin 8.13.0 usados pelo projeto.
A correção de JSON-java atende ao
[GHSA-ghc9-756g-vrcv](https://github.com/advisories/GHSA-ghc9-756g-vrcv), presente
na declaração `testImplementation` do Capacitor. A substituição fica restrita aos
testes; não troca a implementação `org.json` fornecida pelo Android.

O [advisory crítico do Capacitor](https://github.com/ionic-team/capacitor/security/advisories/GHSA-rvm3-566m-v7fv)
foi comparado com as versões npm e Swift do projeto: `8.6.2` está fora das faixas
afetadas. Essa constatação não elimina a necessidade de atualizar o app instalado
quando houver novas correções nativas.

`verifyNativeSecurityVersions`, executado pelo workflow mobile, confere a versão
real do wrapper, os artefatos de Kotlin resolvidos nos plugins de scanner, câmera
e filesystem e JSON-java no classpath de testes JVM do Capacitor. Falha se os
overrides não forem aplicados. `mobile:check` também confere os pins e as
restrições dos providers. Testes e compilação do Android continuam obrigatórios.

Limites da revisão:

- As 41 consultas cobrem declarações conhecidas, não todo o grafo transitivo
  resolvido por Gradle. O relatório de dependências do build deve ser conferido
  para cada publicação; a revisão não é um scanner Maven diário instalado.
- Não havia `Package.resolved` local para o iOS. Foram examinados o pin exato de
  Capacitor `8.6.2`, `ion-ios-filesystem` `2.0.1`, o mínimo `2.0.0` da faixa
  `2.0.x` da câmera e o mínimo `3.0.0` da faixa `3.x` do scanner. O grafo Swift
  efetivamente resolvido e o binário assinado ainda precisam de validação antes
  da distribuição iOS; não se afirma que esses mínimos sejam as versões finais.
- Android System WebView, APIs do sistema e atualizações de segurança do aparelho
  têm ciclo próprio. A análise dos pacotes do ERP não substitui essas atualizações.
- Foram preservadas as versões das demais bibliotecas AndroidX, Firebase, ZXing,
  ML Kit e ION quando a consulta das versões declaradas não indicou advisory.
  Não foi realizado upgrade amplo por existir uma versão mais recente.
