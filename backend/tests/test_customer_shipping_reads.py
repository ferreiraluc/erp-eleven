"""Shipping history follows explicit PDV links and confirmed aliases without writes."""
import uuid

from sqlalchemy import event, select

from test_assistant import setup
from test_customer_links import logistics, customer
from test_customer_activity import activity_env, address, print_job, page
from test_customer_purchases import account
from app.database import Base
from app.models.address_book import FreightOrder
from app.services.customer_shipping_links import address_owners


def freight(db, recipient, user_id):
    row = FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=recipient.id,
        environment='production', state='released', rates=[], tracking='SYNTHETIC-SHIPPING',
        payload={'to': {'name': 'Snapshot original', 'city': 'Cidade QA'}})
    db.add(row); db.flush()
    return row


def history(client, customer_id):
    response = client.get(f'/api/clientes/{customer_id}/historico-enderecos')
    assert response.status_code == 200, response.text
    return response.json()


def test_pdv_address_history_resolves_customer_and_address_aliases_once(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[FreightOrder.__table__])
        principal = customer(db, 'Principal QA')
        middle = customer(db, 'Nome anterior QA'); middle.merged_into_id = principal.id; middle.ativo = False
        old = customer(db, 'Nome antigo QA'); old.merged_into_id = middle.id; old.ativo = False
        buyer = account(db, old, ativo=False)
        root = address(db, None, user_id); root.pdv_cliente_id = buyer.id
        previous = address(db, None, user_id, parent=root)
        oldest = address(db, None, user_id, parent=previous)
        direct = address(db, middle, user_id)
        compatible = address(db, principal, user_id); compatible.pdv_cliente_id = buyer.id
        for index, recipient in enumerate((root, previous, oldest, direct, compatible), 1):
            print_job(db, recipient, user_id, day=index)
        freight(db, oldest, user_id)
        principal_id, alias_id, root_id, buyer_id = principal.id, old.id, root.id, buyer.id
        root_ids = {str(row.id) for row in (root, direct, compatible)}
        db.commit()
        owners = address_owners([principal_id])
        rows = db.execute(select(owners)).all()
        assert len(rows) == 5 and {row.customer_id for row in rows} == {principal_id}
    result = history(client, principal_id)
    assert result['total'] == 6
    assert result['summary']['prints'] == 5 and result['summary']['labels'] == 1
    assert {row['id'] for row in result['addresses']} == root_ids
    assert history(client, alias_id) == result
    listed = page(client, sort='ultima_impressao')['items']
    assert len(listed) == 1 and listed[0]['id'] == str(principal_id)
    assert listed[0]['activity']['print_count'] == 5
    with factory() as db:
        assert db.get(type(root), root_id).cliente_id is None
        assert db.get(type(buyer), buyer_id).cadastro_cliente_id == alias_id


def test_conflicting_address_owners_and_name_only_accounts_are_unattributed(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[FreightOrder.__table__])
        first = customer(db, 'Pessoa homônima QA')
        second = customer(db, 'Pessoa homônima QA')
        buyer = account(db, second)
        conflicting = address(db, first, user_id); conflicting.pdv_cliente_id = buyer.id
        historical = address(db, first, user_id, parent=conflicting)
        unknown = address(db, None, user_id)
        unknown.pdv_cliente_id = account(db, nome=first.nome).id
        for recipient in (conflicting, historical, unknown):
            print_job(db, recipient, user_id)
            freight(db, recipient, user_id)
        ids = (first.id, second.id)
        db.commit()
        owners = address_owners()
        assert not db.execute(select(owners)).all()
    for customer_id in ids:
        result = history(client, customer_id)
        assert result['total'] == 0 and not result['addresses']
    assert all(row['activity']['print_count'] == 0 for row in page(client)['items'])


def test_history_queries_remain_batched_and_read_only_with_many_address_aliases(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[FreightOrder.__table__])
        principal = customer(db, 'Consulta QA'); buyer = account(db, principal)
        for _ in range(12):
            root = address(db, None, user_id); root.pdv_cliente_id = buyer.id
            previous = address(db, None, user_id, parent=root)
            print_job(db, previous, user_id)
        customer_id = principal.id
        db.commit(); engine = db.bind
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        result = history(client, customer_id)
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert result['total'] == 12 and len(result['addresses']) == 12
    assert len(statements) <= 7  # Includes authentication; independent of address count/depth.
    assert all(statement.lstrip().split()[0].upper() in {'SELECT', 'WITH'} for statement in statements)
    assert all('saved_addresses.data' not in statement for statement in statements)


def test_invalid_customer_alias_cycles_never_choose_a_shipping_owner(activity_env):
    factory, _, user_id = activity_env
    with factory() as db:
        one, two = customer(db, 'Alias um QA'), customer(db, 'Alias dois QA')
        one.merged_into_id, two.merged_into_id = two.id, one.id
        one.ativo = two.ativo = False
        root = address(db, one, user_id)
        root.pdv_cliente_id = account(db, two).id
        db.flush()
        owners = address_owners()
        assert not db.execute(select(owners)).all()
