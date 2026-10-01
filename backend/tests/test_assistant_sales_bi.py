"""Bot BI reads synthetic SQLite snapshots; no provider or OneDrive requests."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder

from test_address_manager import env
from test_assistant import setup, incoming
from test_sales_bi_entries import details
from app.config import settings
from app.database import Base
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.access import AuditEvent
from app.models.sales_bi import SalesBIWorkbook, SalesBIConfig
from app.services import assistant_agent, assistant_channels
from app.services.assistant_tools import execute_tool
from app.services.assistant_sales_bi import SpreadsheetSalesArgs as Args, query_spreadsheet_sales as query, spreadsheet_sales_intent


def snapshot(junior='100', lucas='50', total='777', entries=True):
    data = {'total_usd':total, 'source_cell':'total mes!C8', 'warnings':['PRIVATE_SOURCE_WARNING'],
        'sellers': {'Junior':{'total_usd':junior, 'source_cell':'total mes!G8','currencies':{'BRL':'196'}},
                    'Lucas':{'total_usd':lucas,'source_cell':'total mes!H8','currencies':{'USD':'50'}},
                    'Sol':{'total_usd':'1','currencies':{'PYG':'7000'}}},
        'weeks':[{'index':1,'label':'21/09 - 27/09','total_usd':'150','sellers':{'Junior':'100','Lucas':'50'}},
                 {'index':2,'label':'28/09 - 30/09','total_usd':'210','sellers':{'Junior':'80','Lucas':'130'}}]}
    if entries:data['entries']=details()
    return data


def book(key, year=2026, month=9, kind='archive', **kwargs):
    data = snapshot(**kwargs)
    # Ordinary historical fixtures belong to their recorded year/month. Tests
    # for dates crossing workbook periods construct that case explicitly.
    for entry in data.get('entries', {}).get('rows', []):
        if entry.get('date'):
            entry['date'] = datetime.fromisoformat(entry['date']).replace(year=year, month=month).date().isoformat()
    return SalesBIWorkbook(id=key,filename='PRIVATE_SOURCE_FILENAME.xlsx',kind=kind,year=year,month=month,
        parser_version=3,remote_version='1',active=True,synced_at=datetime(2026,9,30,tzinfo=timezone.utc),
        snapshot=data)


@pytest.fixture
def bi_env(env):
    factory,_,uid,_=env
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[SalesBIWorkbook.__table__,SalesBIConfig.__table__,AuditEvent.__table__])
        db.add_all([book('archive'),book('duplicate-current',kind='current',total='99999'),
                    book('old',year=2025,junior='80',total='500'),
                    book('older',year=2024,junior='60',total='250'),book('august',month=8,junior='40',total='100')])
        db.add(SalesBIConfig(id=1,current_url='https://private.invalid/current',archive_url='https://private.invalid/archive',
            archive_root='SECRET_FOLDER',requested_at=datetime(2026,9,1,tzinfo=timezone.utc),
            next_sync_at=datetime(2026,9,30,21,tzinfo=timezone.utc)))
        db.commit()
    return factory,uid


def run(bi_env, **kwargs):
    factory,uid=bi_env
    with factory() as db:return query(db,Args(**kwargs),uid)


def test_default_snapshot_corrected_closing_no_duplicate_or_sync(bi_env):
    factory,uid=bi_env
    with factory() as db:
        before=deepcopy(db.get(SalesBIConfig,1).__dict__)
        result=query(db,Args(),uid)
        assert result['periodo']['ano']==2026 and result['periodo']['mes']==9
        assert result['fechamento_corrigido']['total_usd']==777
        assert result['fechamento_corrigido']['source_months']==1
        assert result['origem']['fontes_no_periodo']==1
        assert 'snapshot' in result['origem']['leitura']
        assert before['requested_at']==db.get(SalesBIConfig,1).requested_at
        assert before['next_sync_at']==db.get(SalesBIConfig,1).next_sync_at
        assert not db.dirty and not db.new
        text=json.dumps(jsonable_encoder(result))
        assert 'PRIVATE_SOURCE' not in text and 'SECRET_FOLDER' not in text and 'private.invalid' not in text


def test_year_accumulation_comparison_and_rankings(bi_env):
    year=run(bi_env,ano=2026)
    assert year['fechamento_corrigido']['total_usd']==877
    compare=run(bi_env,visao='comparar_anos',mes=9,anos=[2024,2025,2026])
    assert [r['total_usd'] for r in compare['resultados']]==[250,500,777]
    assert compare['resultados'][1]['difference_usd']==250
    assert compare['resultados'][2]['difference_percent']==55.4
    missing=run(bi_env,visao='comparar_anos',mes=9,anos=[2023,2026])
    assert missing['periodo']['anos_sem_snapshot']==[2023]
    assert [r['year'] for r in missing['resultados']]==[2026]
    rank=run(bi_env,visao='ranking_vendedores',ano=2026,mes=9)
    assert [r['name'] for r in rank['resultados']]==['Junior','Lucas','Sol']
    week=run(bi_env,visao='ranking_semanas',ano=2026,mes=9,vendedor='Juninho',limite=1)
    assert week['resultados'][0]['total_usd']==100 and week['tem_mais']
    assert week['acesso']['vendedor']=='Junior'


@pytest.mark.parametrize('view',['resumo','comparar_anos','ranking_vendedores','ranking_semanas','lancamentos','por_dia','por_hora'])
def test_personal_scope_before_every_aggregation_and_forged_seller(bi_env,view):
    factory,uid=bi_env
    with factory() as db:
        user=db.get(Usuario,uid);user.sales_scope='own';user.sales_seller='Junior'
        result=query(db,Args(visao=view,vendedor='Lucas',mes=9,**({} if view=='comparar_anos' else {'ano':2026})),uid)
        text=json.dumps(jsonable_encoder(result))
        assert result['acesso']=={'escopo':'pessoal','vendedor':'Junior'}
        assert 'Lucas' not in text and 'Sol' not in text and '777' not in text and 'PRIVATE_SOURCE' not in text
        assert result['fechamento_corrigido']['total_usd']==(240 if view=='comparar_anos' else 100)
        if view=='lancamentos':assert result['total_resultados']==3
        if view=='ranking_vendedores':assert [r['name'] for r in result['resultados']]==['Junior']
        assert db.get(SalesBIWorkbook,'archive').snapshot['total_usd']=='777'


def test_entries_equal_payments_separate_currency_and_closing(bi_env):
    result=run(bi_env,visao='lancamentos',ano=2026,mes=9,vendedor='Junior',moeda='BRL',limite=1,pagina=2)
    assert result['total_resultados']==3 and result['tem_mais']
    assert len(result['resultados'])==1 and result['resultados'][0]['liquido']==98
    assert result['totais_observados']['currencies'][0]['gross']==280
    assert result['totais_observados']['currencies'][0]['net']==196
    assert result['fechamento_corrigido']['total_usd']==100
    assert 'official_total_usd' not in result['totais_observados']
    assert result['cobertura_datas_no_periodo']['undated_count']==1


def test_day_and_hour_use_actual_cells_never_sync_timestamp(bi_env,monkeypatch):
    monkeypatch.setattr(settings,'now',lambda:datetime(2026,9,24,0,1,tzinfo=settings.tz))
    yesterday=run(bi_env,periodo='ontem',vendedor='Junior')
    assert yesterday['periodo']['dia']=='2026-09-23'
    assert yesterday['total_resultados']==2
    # A date lookup examines every selected snapshot. Undated observations are
    # disclosed as coverage gaps and are never assigned to the requested day.
    assert yesterday['cobertura_datas_no_periodo']['undated_count']==4
    sync_day=run(bi_env,dia='2026-09-30')
    assert sync_day['total_resultados']==0
    assert sync_day['fechamento_corrigido']['total_usd']==777
    hour=run(bi_env,visao='por_hora',dia='2026-09-23',vendedor='Junior')
    assert hour['resultados'][0]['hour']==10 and hour['resultados'][0]['count']==2
    assert len(hour['resultados'])==1


def test_old_snapshot_reports_missing_entries_without_network_or_false_zero(bi_env):
    factory,uid=bi_env
    with factory() as db:
        db.get(SalesBIWorkbook,'archive').snapshot=snapshot(entries=False)
        db.flush()
        result=query(db,Args(visao='lancamentos',ano=2026,mes=9),uid)
        assert result['cobertura']['needs_sync'] is True
        assert result['fechamento_corrigido']['total_usd']==777
        assert 'consulta não dispara leitura' in ' '.join(result['avisos'])
        empty=query(db,Args(ano=2030,mes=4),uid)
        assert empty['fechamento_corrigido']['total_usd'] is None
        assert empty['origem']['fontes_no_periodo']==0


@pytest.mark.parametrize('state',['inactive','role','unmapped'])
def test_financial_permissions_fail_closed(bi_env,state):
    factory,uid=bi_env
    with factory() as db:
        user=db.get(Usuario,uid)
        if state=='inactive':user.ativo=False
        elif state=='role':user.role=UsuarioRole.VENDEDOR
        else:user.sales_scope='own';user.sales_seller=None
        assert 'erro' in query(db,Args(),uid)


def test_dispatch_requires_same_author_channel_and_explicit_reply(bi_env):
    factory,uid=bi_env
    with factory() as db:
        message=incoming(db,uid,'Quanto vendi?',channel='telegram',reply=False)
        identity=assistant_channels.authorized_identity(db,'telegram','123')
        assert 'erro' in execute_tool(db,message,identity,'consultar_vendas_planilhas',{})
        message.should_reply=True
        wrong=SimpleNamespace(active=True,user_id=uid,channel='whatsapp',external_id=message.sender_id)
        assert 'erro' in execute_tool(db,message,wrong,'consultar_vendas_planilhas',{})
        assert 'fechamento_corrigido' in execute_tool(db,message,identity,'consultar_vendas_planilhas',{})


@pytest.mark.parametrize('args',[{'limite':21},{'pagina':0},{'dia':'1800-01-01'},{'ano':2026,'periodo':'hoje'},
    {'visao':'comparar_anos','anos':[2026,2026]},{'visao':'ranking_semanas','dia':'2026-09-23'},
    {'visao':'resumo','busca':'Cliente'},{'dia':'2026-09-23','mes':8}])
def test_filters_validated_and_pages_bounded(args):
    with pytest.raises(ValidationError):Args(**args)


@pytest.mark.parametrize('text,expected',[
    ('Quanto vendeu Junior ontem?',True),('Mostre os lançamentos de setembro',True),
    ('Ranking de vendedores neste ano',True),('Cadastre uma venda para Junior',False),
    ('Qual é o preço de venda da camiseta?',False),('Quanto vendemos no PDV?',False),('Lance esta venda no ERP',False),('Quem folga amanhã?',False)])
def test_natural_source_intent(text,expected):
    assert spreadsheet_sales_intent(text) is expected
    assert spreadsheet_sales_intent('e ontem?','Quanto vendeu Junior?')


def test_agent_prioritizes_excel_over_employee_lookup_and_queries_again(bi_env,monkeypatch):
    factory,uid=bi_env
    choices=[];payloads=[]
    def complete(messages,*,tool_choice=None):
        choices.append(tool_choice)
        if len(choices)==1:
            return {'tool_calls':[{'id':'sheet','type':'function','function':{'name':'consultar_vendas_planilhas',
                    'arguments':json.dumps({'ano':2026,'mes':9,'vendedor':'Juninho'})}}]}
        payloads.extend(m['content'] for m in messages if m['role']=='tool')
        return {'content':'Junior vendeu US$ 100 em setembro de 2026, conforme a última sincronização das planilhas.'}
    monkeypatch.setattr(assistant_agent,'complete',complete)
    with factory() as db:
        message=incoming(db,uid,'Quanto vendeu Junior em setembro de 2026?',channel='telegram')
        assistant_agent.respond(db,message,assistant_channels.authorized_identity(db,'telegram','123'))
        assert choices[0]['function']['name']=='consultar_vendas_planilhas'
        assert 'fechamento_corrigido' in payloads[0]
        previous=message;previous.status='done';previous.response='OLD_TOTAL_99999';db.flush()
        choices.clear();payloads.clear()
        followup=incoming(db,uid,'e ontem?',channel='telegram')
        assistant_agent.respond(db,followup,assistant_channels.authorized_identity(db,'telegram','123'))
        assert choices[0]['function']['name']=='consultar_vendas_planilhas'


def test_agent_never_answers_financial_question_from_history_alone(bi_env,monkeypatch):
    factory,uid=bi_env
    calls=[]
    monkeypatch.setattr(assistant_agent,'complete',lambda messages,**kwargs:calls.append(kwargs) or {'content':'O total antigo era 99999.'})
    with factory() as db:
        message=incoming(db,uid,'Quanto vendemos este mês?',channel='telegram')
        response=assistant_agent.respond(db,message,assistant_channels.authorized_identity(db,'telegram','123'))
        assert '99999' not in str(response)
        assert 'Nenhum valor antigo foi reutilizado' in str(response)
        assert len(calls)==2
