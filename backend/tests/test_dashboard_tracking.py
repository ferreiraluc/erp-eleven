"""Dashboard preview is bounded without hiding shipments from the full listing."""
from datetime import datetime, timedelta

from test_customer_links import logistics, setup
from app.models import Rastreamento
from app.models.rastreamento import RastreamentoStatus as Status


def test_dashboard_limits_after_excluding_delivered_and_archived(logistics):
    factory, client, _ = logistics
    start = datetime(2026, 10, 1, 12)
    with factory() as db:
        # Delivered records are newer than every pending shipment, including their updates.
        for i in range(14):
            db.add(Rastreamento(codigo_rastreio=f'DELIVERED-{i}', status=Status.ENTREGUE,
                                created_at=start + timedelta(days=5, minutes=i)))
        for i, status in enumerate([Status.PENDENTE, Status.EM_TRANSITO, Status.NAO_ENCONTRADO, Status.ERRO, Status.EM_TRANSITO]):
            db.add(Rastreamento(codigo_rastreio=f'PENDING-{i}', status=status,
                                created_at=start + timedelta(minutes=i),
                                updated_at=start + timedelta(days=10-i)))
        db.add(Rastreamento(codigo_rastreio='ARCHIVED', status=Status.PENDENTE, ativo=False,
                            created_at=start + timedelta(days=20)))
        db.commit()
    response = client.get('/api/rastreamento/resumo/dashboard')
    assert response.status_code == 200
    summary = response.json()
    assert [r['codigo_rastreio'] for r in summary['rastreamentos_recentes']] == ['PENDING-4', 'PENDING-3', 'PENDING-2']
    assert summary['total_rastreamentos'] == 19
    assert summary['entregues'] == 14
    assert summary['em_transito'] == 2
    assert summary['pendentes'] == 1
    assert summary['com_erro'] == 2
    full_list = client.get('/api/rastreamento/').json()
    assert len(full_list) == 19
    assert sum(r['status'] == 'ENTREGUE' for r in full_list) == 14


def test_dashboard_empty_pending_list_keeps_delivered_totals(logistics):
    factory, client, _ = logistics
    with factory() as db:
        db.add(Rastreamento(codigo_rastreio='DELIVERED', status=Status.ENTREGUE))
        db.commit()
    summary = client.get('/api/rastreamento/resumo/dashboard').json()
    assert summary['rastreamentos_recentes'] == []
    assert summary['total_rastreamentos'] == summary['entregues'] == 1
