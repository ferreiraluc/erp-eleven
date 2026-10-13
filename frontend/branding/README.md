# Ícone Eleven Midnight

Matriz: `eleven-midnight-master.png`, criada com a ferramenta integrada **image_gen**
em 13/10/2026. Palavra Eleven dourada sobre azul-marinho petróleo com brilho discreto.
Não exige chamada de IA no ERP: os arquivos derivados são servidos estaticamente.

`frontend/public/icons/eleven-midnight-v1-*.png` contém as reduções em 16, 32, 48,
152, 167, 180, 192 e 512px. `public/favicon.ico` reúne os PNGs de 16/32/48px.
O HTML declara favicon, Apple touch icons e manifesto; o manifesto declara ícones
192/512px com `purpose: any`. A arte não é anunciada como `maskable`, pois o lettering
se aproxima das bordas: o navegador escolhe a apresentação adequada ao dispositivo.

Para regenerar os tamanhos em macOS, a partir de `frontend/`:

```sh
for icon_size in 16 32 48 152 167 180 192 512; do
  sips -z "$icon_size" "$icon_size" branding/eleven-midnight-master.png \
    --out "public/icons/eleven-midnight-v1-${icon_size}.png"
done
```

Em outra plataforma, exporte a matriz quadrada nas mesmas dimensões sem recorte nem
transparência e regenere o ICO de múltiplos tamanhos. Ao trocar a arte, versione os
nomes e referências no HTML/manifesto para reduzir o reaproveitamento do ícone antigo.

## Prompt da matriz

Create a polished premium app icon for the internal ERP of a fashion store called Eleven. Square 1024x1024 opaque full-bleed artwork, no outer mockup and no device. Exact centered text only: "Eleven" (capital E, lowercase leven), one single horizontal word. Large confident elegant modern luxury serif wordmark with moderately thick strokes (not fragile hairlines), occupying about 76% of the image width, within the central 70% circular safe area for Android masking. Warm champagne gold metallic lettering with a subtle bevel and refined light-catching golden highlights, extremely sharp perfectly legible typography. Background is very deep midnight petroleum navy blue, reminiscent of midnight anodized aluminum, around #101F2C and #172D3B, with a sophisticated smooth glossy light reflection along the upper left corner and gentle gradient toward almost black navy lower right. Tasteful restrained polish, not sparkly. Background reaches all four square corners; the operating system supplies rounded corners. Clean expensive understated fashion identity, strong gold/navy contrast at phone home-screen size. No other text, no ERP label, no decorative symbol, no border, no dots, no stars, no watermark, no perspective. Flat front-facing icon asset.
