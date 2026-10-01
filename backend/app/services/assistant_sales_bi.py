"""Read-only bot access to Excel BI snapshots, scoped before every aggregation."""
from datetime import date, timedelta
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import settings
from ..models.sales_bi import SalesBIWorkbook
from ..models.usuario import Usuario
from .access_policy import own_sales
from .sales_bi import build_overview, choose_workbooks, private_workbooks
from .sales_bi_entries import build_entries
from .sales_bi_parser import normal, seller_name


class SpreadsheetSalesArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    visao: Literal['resumo', 'comparar_anos', 'ranking_vendedores', 'ranking_semanas', 'lancamentos', 'por_dia', 'por_hora'] = 'resumo'
    ano: int | None = Field(None, ge=2000, le=2100)
    mes: int | None = Field(None, ge=1, le=12)
    anos: list[int] | None = Field(None, min_length=1, max_length=10, description='Anos a comparar; use somente com comparar_anos.')
    periodo: Literal['ultimo_mes_disponivel', 'este_mes', 'mes_passado', 'este_ano', 'ano_passado', 'hoje', 'ontem', 'todos'] | None = None
    dia: date | None = None
    vendedor: str | None = Field(None, max_length=100, description='Nome/alias do vendedor. Contas pessoais sempre usam seu vendedor autorizado.')
    moeda: Literal['USD', 'BRL', 'PYG', 'EUR'] | None = None
    busca: str | None = Field(None, max_length=120, description='Filtro textual dos lançamentos individuais; não pesquisa fórmulas.')
    pagina: int = Field(1, ge=1, le=25000)
    limite: int = Field(10, ge=1, le=20)

    @model_validator(mode='after')
    def consistent_filters(self):
        if self.anos and (self.visao != 'comparar_anos' or self.ano is not None or len(set(self.anos)) != len(self.anos) or any(y < 2000 or y > 2100 for y in self.anos)):
            raise ValueError('Use anos distintos de 2000 a 2100 somente em comparar_anos, sem ano individual.')
        if self.periodo and any(v is not None for v in (self.ano, self.mes, self.dia)):
            raise ValueError('Escolha um período relativo ou ano/mês/dia explícitos, sem misturar.')
        if self.dia and not 2000 <= self.dia.year <= 2100:
            raise ValueError('Use data entre 2000 e 2100.')
        if self.dia and ((self.ano and self.ano != self.dia.year) or (self.mes and self.mes != self.dia.month)):
            raise ValueError('O dia precisa pertencer ao ano e mês informados.')
        if self.visao == 'comparar_anos' and (self.periodo or self.dia or self.ano):
            raise ValueError('Comparações usam mês e anos opcionais, sem período relativo, dia ou ano individual.')
        if self.visao.startswith('ranking') and (self.dia or self.periodo in ('hoje', 'ontem') or self.moeda or self.busca):
            raise ValueError('Rankings usam resultados corrigidos em USD por ano/mês; para dia/moeda use lançamentos.')
        if self.busca and self.visao not in ('lancamentos', 'por_dia', 'por_hora'):
            raise ValueError('Use busca somente em lançamentos, por_dia ou por_hora.')
        return self


def spreadsheet_sales_intent(content, previous_text=None):
    """Prefer the business's Excel source for natural financial questions."""
    text = normal(content)
    if re.search(r'\b(pdv|fiado|vendas operacionais|vendas tradicionais|caixa do erp|precos? (?:de )?venda)\b', text):
        return False
    if re.search(r'\b(cadastr\w*|registr\w*|lancar|lanca|lance|lancem|anot\w*|imprim\w*)\b', text) and not re.search(r'\b(consult\w*|mostr\w*|listar|veja|ver|quant\w*)\b', text):
        return False
    if re.search(r'\b(vendas?|vendemos|vendeu|venderam|vendi|faturamento|ranking|acumulado|planilhas?|lancamentos|excel|intraday|intradiario)\b', text):
        return True
    return bool(previous_text and re.search(r'^(e |so |apenas |agora |mais |os proximos |proxim[ao])', text)
                and spreadsheet_sales_intent(previous_text))


def _page(items, args):
    offset = (args.pagina - 1) * args.limite
    return {'total_resultados': len(items), 'pagina': args.pagina, 'limite': args.limite,
            'tem_mais': offset + args.limite < len(items), 'resultados': items[offset:offset + args.limite]}


