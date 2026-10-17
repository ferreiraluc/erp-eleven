# Galeria de produtos — medição antes da publicação

Medição local em 16/10/2026. Não representa uma garantia de latência ou RAM no
Render, iPhone ou Android. Não houve consulta a produtos reais nem chamadas de IA.

## Método

`tools/benchmark_product_gallery.py` cria e remove um schema PostgreSQL local
isolado, com 100 produtos sintéticos. Compara uma foto com cinco fotos; a foto
principal e os outros dados dos produtos são os mesmos. As imagens são JPEG
1200×1200, com aproximadamente 230 KB cada (306 KB como data URL/base64).
Cada rota tem cinco aquecimentos e 40 requisições via FastAPI TestClient.
Os tempos abaixo foram obtidos em uma segunda execução, sem a suíte de testes
rodando em paralelo. O pico Python é uma chamada separada com `tracemalloc`.

| Operação | Mediana: 1 foto | Mediana: 5 fotos | P95: 1 → 5 | Pico Python: 1 → 5 |
| --- | ---: | ---: | ---: | ---: |
| Listagem de 50 produtos | 2,651 ms | 2,642 ms | 2,891 → 3,035 ms | 0,380 → 0,380 MiB |
| Ficha/foto principal | 1,788 ms | 1,556 ms | 2,109 → 1,708 ms | 0,953 → 0,954 MiB |
| Consulta da galeria adicional | 1,298 ms | 5,043 ms | 1,905 → 5,371 ms | 0,081 → 3,584 MiB |
| Atualizar a galeria | 2,619 ms | 23,673 ms | 3,138 → 27,338 ms | 0,969 → 9,754 MiB |

Variações negativas pequenas são ruído de medição, não otimização causada por
guardar mais fotos. A listagem retornou exatamente **30.303 bytes** em ambos os
cenários, sem fotos adicionais, e não materializou a coluna da galeria.
O pico Python inclui a instrumentação/cliente local, buffers e serialização. Não
mede RSS integral do servidor, buffers do PostgreSQL, memória nativa ou GPU.
São alocações transitórias por operação, não uma reserva permanente por produto.

## Navegador e transferência

No Chromium local, em viewport de 408×850, a preparação sequencial de miniaturas
teve mediana de **1 ms com uma foto e 4 ms com cinco** (15 rodadas, imagens já
disponíveis em memória). Não inclui download nem a compressão da foto da câmera.
A interface usa miniaturas de 128 px na faixa e uma foto ampliada por vez.

As quatro fotos extras somaram **1.227.083 bytes** na resposta JSON; comprimidas
com gzip no ensaio, 902.767 bytes. Não se presume gzip habilitado em produção.
Só a transferência de 1,23 MB exige aproximadamente **982 ms em 10 Mbps**, ou
196 ms em 50 Mbps, além de latência/rede, API e renderização. Isso acontece ao
abrir galeria/editor, não ao percorrer a listagem.

Quatro miniaturas RGBA de 128×128 representam **0,25 MiB** de pixels adicionais;
quatro fotos completas de 1200×1200 representariam **21,97 MiB**. São cálculos de
buffers, não medições da RAM do celular. O navegador pode reter imagens decodificadas
em seu próprio cache. Strings base64, canvas, foto original da câmera e buffers
temporários também consomem memória. Não é possível prometer um valor único de
RAM para todos os aparelhos sem medir neles. O processamento sequencial evita
decodificar cinco arquivos grandes de câmera ao mesmo tempo.

## Armazenamento e limites

Quatro adicionais no limite do contrato ocupam até cerca de **1,36 MB por produto**
em JSON/base64, antes de compressão interna, índices, WAL e backups do PostgreSQL.
Mil produtos preenchidos com cinco fotos podem acrescentar até aproximadamente
**1,36 GB** de conteúdo lógico adicional. Grades copiam as fotos para cada variante;
esta versão não deduplica mídias entre produtos nem contrata armazenamento externo.
Não há uso extra de IA ao adicionar fotos; operações explícitas de IA preservam
seu custo e confirmação existentes.

## Reproduzir

Use PostgreSQL descartável local e as dependências já instaladas do backend:

```sh
PYTHONPATH=backend DATABASE_URL=sqlite:// backend/venv/bin/python \
  tools/benchmark_product_gallery.py \
  --database-url postgresql://127.0.0.1:59216/gallery_test
```

O script rejeita hosts remotos e remove apenas o schema aleatório que criou.
Não usar `backend/.env`/banco de produção como origem dos dados.
