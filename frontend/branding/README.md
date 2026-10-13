# Ícone ELEVEN Midnight

Matriz: `eleven-midnight-master.png`, editada com a ferramenta integrada **image_gen**
em 13/10/2026. Palavra **ELEVEN** em caixa alta, com proporções naturais, peso
intermediário e pequenas serifas, dourada sobre azul-marinho petróleo com brilho
discreto. A versão v3 equilibra a elegância da v1 com a presença da v2, reduzindo
a altura excessiva e a condensação das letras. Cores e iluminação são preservadas.
Não exige chamada de IA no ERP: os arquivos derivados são servidos estaticamente.

`frontend/public/icons/eleven-midnight-v3-*.png` contém as reduções em 16, 32, 48,
152, 167, 180, 192 e 512px. `public/favicon.ico` reúne os PNGs de 16/32/48px.
O HTML declara favicon, Apple touch icons e manifesto; o manifesto declara ícones
192/512px com `purpose: any`. A arte não é anunciada como `maskable`, pois o lettering
se aproxima das bordas: o navegador escolhe a apresentação adequada ao dispositivo.
Os PNGs v1/v2 permanecem disponíveis para referências antigas em cache.

Para regenerar os tamanhos em macOS, a partir de `frontend/`:

```sh
for icon_size in 16 32 48 152 167 180 192 512; do
  sips -z "$icon_size" "$icon_size" branding/eleven-midnight-master.png \
    --out "public/icons/eleven-midnight-v3-${icon_size}.png"
done
```

Em outra plataforma, exporte a matriz quadrada nas mesmas dimensões sem recorte nem
transparência e regenere o ICO de múltiplos tamanhos. Ao trocar a arte, versione os
nomes e referências no HTML/manifesto para reduzir o reaproveitamento do ícone antigo.

## Prompt da edição v3

Use case: text-localization
Asset type: finished square app icon for the Eleven fashion store, used at 76–100px on iPad home screen.
Input image: edit target. Preserve the glossy midnight petroleum navy background and centered champagne gold wordmark composition.
Primary request: replace the excessively heavy condensed lettering with a balanced, elegant medium-bold wordmark. Exact text: "ELEVEN", all six letters uppercase, on a single horizontal line.
Typography: naturally proportioned normal-width uppercase letters, modest square shoulders and subtly flared terminals, an elegant contemporary fashion wordmark halfway between refined serif lettering and geometric bold sans-serif. Medium-bold weight, not black or extra-bold. Visibly LOWER cap height than the reference and slightly wider individual letter proportions. No tall condensed letters, no vertical stretching, no compressed spacing. Comfortable even spacing. Entire word about 78% canvas width and about 17% canvas height, precisely centered. Legible at actual home screen size.
Gold finish: soft warm champagne metallic gold, refined shallow bevel and subtle highlights, much less chunky extrusion and dark shadow than the reference. Maintain clear contrast and open spaces within the E letters.
Keep the navy background, blue glossy upper-left reflection, full-bleed opaque square, same palette. No other text, no logo symbol, no device, no presentation mockup, no rounded exterior corners, no border or watermark. Deliver the icon itself.