def _period(args, selected):
    today = settings.now().date()
    latest = max(((r.year, r.month) for r in selected), default=(None, None))
    year, month, day = args.ano, args.mes, args.dia
    basis = 'período informado'
    if args.visao == 'comparar_anos':
        month = month or latest[1]
        return None, month, None, 'mesmo mês nos anos selecionados; mês mais recente disponível se omitido'
    if args.periodo in ('hoje', 'ontem'):
        day = today - timedelta(days=args.periodo == 'ontem')
        basis = args.periodo + ' no fuso da loja'
    if day:
        return day.year, day.month, day.isoformat(), basis
    if args.periodo == 'este_mes': year, month = today.year, today.month
    elif args.periodo == 'mes_passado':
        last = today.replace(day=1) - timedelta(days=1)
        year, month = last.year, last.month
    elif args.periodo in ('este_ano', 'ano_passado'):
        year, month = today.year - (args.periodo == 'ano_passado'), None
    elif args.periodo == 'todos': year, month = None, None
    elif args.periodo == 'ultimo_mes_disponivel' or (year is None and month is None):
        year, month = latest
        basis = 'último mês disponível no snapshot; não é necessariamente o mês atual'
    elif year is None:
        year = today.year
        basis = 'mês informado sem ano: usado o ano atual da loja'
    return year, month, None, args.periodo or basis


