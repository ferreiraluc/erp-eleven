# Ícone ELEVEN Midnight

Matriz: `eleven-midnight-master.png`, editada com a ferramenta integrada **image_gen**
em 13/10/2026. Palavra **ELEVEN** em caixa alta, com letras quadradas, altas e
espessas, douradas sobre azul-marinho petróleo com brilho discreto. A versão v2
substitui a tipografia serifada da v1, preservando as cores e a iluminação.
Não exige chamada de IA no ERP: os arquivos derivados são servidos estaticamente.

`frontend/public/icons/eleven-midnight-v2-*.png` contém as reduções em 16, 32, 48,
152, 167, 180, 192 e 512px. `public/favicon.ico` reúne os PNGs de 16/32/48px.
O HTML declara favicon, Apple touch icons e manifesto; o manifesto declara ícones
192/512px com `purpose: any`. A arte não é anunciada como `maskable`, pois o lettering
se aproxima das bordas: o navegador escolhe a apresentação adequada ao dispositivo.
Os PNGs v1 permanecem disponíveis para referências antigas em cache.

Para regenerar os tamanhos em macOS, a partir de `frontend/`:

```sh
for icon_size in 16 32 48 152 167 180 192 512; do
  sips -z "$icon_size" "$icon_size" branding/eleven-midnight-master.png \
    --out "public/icons/eleven-midnight-v2-${icon_size}.png"
done
```

Em outra plataforma, exporte a matriz quadrada nas mesmas dimensões sem recorte nem
transparência e regenere o ICO de múltiplos tamanhos. Ao trocar a arte, versione os
nomes e referências no HTML/manifesto para reduzir o reaproveitamento do ícone antigo.

## Prompt da edição v2

Use case: text-localization
Asset type: production square app icon and favicon for Eleven fashion store ERP.
Input image: edit target, the current gold Eleven wordmark on glossy midnight petroleum navy.
Primary request: replace ONLY the lettering. Exact text (verbatim): "ELEVEN", spelled E L E V E N, ALL SIX LETTERS UPPERCASE.
Typography: tall, very bold, thick square block sans-serif, slightly condensed, straight squared terminals, strong geometric strokes, no serifs, no lowercase, no script. The store's identity is heavy and tall uppercase lettering. Make the word visually substantial and easy to read at phone icon size. Single horizontal centered word, about 80% canvas width, equal cap height, optically balanced spacing.
Keep unchanged: deep petroleum midnight navy blue background, full-bleed opaque square, restrained glossy highlight from upper left, warm champagne metallic gold with subtle bevel. Preserve the sophisticated navy and gold palette and lighting from the edit target.
No new symbols, no ERP subtitle, no frame, no rounded outer corners, no device or mockup, no other text, no watermark. Output one front-facing finished square icon asset.
