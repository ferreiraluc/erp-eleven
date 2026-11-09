"""Explicit sale revisions retain the same safe facts as their ORM audit rows."""
import json
import uuid

import pytest

from app.models.access import AuditEvent
from app.models.pdv import PdvSale
from app.models.usuario import Usuario
from test_pdv_unknown_stock import pdv_app  # noqa: F401
from test_pdv_management import sold, command, edit_body, review


@pytest.mark.parametrize('operation', ['edit', 'return', 'cancel', 'delete', 'legacy_cancel'])
def test_sale_revision_audit_keeps_actual_seller_total_and_status_without_private_fields(pdv_app, operation):
    factory, client, _ = pdv_app
    factory.configure(info={'audit_enabled': True})
    _, sid, data = sold(pdv_app)
    with factory() as db:
        seller = Usuario(nome='Sol', email='sol-audit@example.test', senha_hash='unused')
        db.add(seller)
        db.flush()
        seller_id = seller.id
        sale = db.get(PdvSale, uuid.UUID(sid))
        sale.vendedor_id = seller_id
        sale.cliente_nome = 'PRIVATE CUSTOMER'
        sale.notas = 'PRIVATE NOTE'
        db.commit()
    data = client.get('/api/pdv/management/' + sid).json()
    if operation == 'edit':
        edit = edit_body(data)
        edit['items'][0]['quantity'] = 3
        edit['payments'][0].update(amount_original=300, amount_gs=300)
        body = command(operation, edit=edit)
    elif operation == 'return':
        body = command(operation, lines=[{'line_id': data['items'][0]['id'], 'quantity': 1, 'restock': True}])
    else:
        body = command(operation) if operation != 'legacy_cancel' else None
    if body:
        request, _ = review(client, sid, body)
        response = client.post(f'/api/pdv/management/{sid}/commit', json=request)
        assert response.status_code == 200, response.text
        replay = client.post(f'/api/pdv/management/{sid}/commit', json=request)
        assert replay.status_code == 200 and replay.json()['replayed']
    else:
        response = client.post(f'/api/pdv/sales/{sid}/cancel')
        assert response.status_code == 200, response.text

    action = 'pdv_cancel' if operation == 'legacy_cancel' else 'pdv_' + operation
    with factory() as db:
        audit = db.query(AuditEvent).filter_by(entity='pdv_sales', entity_id=sid, action=action).one()
        assert audit.actor_name == 'Lucas sintético'
        assert audit.changes['_context'] == {'sale_id': sid, 'sale': {
            'seller_id': str(seller_id), 'seller_name': 'Sol',
            'total_gs': '300.00' if operation == 'edit' else '200.00',
            'usd_rate_gs': '6000.0000',
            'status': 'completed' if operation == 'edit' else 'partially_refunded' if operation == 'return' else 'cancelled',
        }}
        assert audit.changes['refund_gs'] == ('0' if operation == 'edit' else '100.00' if operation == 'return' else '200.00')
        assert 'PRIVATE' not in json.dumps(audit.changes)