def query_spreadsheet_sales(db, args, user_id):
    user = db.get(Usuario, user_id)
    role = getattr(getattr(user, 'role', None), 'value', None)
    if not user or not user.ativo or role not in ('ADMIN', 'GERENTE'):
        return {'erro':'Consultas financeiras de planilhas exigem usuário ativo autorizado como ADMIN ou GERENTE.'}
    private = own_sales(user)
    if private and not user.sales_seller:
        return {'erro':'Seu vendedor ainda não foi vinculado às planilhas. Peça ao Lucas para configurar seu acesso.'}
    rows = db.query(SalesBIWorkbook).filter_by(active=True).all()
    # Project before discovery, source selection, rankings, comparisons or row totals.
    if private:
        seller = user.sales_seller
        rows = private_workbooks(rows, seller)
    else:
        seller = None
        if args.vendedor:
            wanted = normal(seller_name(args.vendedor))
            candidates = sorted({name for row in rows if row.snapshot for name in row.snapshot.get('sellers', {})
                                 if normal(seller_name(name)) == wanted})
            if len(candidates) != 1:
                return {'erro':'Vendedor não identificado nas planilhas. Informe o nome cadastrado.',
                        'opcoes': candidates[:20] if candidates else sorted({name for row in rows if row.snapshot for name in row.snapshot.get('sellers', {})})[:20]}
            seller = candidates[0]
    if args.anos:
        rows = [r for r in rows if r.year in args.anos]
    selected = choose_workbooks(rows)
    year, month, day, basis = _period(args, selected)
    scoped = [r for r in selected if (not year or r.year == year) and (not month or r.month == month)]
    view = build_overview(rows, year, month, seller)
    sync_dates = sorted(r.synced_at.isoformat() for r in scoped if r.synced_at)
    output = {
        'origem': {'tipo':'BI das planilhas Excel / OneDrive', 'pagina':'/bi-vendas', 'leitura':'snapshot salvo, sem iniciar sincronização',
                   'sincronizacao':'diária às 18h de Brasília ou botão manual no ERP', 'fontes_no_periodo':len(scoped),
                   'snapshot_mais_antigo_em':sync_dates[0] if sync_dates else None, 'snapshot_mais_recente_em':sync_dates[-1] if sync_dates else None,
                   'fontes_com_pendencia':sum(bool(r.error) for r in scoped)},
        'acesso': {'escopo':'pessoal' if private else 'loja', 'vendedor':seller},
        'periodo': {'ano':year, 'mes':month, 'dia':day, 'anos':sorted(args.anos) if args.anos else None,
                    'criterio':basis, 'fuso':settings.TIMEZONE},
        'fechamento_corrigido': {'moeda':'USD', **view['selected'],
            'natureza':'resultado corrigido salvo do mês/ano; não é a soma de lançamentos filtrados por dia, moeda ou busca'},
        'moedas_do_fechamento': [r for r in view['currencies'] if not args.moeda or r['currency'] == args.moeda],
        'avisos':['Excel, vendas operacionais e PDV são fontes distintas: não somar seus totais.',
                  'Ausência de valor não é zero. Resultados de mês corrente podem ser parciais.'],
    }
    if args.visao == 'comparar_anos' and args.anos:
        missing = sorted(set(args.anos) - {r.year for r in scoped})
        output['periodo']['anos_sem_snapshot'] = missing
        if missing:
            output['avisos'].append('Não há snapshot deste mês nos anos: ' + ', '.join(map(str, missing)) + '. Não foram preenchidos com zero.')
    if not scoped:
        output['avisos'].append('Não há snapshot para o período selecionado. Nenhum valor foi estimado.')
    if private:
        output['avisos'].append('Esta conta consulta somente seu vendedor; filtros não ampliam o acesso e o ranking é pessoal.')
    if args.visao in ('lancamentos', 'por_dia', 'por_hora') or day:
        details = build_entries(rows, year=year, month=month, seller=seller, currency=args.moeda,
            day=day, search=args.busca, offset=(args.pagina - 1) * args.limite, limit=args.limite, private=private)
        output.update(visao=args.visao if not day or args.visao != 'resumo' else 'lancamentos',
            filtros_lancamentos={'moeda':args.moeda,'busca':args.busca}, totais_observados={k:v for k,v in details['summary'].items() if k != 'official_total_usd'}, cobertura=details['coverage'])
        date_coverage = build_entries(rows, year=year, month=month, seller=seller, currency=args.moeda,
            search=args.busca, offset=0, limit=1, private=private)['summary'] if day else details['summary']
        output['cobertura_datas_no_periodo'] = {k:date_coverage[k] for k in ('count', 'dated_count', 'timed_count', 'undated_count')}
        if date_coverage['undated_count']:
            output['avisos'].append('Há lançamentos sem data explícita no período: consultas por dia/hora não representam todas as vendas.')
        output['avisos'].append('Datas e horas vêm de células explícitas. Horário da sincronização, nome da aba e dia da semana não provam a data de venda. Linhas iguais podem ser vendas distintas.')
        if details['coverage']['needs_sync']:
            output['avisos'].append('Parte dos snapshots ainda não contém lançamentos individuais. Aguarde a leitura diária ou atualize pelo botão do ERP; a consulta não dispara leitura.')
        if args.visao in ('por_dia','por_hora'):
            groups = details['daily'] if args.visao == 'por_dia' else details['hourly']
            output.update(_page(groups, args))
            if not groups:output['avisos'].append('Não há data/hora explícita suficiente para esse agrupamento; não foi inventado intradiário.')
        else:
            output.update(total_resultados=details['total'], pagina=args.pagina, limite=args.limite,
                          tem_mais=details['offset'] + args.limite < details['total'], resultados=[{
                'vendedor':r['seller'], 'moeda':r['currency'], 'bruto':r['gross'], 'liquido':r['net'],
                'data':r['date'], 'hora':r['time'], 'dia_da_semana':r['day_group'],
                'cliente':r['customer'], 'pagamento':r['payment_method'], 'celula':r['source_cell'],
                'ano':r['year'], 'mes':r['month'], 'sincronizado_em':r['synced_at'], 'snapshot_com_pendencia':r['stale'],
            } for r in details['items']])
        # Reconciliation is the whole selected month, not a day/currency-filtered total.
        output['conferencia_mensal'] = {'natureza':'fechamento publicado versus linhas do mês, sem aplicar dia/busca',
                                       **_page([r for r in details['reconciliation'] if not args.moeda or r['currency'] == args.moeda], args)}
    elif args.visao == 'comparar_anos':
        output.update(visao=args.visao, **_page(view['comparison'], args))
        # Source filenames/warnings are not needed in the bot, especially for personal accounts.
        output['resultados'] = [{k:r.get(k) for k in ('year','month','total_usd','partial','synced_at','stale','difference_usd','difference_percent','previous_year')} for r in output['resultados']]
    elif args.visao == 'ranking_vendedores':
        ranking = [r for r in view['ranking'] if not seller or r['name'] == seller]
        output.update(visao=args.visao, **_page(ranking, args))
    elif args.visao == 'ranking_semanas':
        weeks = [{k:r[k] for k in ('year','month','index','label','total_usd','partial')} for r in view['weeks']]
        output.update(visao=args.visao, **_page(weeks, args))
    else:
        months = [{k:r.get(k) for k in ('year','month','total_usd','partial','synced_at','stale')} for r in view['months']
                  if (not year or r['year'] == year) and (not month or r['month'] == month)]
        output.update(visao='resumo', **_page(months, args))
    return output
