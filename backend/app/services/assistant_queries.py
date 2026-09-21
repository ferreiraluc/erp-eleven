"""Read-only, bounded ERP queries. The model chooses filters, never SQL or columns."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import String, case, cast, exists, func, literal, or_, select, union_all

from ..config import settings
from ..models.cliente import Cliente
from ..models.inventory import Item
from ..models.pdv import PdvCliente, PdvSale
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.usuario import Usuario
from ..models.venda import Venda
from ..models.vendedor import Vendedor


def literal_pattern(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def contains(columns, value):
    return or_(*(c.ilike(literal_pattern(value), escape="\\") for c in columns))


def scalar(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)  # never round money through binary floating point
    return value


def record(row):
    return {key: scalar(value) for key, value in row.items()}


def local_timestamp(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(settings.tz).isoformat()


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    termo: str | None = Field(default=None, min_length=2, max_length=100,
                              description="Somente nome, código ou termo procurado; omita para listar todos.")
    limite: int = Field(default=5, ge=1, le=20)
    pagina: int = Field(default=1, ge=1, le=1000)


class DatedArgs(QueryArgs):
    periodo: Literal["hoje", "ontem", "anteontem", "amanha", "ultimos_7_dias", "ultimos_30_dias",
                     "proximos_7_dias", "esta_semana", "semana_passada", "proxima_semana", "este_mes", "mes_passado"] | None = None
    data_inicio: date | None = Field(default=None, description="AAAA-MM-DD, inclusive; não combinar com periodo.")
    data_fim: date | None = Field(default=None, description="AAAA-MM-DD, inclusive; não combinar com periodo.")

    @model_validator(mode="after")
    def valid_period(self):
        if self.periodo and (self.data_inicio or self.data_fim):
            raise ValueError("Use periodo OU datas explícitas.")
        if self.data_inicio and self.data_fim and self.data_inicio > self.data_fim:
            raise ValueError("Data inicial posterior à final.")
        return self


class ShipmentArgs(DatedArgs):
    situacao: Literal["todos", "em_aberto", "PENDENTE", "EM_TRANSITO", "ENTREGUE", "ERRO", "NAO_ENCONTRADO"] = "todos"
    ordem: Literal["recentes", "antigos", "priorizar_abertos"] = Field(
        default="recentes", description="Para rastreio de um cliente sem período, use priorizar_abertos. Se pedir último/mais recente, use recentes.")


class OrderArgs(DatedArgs):
    situacao: Literal["todos", "em_aberto", "sem_rastreio", "PENDENTE", "PROCESSANDO", "ENVIADO", "ENTREGUE", "CANCELADO"] = "todos"


class StockArgs(QueryArgs):
    situacao: Literal["todos", "disponivel", "zerado", "abaixo_minimo"] = "todos"
    local: Literal["total", "loja", "deposito"] = "total"
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    tamanho: str | None = Field(default=None, min_length=1, max_length=50)
    cor: str | None = Field(default=None, min_length=1, max_length=50)


class CustomerArgs(QueryArgs):
    origem: Literal["ambos", "pedidos", "pdv"] = "ambos"


class SalesArgs(DatedArgs):
    origem: Literal["ambos", "vendas", "pdv"] = "ambos"
    vendedor: str | None = Field(default=None, min_length=2, max_length=100)
    # No generic termo: legacy sales have no customer column.
    termo: None = Field(default=None, description="Não aplicável; use vendedor. Não há cliente no módulo vendas.")


def period_bounds(args, today=None):
    today = today or settings.now().date()
    start, end = args.data_inicio, args.data_fim
    period = args.periodo
    if period in ("hoje", "ontem", "anteontem", "amanha"):
        start = end = today - timedelta(days={"hoje": 0, "ontem": 1, "anteontem": 2, "amanha": -1}[period])
    elif period in ("ultimos_7_dias", "ultimos_30_dias"):
        start, end = today - timedelta(days=6 if period == "ultimos_7_dias" else 29), today
    elif period == "proximos_7_dias":
        start, end = today, today + timedelta(days=6)
    elif period in ("esta_semana", "semana_passada", "proxima_semana"):
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        if period == "semana_passada":
            start, end = start - timedelta(days=7), start - timedelta(days=1)
        elif period == "proxima_semana":
            start, end = start + timedelta(days=7), start + timedelta(days=13)
    elif period in ("este_mes", "mes_passado"):
        start = today.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if period == "mes_passado":
            end = start - timedelta(days=1)
            start = end.replace(day=1)
    return start, end


def local_day(db, column):
    """ERP timestamp-without-time-zone columns are persisted in PostgreSQL's UTC session."""
    if db.bind.dialect.name == "postgresql":
        return func.date(func.timezone(settings.TIMEZONE, func.timezone("UTC", column)))
    # SQLite is only used by isolated tests for current dates; production uses PostgreSQL's date-aware timezone conversion.
    return func.date(column, f"{int(settings.now().utcoffset().total_seconds())} seconds")


