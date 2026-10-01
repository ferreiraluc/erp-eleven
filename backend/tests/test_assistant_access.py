"""A newly restricted user must not recover former financial access from memory."""
import json
from datetime import timedelta

from test_address_manager import env
from test_assistant import incoming, setup
from app.database import Base
from app.models import Usuario
from app.models.access import AuditEvent, now
from app.models.assistant import AssistantNote
from app.services import assistant_agent, assistant_channels
from app.services.assistant_tools import search_memory


def test_restricted_bot_excludes_pre_restriction_history_and_team_notes(env, monkeypatch):
    factory,_,uid,_=env
    captured=[]
    monkeypatch.setattr(assistant_agent,'complete',lambda messages: captured.extend(messages) or {'content':'Olá, em que posso ajudar?'})
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[AuditEvent.__table__])
        user=db.get(Usuario,uid);user.sales_scope='own';user.sales_seller='Junior'
        cutoff=now()-timedelta(minutes=2)
        old=incoming(db,uid,'Memória antiga da loja',channel='telegram');old.status='done';old.created_at=cutoff-timedelta(minutes=1)
        old.response='TOTAL_PRIVADO_ANTIGO'
        recent=incoming(db,uid,'Meu relatório pessoal',channel='telegram');recent.status='done';recent.created_at=cutoff+timedelta(minutes=1)
        recent.response='RESULTADO_PESSOAL_ATUAL'
        db.add(AuditEvent(action='access_changed',module='usuarios',entity='usuarios',entity_id=str(uid),occurred_at=cutoff))
        db.add(AssistantNote(source_message_id=old.id,user_id=uid,kind='geral',content='Memória TOTAL_PRIVADO_ANTIGO',status='shared',confirmed_at=old.created_at))
        db.add(AssistantNote(source_message_id=recent.id,user_id=uid,kind='geral',content='Memória RESULTADO_PESSOAL_ATUAL',status='shared',confirmed_at=recent.created_at))
        other=Usuario(nome='Outro',email='other@example.com',senha_hash='unused');db.add(other);db.flush()
        other_msg=incoming(db,other.id,'Memória da equipe',channel='telegram')
        db.add(AssistantNote(source_message_id=other_msg.id,user_id=other.id,kind='geral',content='Memória OUTRO_FUNCIONARIO',status='shared',confirmed_at=now()))
        db.flush()
        notes=search_memory(db,'Memória',user)
        assert len(notes)==1 and 'RESULTADO_PESSOAL_ATUAL' in notes[0]['conteudo']
        message=incoming(db,uid,'Olá, pode ajudar?',channel='telegram')
        assistant_agent.respond(db,message,assistant_channels.authorized_identity(db,'telegram','123'))
        payload=json.dumps(captured)
        assert 'TOTAL_PRIVADO_ANTIGO' not in payload and 'OUTRO_FUNCIONARIO' not in payload
        assert 'RESULTADO_PESSOAL_ATUAL' in payload
        user.sales_scope='all'
        assert len(search_memory(db,'Memória',user))==3
