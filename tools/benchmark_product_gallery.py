"""Disposable local PostgreSQL benchmark; never uses the configured ERP database.

PYTHONPATH=backend DATABASE_URL=sqlite:// backend/venv/bin/python tools/benchmark_product_gallery.py
"""
import argparse
import base64
import gc
import gzip
import io
import json
import os
import random
import statistics
import time
import tracemalloc
import uuid
from pathlib import Path

os.environ['DATABASE_URL'] = 'sqlite://'
from PIL import Image
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import inventory
from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item
from app.schemas.product_gallery import GalleryInput


def photos():
    result = []
    for index in range(5):
        noise = Image.frombytes('L', (1200, 1200), random.Random(42 + index).randbytes(1200 * 1200)).convert('RGB')
        mix = .14
        while True:
            with Image.blend(Image.new('RGB', noise.size, (210 - index * 20, 180, 160)), noise, mix) as image:
                output = io.BytesIO(); image.save(output, format='JPEG', quality=85)
            if len(output.getvalue()) < 250000: break
            mix *= .9
        result.append('data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode())
    GalleryInput(additional_images=result[1:])
    return result


def measure(operation):
    for _ in range(5): operation()
    times = []
    for _ in range(40):
        start = time.perf_counter(); response = operation(); times.append((time.perf_counter() - start) * 1000)
        assert response.status_code in (200, 201), response.text[:200]
    size = len(response.content)
    compressed = len(gzip.compress(response.content))
    del response
    gc.collect(); tracemalloc.start()
    response = operation()
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return dict(median_ms=round(statistics.median(times), 3), p95_ms=round(sorted(times)[37], 3),
                response_bytes=size, gzip_bytes=compressed, python_peak_mib=round(peak / 1048576, 3))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', default='postgresql://127.0.0.1:59216/gallery_test')
    parser.add_argument('--fixtures', type=Path)
    args = parser.parse_args()
    if make_url(args.database_url).host not in ('127.0.0.1', 'localhost'):
        raise SystemExit('Use only a disposable local PostgreSQL database.')
    schema = 'gallery_bench_' + uuid.uuid4().hex
    root = sa.create_engine(args.database_url)
    with root.begin() as connection: connection.exec_driver_sql(f'CREATE SCHEMA {schema}')
    engine = sa.create_engine(args.database_url, connect_args={'options': f'-c search_path={schema},public'})
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        images = photos()
        if args.fixtures: args.fixtures.write_text(json.dumps(images))
        user = Usuario(id=uuid.uuid4(), nome='Fixture', email='fixture@example.test', senha_hash='test', role=UsuarioRole.GERENTE)
        ids = [uuid.UUID(int=n + 1) for n in range(100)]
        with factory() as db:
            db.add(user); db.commit()
            for index, id in enumerate(ids):
                db.add(Item(id=id, name=f'Camiseta teste {index:03}', sku_internal=f'TEST-{index}',
                            image_data=images[0], stock_loja=1, stock_deposito=0, current_stock=1))
            db.commit()
        app = FastAPI(); app.include_router(inventory.router, prefix='/api/inventory')
        def session():
            with factory() as db: yield db
        def actor():
            return type('Actor', (), {'id': user.id, 'role': UsuarioRole.GERENTE})()
        # Capture the user before its originating session is closed/expired.
        with factory() as db: user = db.query(Usuario).one()
        app.dependency_overrides[get_db] = session
        app.dependency_overrides[get_current_active_user] = actor
        client = TestClient(app)
        results = {}
        for count in (1, 5):
            with factory() as db:
                db.query(Item).update({Item.additional_images: images[1:] if count == 5 else None, Item.updated_at: Item.updated_at}); db.commit()
            base = '/api/inventory/items'
            photo_payload = {'additional_images': images[1:] if count == 5 else []}
            results[str(count)] = {
                'list_50': measure(lambda: client.get(base, params={'include_images': False, 'page_size': 50})),
                'detail': measure(lambda: client.get(f'{base}/{ids[0]}')),
                'gallery': measure(lambda: client.get(f'{base}/{ids[0]}/photos')),
                'save_gallery': measure(lambda: client.put(f'{base}/{ids[0]}', json=photo_payload)),
            }
        print(json.dumps({'environment': 'local PostgreSQL, TestClient, 100 synthetic products; 40 warm requests per case',
            'encoded_photo_bytes': [len(image) for image in images], 'photo_dimensions': [1200,1200], 'results': results}, indent=2))
    finally:
        engine.dispose()
        with root.begin() as connection: connection.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        root.dispose()


if __name__ == '__main__': main()