def date_filter(query, column, args, timestamp=False):
    start, end = period_bounds(args)
    if timestamp:
        # Convert local midnight to the database's UTC-naive timestamps. End is exclusive.
        def midnight(day):
            return datetime.combine(day, time.min, settings.tz).astimezone(timezone.utc).replace(tzinfo=None)
        if start:
            query = query.filter(column >= midnight(start))
        if end:
            query = query.filter(column < midnight(end + timedelta(days=1)))
    else:
        if start:
            query = query.filter(column >= start)
        if end:
            query = query.filter(column <= end)
    return query


def page(query, args):
    total = query.order_by(None).count()
    rows = query.offset((args.pagina - 1) * args.limite).limit(args.limite).all()
    return rows, {"total": total, "pagina": args.pagina, "limite": args.limite,
                  "tem_mais": args.pagina * args.limite < total}


def period_info(args, field):
    start, end = period_bounds(args)
    return {"inicio": scalar(start), "fim": scalar(end), "campo": field, "fuso": settings.TIMEZONE}


OPEN_SHIPMENTS = ("PENDENTE", "EM_TRANSITO", "ERRO", "NAO_ENCONTRADO")


def shipments_source(db):
    """One row per tracking code, including legacy order-only codes, never double-counting."""
    r, p = Rastreamento, Pedido
    tracks = select(
        cast(r.id, String).label("id"), r.codigo_rastreio.label("codigo"),
        func.coalesce(r.destinatario, p.cliente_nome).label("cliente"),
        p.numero_pedido.label("pedido"), p.cliente_telefone.label("telefone_busca"),
        cast(p.cliente_id, String).label("cliente_id"),
        cast(r.status, String).label("status"), cast(p.status, String).label("status_pedido"),
        func.coalesce(r.data_criacao, local_day(db, r.created_at)).label("data_envio"),
        r.created_at.label("cadastrado_em"), r.ultima_atualizacao.label("consultado_em"),
        literal("rastreamentos").label("origem"),
    ).outerjoin(p, p.id == r.pedido_id).where(r.ativo.is_(True))
    # A code explicitly deactivated in Rastreamento must not resurface via Pedido.
    known_code = exists(select(r.id).where(r.codigo_rastreio == p.codigo_rastreio))
    legacy_status = case((p.status == "ENVIADO", "EM_TRANSITO"), (p.status == "ENTREGUE", "ENTREGUE"),
                         (p.status == "CANCELADO", "CANCELADO"), else_="PENDENTE")
    orders = select(
        cast(p.id, String), p.codigo_rastreio, p.cliente_nome, p.numero_pedido, p.cliente_telefone,
        cast(p.cliente_id, String), legacy_status, cast(p.status, String),
        local_day(db, p.created_at), p.created_at, literal(None), literal("pedido_sem_rastreamento"),
    ).where(p.codigo_rastreio.isnot(None), p.codigo_rastreio != "", ~known_code)
    return union_all(tracks, orders).subquery()


