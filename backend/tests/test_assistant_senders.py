"""Sender names resolve from live registrations without guessing identity or printing."""
import pytest

from app.database import Base
from app.models.assistant import AssistantAction, AssistantIdentity
from app.models.printing import PrintJob, PrintSender
from app.models.usuario import Usuario, UsuarioRole
from app.services.assistant_printing import AddressArgs, prepare_print
from app.services.assistant_senders import active_sender_catalog, resolve_sender, sender_candidates
from test_assistant import incoming, setup
from test_printing import device, print_env


@pytest.fixture
def senders(setup):
    factory, _, _ = setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintSender.__table__])
        db.add_all([
            PrintSender(id='debora', name='Débora de Almeida Santos', lines=['Synthetic print block']),
            PrintSender(id='mona', name='Remetente principal', lines=['Synthetic print block'],
                        data={'nome': 'Mona de Souza Oliveira'}),
            PrintSender(id='antigo', name='Pessoa desativada', lines=[], active=False),
        ])
        db.commit()
        yield db


@pytest.mark.parametrize('reference,expected', [
    ('debora', 'debora'), ('Débora', 'debora'), (' DÉBORA ', 'debora'),
    ('debora santos', 'debora'), ('Santos Debora', 'debora'),
    ('MONA', 'mona'), ('Mona Oliveira', 'mona'), ('Oliveira Mona', 'mona'),
    ('Remetente principal', 'mona'),
])
def test_known_ids_and_partial_names_find_current_senders(senders, reference, expected):
    sender, error = resolve_sender(senders, reference)
    assert error is None and sender.id == expected


def test_homonymous_names_require_choice_but_explicit_id_remains_exact(senders):
    senders.add_all([
        PrintSender(id='mona-2', name='Mona de Souza Silva', lines=[]),
        PrintSender(id='debora-2', name='Débora de Almeida Santos', lines=[]),
    ])
    senders.flush()
    sender, error = resolve_sender(senders, 'Mona Souza')
    assert sender is None and error['codigo'] == 'remetente_ambiguo'
    assert {row['id'] for row in error['candidatos']} == {'mona', 'mona-2'}
    assert resolve_sender(senders, 'mona')[0].id == 'mona'
    assert resolve_sender(senders, 'Débora de Almeida Santos')[1]['codigo'] == 'remetente_ambiguo'


def test_missing_and_inactive_are_distinguished_without_exposing_address_or_document(senders):
    senders.add(PrintSender(id='outra', name='Antigo', lines=['Private address'],
                           data={'cpf': 'private-document'}))
    senders.flush()
    sender, error = resolve_sender(senders, 'ANTIGO')
    assert sender is None and error['codigo'] == 'remetente_inativo'
    sender, error = resolve_sender(senders, 'Não cadastrado')
    assert sender is None and error['codigo'] == 'remetente_nao_encontrado'
    assert {row['id'] for row in error['remetentes_disponiveis']} == {'debora', 'mona', 'outra'}
    assert all(set(row) == {'id', 'nome'} for row in error['remetentes_disponiveis'])
    assert 'Private address' not in str(error) and 'private-document' not in str(error)
    assert 'antigo' not in {row.id for row in active_sender_catalog(senders)}


@pytest.mark.parametrize('reference', ['', 'D', 'Deb', 'Debora%', 'Mona_', 'Mona\u005c', 'Mona Pessoa', 'Mona Santos'])
def test_partial_substrings_wildcards_and_names_from_different_people_are_not_identifiers(senders, reference):
    assert not sender_candidates(senders, reference)


def test_changed_registry_is_read_again_instead_of_reusing_old_identity(senders):
    sender = resolve_sender(senders, 'Débora Santos')[0]
    sender.name = 'Débora Rocha'
    senders.commit()
    assert resolve_sender(senders, 'Débora Santos')[1]['codigo'] == 'remetente_nao_encontrado'
    assert resolve_sender(senders, 'Rocha Debora')[0].id == sender.id
    sender.active = False
    senders.commit()
    assert resolve_sender(senders, 'debora')[1]['codigo'] == 'remetente_inativo'


def test_resolution_refreshes_registry_loaded_before_a_concurrent_change(senders):
    sender = resolve_sender(senders, 'mona')[0]
    senders.query(PrintSender).filter_by(id='mona').update({'active': False}, synchronize_session=False)
    assert sender.active
    assert resolve_sender(senders, 'mona')[1]['codigo'] == 'remetente_inativo'
    assert not sender.active


def test_print_preview_uses_canonical_sender_id_preserves_confirmation_and_permissions(print_env):
    factory, client = print_env
    device(client)
    args = AddressArgs(pais='BR', nome='Cliente sintético', endereco='Rua Exemplo 123',
                       cidade='Curitiba', estado='PR', cep='80000-000', remetente='DÉBORA SANTOS')
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintSender.__table__])
        db.add(PrintSender(id='debora', name='Débora Almeida Santos', lines=['Current print block']))
        db.flush()
        user = db.query(Usuario).one()
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message = incoming(db, user.id, 'Imprima com remetente Débora Santos', channel='telegram')
        assert 'erro' in prepare_print(db, message, identity, args)
        assert db.query(AssistantAction).count() == 0
        user.role = UsuarioRole.ADMIN
        result = prepare_print(db, message, identity, args)
        assert 'confirmacao' in result and 'Débora Almeida Santos' in result['confirmacao']
        action = db.query(AssistantAction).one()
        assert action.payload['endereco']['remetente'] == 'debora'
        assert action.payload['remetente']['linhas'] == ['Current print block']
        assert db.query(PrintJob).count() == 0
        assert args.remetente == 'DÉBORA SANTOS'
        assert prepare_print(db, message, identity, args)['confirmacao'] == result['confirmacao']
        assert db.query(AssistantAction).count() == 1


def test_print_ambiguity_does_not_create_action_or_queue_job(print_env):
    factory, client = print_env
    device(client)
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintSender.__table__])
        db.add_all([PrintSender(id=f'mona-{number}', name=f'Mona Souza {number}', lines=[])
                    for number in (1, 2)])
        db.flush()
        user = db.query(Usuario).one()
        user.role = UsuarioRole.ADMIN
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message = incoming(db, user.id, 'Imprima com remetente Mona Souza', channel='telegram')
        result = prepare_print(db, message, identity, AddressArgs(pais='BR', nome='Cliente sintético',
            endereco='Rua Exemplo 123', cidade='Curitiba', estado='PR', cep='80000-000', remetente='Mona Souza'))
        assert result['codigo'] == 'remetente_ambiguo'
        assert db.query(AssistantAction).count() == db.query(PrintJob).count() == 0
