"""Shortened recipient names keep shipment filters and identity safeguards."""
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_assistant_queries import shipment
from app.database import Base
from app.models import Cliente, Pedido, Rastreamento, Usuario, Vendedor, PdvCliente, PdvSale
from app.services.assistant_queries import ShipmentArgs, query_shipments
from app.services.assistant_tracking import CustomerTrackingArgs, customer_tracking, customer_tracking_reply


@pytest.fixture(params=['sqlite', 'postgres'])
def tracking_db(request):
    if request.param == 'postgres':
        engine, schema = request.getfixturevalue('pg')
        isolated = sa.create_engine(engine.url, connect_args={
            'options': f'-csearch_path={schema} -cstatement_timeout=5000'})
    else:
        isolated = sa.create_engine('sqlite://')
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, PdvCliente, PdvSale, Pedido, Rastreamento,
        )])
        with sessionmaker(bind=isolated, autoflush=False)() as db:
            yield db
    finally:
        isolated.dispose()


@pytest.mark.parametrize('term,name', [
    ('Davi Muniz', 'Davi Almeida Muniz'),
    ('muniz davi', 'Davi Almeida Muniz'),
    ('  DAVI   MUNIZ ', 'Davi Almeida Muniz'),
    ('Joao Silva', 'JOÃO DE ÁVILA SILVA'),
    ('joão sílva', 'Joao de Avila Silva'),
])
def test_shortened_names_ignore_order_case_accents_and_extra_middle_names(tracking_db, term, name):
    shipment(tracking_db, 'QA-CURRENT', name=name)
    result = query_shipments(tracking_db, ShipmentArgs(termo=term))
    assert result['total'] == 1
    assert result['resultados'][0]['cliente'] == name
    assert result['recomendado']['codigo'] == 'QA-CURRENT'


def test_all_name_terms_must_match_one_person_in_one_field(tracking_db):
    db = tracking_db
    buyer = Cliente(nome='Davi Almeida Silva')
    db.add(buyer); db.flush()
    shipment(db, 'QA-SPLIT', name='Pedro Rocha Muniz', cliente_id=buyer.id)
    shipment(db, 'QA-FIRST', name='Davi Souza')
    shipment(db, 'QA-LAST', name='Claudio Muniz')
    assert query_shipments(db, ShipmentArgs(termo='Davi Muniz'))['total'] == 0
    shipment(db, 'QA-MATCH', name='Davi Almeida Muniz')
    result = query_shipments(db, ShipmentArgs(termo='Davi Muniz'))
    assert [row['codigo'] for row in result['resultados']] == ['QA-MATCH']


def test_both_confirmed_customer_and_historical_recipient_are_searchable(tracking_db):
    db = tracking_db
    buyer = Cliente(nome='Davi Almeida Muniz')
    db.add(buyer); db.flush()
    shipment(db, 'QA-LINKED', name='Marina de Souza Ramos', cliente_id=buyer.id)
    for term in ('Davi Muniz', 'Marina Ramos'):
        result = query_shipments(db, ShipmentArgs(termo=term))
        assert [row['codigo'] for row in result['resultados']] == ['QA-LINKED']
        assert result['resultados'][0]['cliente'] == buyer.nome


def test_homonyms_outside_first_page_still_require_identification(tracking_db):
    db = tracking_db
    shipment(db, 'QA-NEW', name='Davi Almeida Muniz', day=date(2026, 9, 20))
    shipment(db, 'QA-OLD', name='Davi Rocha Muniz', day=date(2026, 9, 1))
    result = query_shipments(db, ShipmentArgs(termo='Davi Muniz', limite=1, ordem='recentes'))
    assert result['total'] == 2 and result['tem_mais']
    assert result['clientes_distintos'] and result['recomendado'] is None
    assert len(result['resultados']) == 1
    reply = customer_tracking_reply(customer_tracking(db, CustomerTrackingArgs(termo='Davi Muniz')))
    assert 'Qual deles?' in reply and 'Davi Almeida Muniz' in reply and 'Davi Rocha Muniz' in reply


def test_shortened_name_keeps_status_dates_and_pagination_in_sql(tracking_db):
    db = tracking_db
    for number, status, day in (
        (1, 'EM_TRANSITO', 10), (2, 'EM_TRANSITO', 11),
        (3, 'EM_TRANSITO', 12), (4, 'ENTREGUE', 12),
    ):
        shipment(db, f'QA-{number}', name='Davi Almeida Muniz', status=status, day=date(2026, 9, day))
    result = query_shipments(db, ShipmentArgs(termo='Davi Muniz', situacao='EM_TRANSITO',
        data_inicio=date(2026, 9, 11), data_fim=date(2026, 9, 12), limite=1, pagina=2))
    assert result['total'] == 2 and not result['tem_mais']
    assert result['por_status'] == {'EM_TRANSITO': 2}
    assert [row['codigo'] for row in result['resultados']] == ['QA-2']


def test_pending_fallback_returns_current_codes_and_excludes_delivered(tracking_db):
    db = tracking_db
    shipment(db, 'QA-PENDING', name='Davi Almeida Muniz', status='PENDENTE')
    shipment(db, 'QA-DELIVERED', name='Davi Almeida Muniz', status='ENTREGUE')
    result = customer_tracking(db, CustomerTrackingArgs(termo='Davi Muniz'))
    reply = customer_tracking_reply(result)
    assert reply.parts[0] == 'QA-PENDING' and len(reply.parts) == 2
    assert 'Pendente' in reply.parts[1] and 'QA-DELIVERED' not in reply