def query_shipments(db, args):
    source = shipments_source(db)
    c = source.c
    q = db.query(source)
    if args.termo:
        q = q.filter(contains([c.cliente, c.codigo, c.pedido, c.telefone_busca], args.termo))
    if args.situacao == "em_aberto":
        q = q.filter(c.status.in_(OPEN_SHIPMENTS))
    elif args.situacao != "todos":
        q = q.filter(c.status == args.situacao)
    q = date_filter(q, c.data_envio, args)
    counts = {status: count for status, count in q.with_entities(c.status, func.count()).group_by(c.status).all()}
    order = [c.data_envio.desc(), c.cadastrado_em.desc(), c.id.desc()]
    if args.ordem == "antigos":
        order = [c.data_envio.asc(), c.cadastrado_em.asc(), c.id.asc()]
    if args.ordem == "priorizar_abertos":
        order.insert(0, case((c.status.in_(OPEN_SHIPMENTS), 0), else_=1))
    rows, info = page(q.order_by(*order), args)
    results = []
    for row in rows:
        data = record(row._mapping)
        for field in ("cadastrado_em", "consultado_em"):
            data[field] = local_timestamp(row._mapping[field])
        data.pop("telefone_busca")
        data.pop("cliente_id")
        results.append(data)
    # Identity check over the entire filtered set, not just the displayed page.
    # Same full name with different registered customer IDs remains ambiguous.
    identities = q.with_entities(func.lower(func.trim(c.cliente)), c.cliente_id).distinct().limit(2).all()
    unique_customer = len(identities) == 1 and bool(identities[0][0])
    open_count = sum(counts.get(status, 0) for status in OPEN_SHIPMENTS)
    recommendation = None
    if args.termo and args.pagina == 1 and results:
        # Exact code/order lookup is unambiguous even when customer names are absent.
        exact = q.filter(or_(func.lower(c.codigo) == args.termo.lower(), func.lower(c.pedido) == args.termo.lower())).limit(2).all()
        if len(exact) == 1:
            recommendation = {"codigo": exact[0]._mapping["codigo"], "motivo": "código/pedido exato"}
        elif unique_customer and (info["total"] == 1 or args.ordem == "recentes" or (args.ordem == "priorizar_abertos" and open_count <= 1)):
            recommendation = {"codigo": results[0]["codigo"], "motivo": (
                "único envio em aberto deste cliente" if args.ordem == "priorizar_abertos" and open_count == 1
                else "envio mais recente deste cliente" if info["total"] > 1 else "único envio encontrado")}
    return {**info, "periodo": period_info(args, "data de cadastro do envio no ERP"),
            "por_status": counts, "em_aberto": open_count, "resultados": results,
            "recomendado": recommendation, "clientes_distintos": not unique_customer and info["total"] > 1,
            "fonte": "Dados salvos no ERP, sem consulta online aos Correios. Data do envio é data_criacao; "
                     "códigos existentes apenas no pedido usam a data do pedido (origem identificada). "
                     "ERRO/NAO_ENCONTRADO indicam falha de rastreio, não comprovam atraso ou cancelamento.",
            "instrucao": "Listagens: responda diretamente com os resultados. Rastreio individual: use recomendado; "
                         "se houver vários envios em aberto, mostre os mais recentes com data/status e peça "
                         "esclarecimento somente se precisar escolher um. Nunca trate entregues antigos como pendentes."}


def query_orders(db, args):
    p = Pedido
    q = db.query(p)
    if args.termo:
        q = q.filter(contains([p.cliente_nome, p.numero_pedido, p.codigo_rastreio, p.cliente_telefone], args.termo))
    if args.situacao == "em_aberto":
        q = q.filter(p.status.in_(["PENDENTE", "PROCESSANDO", "ENVIADO"]))
    elif args.situacao == "sem_rastreio":
        q = q.filter(or_(p.codigo_rastreio.is_(None), p.codigo_rastreio == ""),
                     ~exists(select(Rastreamento.id).where(Rastreamento.pedido_id == p.id, Rastreamento.ativo.is_(True))))
    elif args.situacao != "todos":
        q = q.filter(p.status == args.situacao)
    q = date_filter(q, p.created_at, args, timestamp=True)
    counts = {scalar(status): count for status, count in q.with_entities(p.status, func.count()).group_by(p.status).all()}
    rows, info = page(q.order_by(p.created_at.desc(), p.id.desc()), args)
    return {**info, "periodo": period_info(args, "cadastro do pedido"), "por_status": counts,
            "resultados": [{"pedido": p.numero_pedido, "cliente": p.cliente_nome, "status_pedido": scalar(p.status),
                            "codigo_cadastrado": p.codigo_rastreio, "cadastrado_em_utc": scalar(p.created_at)} for p in rows],
            "aviso": "Status administrativo do pedido pode divergir da entrega; para entrega consulte buscar_rastreios."}


def query_stock(db, args):
    i = Item
    qty = {"total": i.current_stock, "loja": i.stock_loja, "deposito": i.stock_deposito}[args.local]
    q = db.query(i).filter(i.is_active.is_(True))
    if args.termo:
        q = q.filter(contains([i.name, i.sku_internal, i.barcode, i.brand, i.category], args.termo))
    for column, value in ((i.category, args.categoria), (i.size, args.tamanho), (i.color, args.cor)):
        if value:
            q = q.filter(func.lower(column) == value.lower())
    if args.situacao == "disponivel":
        q = q.filter(qty > 0)
    elif args.situacao == "zerado":
        q = q.filter(qty <= 0)
    elif args.situacao == "abaixo_minimo":
        if args.local != "total":
            return {"erro": "O estoque mínimo é global por produto; use local=total para abaixo_minimo."}
        q = q.filter(qty < i.min_stock)
    totals = q.with_entities(*(func.coalesce(func.sum(column), 0) for column in
                              (i.current_stock, i.stock_loja, i.stock_deposito))).one()
    by_location = dict(zip(("total", "loja", "deposito"), totals))
    rows, info = page(q.order_by(i.name, i.size, i.id), args)
    return {**info, "local": args.local, "unidades": by_location[args.local],
            "saldos_por_local": by_location,
            "escopo_dos_saldos": "Todos os produtos filtrados, não só a página exibida.",
            "resultados": [{"produto": x.name, "sku": x.sku_internal, "categoria": x.category,
                            "tamanho": x.size, "cor": x.color, "marca": x.brand,
                            "total": x.current_stock, "loja": x.stock_loja, "deposito": x.stock_deposito,
                            "minimo": x.min_stock, "preco_venda": scalar(x.sale_price), "moeda": x.sale_currency} for x in rows]}


def query_customers(db, args):
    results = {}
    for source, model in (("pedidos", Cliente), ("pdv", PdvCliente)):
        if args.origem not in ("ambos", source):
            continue
        q = db.query(model).filter(model.ativo.is_(True))
        if args.termo:
            q = q.filter(contains([model.nome, model.telefone], args.termo))
        rows, info = page(q.order_by(model.nome, model.id), args)
        results[source] = {**info, "resultados": [{"nome": row.nome} for row in rows]}
    return {"cadastros": results, "aviso": "Clientes de pedidos e PDV são cadastros separados. "
            "Envios podem ter destinatário sem cadastro de cliente; consulte também buscar_rastreios."}


def query_sales(db, args, user_id):
    user = db.get(Usuario, user_id)
    if not user or not user.ativo or scalar(user.role) not in ("ADMIN", "GERENTE"):
        return {"erro": "Resumos financeiros do assistente disponíveis somente para ADMIN ou GERENTE."}
    result = {"periodo": period_info(args, "data_venda (vendas) / criação local (PDV)"),
              "aviso": "Módulos separados: não somar vendas e PDV como faturamento consolidado; pode haver sobreposição. "
                       "Totais por moeda, sem conversão. PDV exclui canceladas."}
    if args.origem in ("ambos", "vendas"):
        q = db.query(Venda).join(Vendedor, Vendedor.id == Venda.vendedor_id)
        q = date_filter(q, Venda.data_venda, args)
        if args.vendedor:
            q = q.filter(contains([Vendedor.nome], args.vendedor))
        sums = q.with_entities(Venda.moeda, func.count(), func.sum(Venda.valor_bruto), func.sum(Venda.valor_liquido)).group_by(Venda.moeda).all()
        rows, info = page(q.add_columns(Vendedor.nome).order_by(Venda.data_venda.desc(), Venda.created_at.desc(), Venda.id.desc()), args)
        result["vendas"] = {**info,
            "totais": [{"moeda": scalar(currency), "quantidade": count, "bruto": scalar(gross), "liquido": scalar(net)} for currency, count, gross, net in sums],
            "resultados": [{"data": scalar(sale.data_venda), "vendedor": name, "moeda": scalar(sale.moeda),
                            "bruto": scalar(sale.valor_bruto), "liquido": scalar(sale.valor_liquido)} for sale, name in rows]}
    if args.origem in ("ambos", "pdv"):
        q = db.query(PdvSale).outerjoin(Usuario, Usuario.id == PdvSale.vendedor_id).filter(PdvSale.status == "completed")
        q = date_filter(q, PdvSale.created_at, args, timestamp=True)
        if args.vendedor:
            q = q.filter(contains([Usuario.nome], args.vendedor))
        total = q.with_entities(func.coalesce(func.sum(PdvSale.total_gs), 0)).scalar()
        rows, info = page(q.add_columns(Usuario.nome).order_by(PdvSale.created_at.desc(), PdvSale.id.desc()), args)
        result["pdv"] = {**info, "valor_total_gs": scalar(total), "moeda": "G$",
            "resultados": [{"data_utc": scalar(sale.created_at), "vendedor": name, "cliente": sale.cliente_nome,
                            "total_gs": scalar(sale.total_gs)} for sale, name in rows]}
    return result