def test_legacy_codes_remain_deduplicated_and_disabled_tracking_stays_hidden(tracking_db):
    db = tracking_db
    for number, code in ((1, 'QA-LEGACY'), (2, 'QA-ACTIVE'), (3, 'QA-DISABLED')):
        db.add(Pedido(numero_pedido=f'QA-PED-{number}', descricao='Synthetic order', valor_total=1,
            cliente_nome='Davi Almeida Muniz', codigo_rastreio=code, status='ENVIADO'))
    db.flush()
    shipment(db, 'QA-ACTIVE', name='Davi Almeida Muniz')
    shipment(db, 'QA-DISABLED', name='Davi Almeida Muniz', ativo=False)
    result = query_shipments(db, ShipmentArgs(termo='Davi Muniz'))
    assert result['total'] == 2
    assert {row['codigo'] for row in result['resultados']} == {'QA-LEGACY', 'QA-ACTIVE'}
    assert next(row for row in result['resultados'] if row['codigo'] == 'QA-LEGACY')['origem'] == 'pedido_sem_rastreamento'


@pytest.mark.parametrize('term', ['Davi%', 'Davi_', 'Davi\\', 'Davi Muniz%', 'Davi 102'])
def test_name_expansion_never_strips_wildcards_or_identifier_digits(tracking_db, term):
    shipment(tracking_db, 'QA102BR', name='Davi Almeida Muniz')
    assert query_shipments(tracking_db, ShipmentArgs(termo=term))['total'] == 0


def test_codes_orders_phones_and_special_characters_keep_literal_matching(tracking_db):
    db = tracking_db
    order = Pedido(numero_pedido='QA-ORDER-102', descricao='Synthetic order', valor_total=1,
        cliente_nome='Davi Almeida Muniz', cliente_telefone='+551100001020', codigo_rastreio='QA102BR')
    db.add(order); db.flush()
    shipment(db, 'QA102BR', name='Davi Almeida Muniz', pedido_id=order.id)
    for term in ('qa102br', 'qa-order-102', '+551100001020'):
        result = query_shipments(db, ShipmentArgs(termo=term))
        assert [row['codigo'] for row in result['resultados']] == ['QA102BR']
    assert query_shipments(db, ShipmentArgs(termo='QA 102'))['total'] == 0
    shipment(db, 'QA-LITERAL', name='Cliente 50%_\\ Original')
    assert [row['codigo'] for row in query_shipments(db, ShipmentArgs(termo='50%_\\'))['resultados']] == ['QA-LITERAL']


@pytest.mark.parametrize('term,name', [
    ('Murilo', 'Murillo Almeida'), ('Murillo', 'Murilo Almeida'),
    ('Murilo Muniz', 'Murillo de Almeida Muniz'),
    ('Debroa', 'Débora Silva'), ('Munilo', 'Murilo Silva'),
])
def test_typo_fallback_returns_real_registered_recipient(tracking_db, term, name):
    shipment(tracking_db, 'QA-TYPO', name=name)
    result = customer_tracking(tracking_db, CustomerTrackingArgs(termo=term))
    assert result['total'] == 1 and result['busca_aproximada']
    reply = customer_tracking_reply(result)
    assert reply.parts[0] == 'QA-TYPO'
    assert name in reply.parts[1] and 'Nome próximo à busca' in reply.parts[1]


def test_exact_pending_recipient_wins_over_similar_transit(tracking_db):
    shipment(tracking_db, 'QA-EXACT', name='Murilo Almeida', status='PENDENTE')
    shipment(tracking_db, 'QA-TYPO', name='Murillo Souza', status='EM_TRANSITO')
    result = customer_tracking(tracking_db, CustomerTrackingArgs(termo='Murilo'))
    assert [row['codigo'] for row in result['resultados']] == ['QA-EXACT']
    assert not result['busca_aproximada']


def test_exact_delivered_customer_does_not_fall_back_to_different_current_person(tracking_db):
    shipment(tracking_db, 'QA-EXACT', name='Murilo Almeida', status='ENTREGUE')
    shipment(tracking_db, 'QA-TYPO', name='Murillo Souza', status='EM_TRANSITO')
    result = customer_tracking(tracking_db, CustomerTrackingArgs(termo='Murilo'))
    assert result['total'] == 0


def test_typo_ambiguity_is_not_hidden_by_pagination(tracking_db):
    shipment(tracking_db, 'QA-A', name='Murillo Almeida')
    shipment(tracking_db, 'QA-B', name='Murilo Souza')
    result = query_shipments(tracking_db, ShipmentArgs(termo='Murilllo', limite=1))
    # Only one edit, so Murilo is too distant from Murilllo.
    assert result['total'] == 1
    result = query_shipments(tracking_db, ShipmentArgs(termo='Murilio', limite=1))
    assert result['total'] >= 2 and result['clientes_distintos']
    assert result['recomendado'] is None


@pytest.mark.parametrize('term', ['Mui', 'Murilo 102', 'Murilo%', 'Murilo Munis'])
def test_fuzzy_names_do_not_match_codes_short_fragments_or_two_typos(tracking_db, term):
    shipment(tracking_db, 'QA102BR', name='Murillo Muniz')
    assert query_shipments(tracking_db, ShipmentArgs(termo=term))['total'] == 0


def test_similar_recipients_for_one_buyer_remain_distinguishable(tracking_db):
    buyer = Cliente(nome='Cliente vinculado')
    tracking_db.add(buyer); tracking_db.flush()
    shipment(tracking_db, 'QA-A', name='Murillo Almeida', cliente_id=buyer.id)
    shipment(tracking_db, 'QA-B', name='Murilo Souza', cliente_id=buyer.id)
    result = customer_tracking(tracking_db, CustomerTrackingArgs(termo='Murilio'))
    assert result['clientes_distintos']
    reply = customer_tracking_reply(result)
    assert 'Murillo Almeida' in reply and 'Murilo Souza' in reply and 'Qual deles?' in reply
