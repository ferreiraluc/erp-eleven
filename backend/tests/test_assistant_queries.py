"""Regressions for natural queries, confirmed calendar writes and ordered provider delivery."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import uuid

import pytest

from test_assistant import setup, incoming, post_telegram, telegram_update
from app.config import settings
from app.models import Pedido, Rastreamento, Usuario
from app.models.assistant import AssistantAction, AssistantDelivery, AssistantMessage, utcnow
from app.models.folga import Folga
from app.models.inventory import Item
from app.models.pdv import PdvSale
from app.models.venda import Venda, MoedaTipo, PagamentoMetodo
from app.models.vendedor import Vendedor
from app.models.usuario import UsuarioRole
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services.assistant_queries import (
    ShipmentArgs, OrderArgs, StockArgs, SalesArgs, DatedArgs,
    query_shipments, query_orders, query_stock, query_sales, period_bounds,
)
from app.services.assistant_schedule import ScheduleArgs, ScheduleWriteArgs, prepare_schedule, confirm_action, query_schedule
from app.services.assistant_replies import Reply
from app import assistant_worker as worker


def shipment(db, code, name="Vandilson Viana", status="EM_TRANSITO", day=date(2026, 9, 20), **kwargs):
    item = Rastreamento(codigo_rastreio=code, destinatario=name, status=status, data_criacao=day,
                        created_at=datetime.combine(day, datetime.min.time()) + timedelta(hours=15), **kwargs)
    db.add(item)
    db.flush()
    return item


def test_latest_shipments_without_search_and_accurate_totals(setup):
    factory, _, _ = setup
    with factory() as db:
        for i in range(9):
            shipment(db, f"AA{i:09d}BR", day=date(2026, 9, 10 + i), status="ENTREGUE" if i < 6 else "EM_TRANSITO")
        result = query_shipments(db, ShipmentArgs(limite=5))
        assert result["total"] == 9 and result["tem_mais"]
        assert result["por_status"] == {"ENTREGUE": 6, "EM_TRANSITO": 3}
        assert [r["codigo"] for r in result["resultados"]] == [f"AA{i:09d}BR" for i in range(8, 3, -1)]
        second = query_shipments(db, ShipmentArgs(limite=5, pagina=2))
        assert len(second["resultados"]) == 4 and not second["tem_mais"]


def test_unique_open_shipment_beats_old_delivered_history(setup):
    factory, _, _ = setup
    with factory() as db:
        for i in range(4):
            shipment(db, f"OLD{i}", status="ENTREGUE", day=date(2026, 8, 10 + i))
        shipment(db, "CURRENT")
        result = query_shipments(db, ShipmentArgs(termo="Vandilson", ordem="priorizar_abertos"))
        assert result["recomendado"]["codigo"] == "CURRENT"
        assert result["em_aberto"] == 1
        shipment(db, "ANOTHER", day=date(2026, 9, 21))
        assert query_shipments(db, ShipmentArgs(termo="Vandilson", ordem="priorizar_abertos"))["recomendado"] is None
        assert query_shipments(db, ShipmentArgs(termo="Vandilson", ordem="recentes"))["recomendado"]["codigo"] == "ANOTHER"


def test_homonym_beyond_first_page_is_not_silently_selected(setup):
    factory, _, _ = setup
    with factory() as db:
        shipment(db, "FIRST", name="João Silva")
        shipment(db, "SECOND", name="João Souza", day=date(2026, 8, 1))
        result = query_shipments(db, ShipmentArgs(termo="João", limite=1, ordem="recentes"))
        assert result["recomendado"] is None and result["clientes_distintos"]
        assert query_shipments(db, ShipmentArgs(termo="FIRST"))["recomendado"]["codigo"] == "FIRST"
        assert query_shipments(db, ShipmentArgs(termo="Jo%"))["total"] == 0


def test_linked_and_legacy_codes_deduplicated_actual_delivery_status_wins(setup):
    factory, _, _ = setup
    with factory() as db:
        p = Pedido(numero_pedido="PED-1", descricao="Test", valor_total=1, cliente_nome="Maria", status="ENVIADO", codigo_rastreio="CODE1")
        db.add(p); db.flush()
        shipment(db, "CODE1", name="Maria", status="ENTREGUE", pedido_id=p.id)
        db.add(Pedido(numero_pedido="PED-2", descricao="Test", valor_total=1, cliente_nome="Carlos", codigo_rastreio="CODE2"))
        db.flush()
        assert query_shipments(db, ShipmentArgs())["total"] == 2
        result = query_shipments(db, ShipmentArgs(situacao="em_aberto"))
        assert result["total"] == 1 and result["resultados"][0]["codigo"] == "CODE2"
        shipment(db, "CODE2", name="Carlos", ativo=False)
        assert query_shipments(db, ShipmentArgs())["total"] == 1


def test_yesterday_local_timezone_and_registered_shipment_date(setup, monkeypatch):
    factory, _, _ = setup
    monkeypatch.setattr(settings, "now", lambda: datetime(2026, 9, 21, 22, tzinfo=settings.tz))
    with factory() as db:
        shipment(db, "YESTERDAY", day=date(2026, 9, 20), ultima_atualizacao=datetime(2026, 9, 21, 23))
        shipment(db, "TODAY", day=date(2026, 9, 21))
        result = query_shipments(db, ShipmentArgs(periodo="ontem"))
        assert result["total"] == 1 and result["resultados"][0]["codigo"] == "YESTERDAY"
        for number, when in [("BEFORE", datetime(2026, 9, 20, 2, 59)), ("START", datetime(2026, 9, 20, 3)),
                             ("END", datetime(2026, 9, 21, 2, 59)), ("AFTER", datetime(2026, 9, 21, 3))]:
            db.add(Pedido(numero_pedido=number, descricao="Test", valor_total=1, created_at=when))
        db.flush()
        result = query_orders(db, OrderArgs(periodo="ontem"))
        assert {r["pedido"] for r in result["resultados"]} == {"START", "END"}
        assert query_shipments(db, ShipmentArgs(data_inicio=date(2030, 1, 1)))["total"] == 0


def test_period_validation_and_calendar_boundaries():
    today = date(2026, 9, 21)
    assert period_bounds(DatedArgs(periodo="esta_semana"), today) == (today, date(2026, 9, 27))
    assert period_bounds(DatedArgs(periodo="mes_passado"), date(2026, 1, 2)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert period_bounds(DatedArgs(periodo="este_mes"), today) == (date(2026, 9, 1), date(2026, 9, 30))
    with pytest.raises(ValueError):
        ShipmentArgs(periodo="ontem", data_inicio=today)
    with pytest.raises(ValueError):
        ShipmentArgs(limite=500)
    with pytest.raises(ValueError):
        ShipmentArgs(sql="SELECT * FROM usuarios")


def test_stock_filters_and_aggregate_units_ignore_inactive(setup):
    factory, _, _ = setup
    with factory() as db:
        db.add_all([Item(name="Camiseta Azul", sku_internal="M-1", size="M", category="Camisetas", current_stock=8,
                         stock_loja=3, stock_deposito=5, min_stock=10, sale_price=Decimal("15.90"), sale_currency="USD"),
                    Item(name="Camiseta Verde", sku_internal="M-2", size="M", current_stock=0, stock_loja=0, stock_deposito=0),
                    Item(name="Desativado", sku_internal="OFF", current_stock=100, is_active=False)])
        db.flush()
        result = query_stock(db, StockArgs(termo="Camiseta", tamanho="M", local="loja", limite=1))
        assert result["total"] == 2 and result["unidades"] == 3
        assert result["saldos_por_local"] == {"total": 8, "loja": 3, "deposito": 5}
        assert result["resultados"][0]["preco_venda"] == "15.90"
        assert query_stock(db, StockArgs(situacao="abaixo_minimo"))["total"] == 1
        assert "erro" in query_stock(db, StockArgs(situacao="abaixo_minimo", local="loja"))


def test_sales_permission_decimal_currency_and_cancelled_pdv(setup):
    factory, _, user_id = setup
    with factory() as db:
        assert "erro" in query_sales(db, SalesArgs(), user_id)
        db.get(Usuario, user_id).role = UsuarioRole.ADMIN
        vendor = Vendedor(nome="Maria", usuario_id=user_id)
        db.add(vendor); db.flush()
        for currency, amount in [(MoedaTipo.R_DOLLAR, "10.12"), (MoedaTipo.U_DOLLAR, "50.31")]:
            db.add(Venda(vendedor_id=vendor.id, moeda=currency, valor_bruto=Decimal(amount), valor_liquido=Decimal(amount), metodo_pagamento=PagamentoMetodo.CREDITO))
        db.add_all([PdvSale(vendedor_id=user_id, total_gs=Decimal("30000.01"), status="completed"),
                    PdvSale(vendedor_id=user_id, total_gs=99999, status="cancelled")]); db.flush()
        result = query_sales(db, SalesArgs(), user_id)
        assert {x["moeda"] for x in result["vendas"]["totais"]} == {"R$", "U$"}
        assert result["pdv"]["valor_total_gs"] == "30000.01"
        assert result["pdv"]["total"] == 1


def prepare_calendar(db, user_id):
    db.get(Usuario, user_id).role = UsuarioRole.ADMIN
    db.add(Vendedor(nome="Maria Souza")); db.flush()
    msg = incoming(db, user_id, "Cadastre folga para Maria em 23/09/2026", channel="telegram")
    identity = channels.authorized_identity(db, "telegram", "123")
    result = prepare_schedule(db, msg, identity, ScheduleWriteArgs(vendedor="Maria", data=date(2026, 9, 23)))
    assert "confirmacao" in result
    return db.query(AssistantAction).one(), identity


def test_calendar_preview_confirm_and_duplicate_are_idempotent(setup):
    factory, _, user_id = setup
    with factory() as db:
        action, identity = prepare_calendar(db, user_id)
        assert db.query(Folga).count() == 0
        confirm = incoming(db, user_id, "confirmo", channel="telegram")
        assert "cadastrada no ERP" in agent.respond(db, confirm, identity)
        db.flush()
        folga = db.query(Folga).one()
        assert not folga.aprovado and action.result_id == folga.id
        assert "Nenhuma alteração" in confirm_action(db, confirm, identity, action)
        msg = incoming(db, user_id, "Cadastre de novo", channel="telegram")
        assert "Já existe" in prepare_schedule(db, msg, identity, ScheduleWriteArgs(vendedor="Maria", data=folga.data))["erro"]
        assert query_schedule(db, ScheduleArgs(data_inicio=date(2026, 9, 23), data_fim=date(2026, 9, 23)))["total"] == 1


def test_calendar_wrong_conversation_expired_and_revoked_permission_cannot_write(setup):
    factory, _, user_id = setup
    with factory() as db:
        action, identity = prepare_calendar(db, user_id)
        other = incoming(db, user_id, "confirmo", channel="whatsapp")
        assert "mesma conversa" in confirm_action(db, other, identity, action)
        confirm = incoming(db, user_id, "confirmo", channel="telegram")
        identity.can_register = False
        assert "não tem permissão" in confirm_action(db, confirm, identity, action)
        identity.can_register = True
        action.created_at = utcnow() - timedelta(hours=25)
        assert "expirada" in confirm_action(db, confirm, identity, action)
        assert db.query(Folga).count() == 0


def test_calendar_vendedor_cannot_write_even_with_register_permission(setup):
    factory, _, user_id = setup
    with factory() as db:
        msg = incoming(db, user_id, "Cadastre folga")
        identity = channels.authorized_identity(db, msg.channel, msg.sender_id)
        assert "erro" in prepare_schedule(db, msg, identity, ScheduleWriteArgs(vendedor="Maria", data=date(2026, 9, 23)))
        assert db.query(AssistantAction).count() == 0


def test_tracking_two_messages_from_actual_results_and_provider_order(setup, monkeypatch):
    factory, client, _ = setup
    with factory() as db:
        shipment(db, "OY859210230BR", name="Peter", status="EM_TRANSITO")
        # Test fixture event notifications are unrelated to the reply.
        db.query(AssistantDelivery).delete(); db.commit()
    calls = iter([
        {"tool_calls": [{"id": "lookup", "type": "function", "function": {"name": "buscar_rastreios", "arguments": json.dumps({"termo": "Peter", "ordem": "priorizar_abertos"})}}]},
        {"tool_calls": [{"id": "answer", "type": "function", "function": {"name": "responder_rastreio", "arguments": json.dumps({"codigo": "OY859210230BR"})}}]},
    ])
    monkeypatch.setattr(agent, "complete", lambda _: next(calls))
    post_telegram(client, telegram_update("/eleven Qual o rastreio do Peter?"))
    assert worker.process_inbox()
    with factory() as db:
        deliveries = db.query(AssistantDelivery).order_by(AssistantDelivery.created_at).all()
        assert len(deliveries) == 2
        assert deliveries[0].text == "OY859210230BR" and deliveries[1].depends_on_id == deliveries[0].id
        assert "Status: Em trânsito" in deliveries[1].text
        deliveries[0].available_at = utcnow() + timedelta(minutes=1)
        db.commit()
    sent = []
    monkeypatch.setattr(worker, "send_delivery", lambda d: sent.append(d.text) or str(len(sent)))
    assert worker.process_outbox() is False  # second cannot jump ahead during first's backoff
    with factory() as db:
        db.query(AssistantDelivery).filter_by(depends_on_id=None).update({"available_at": utcnow()}); db.commit()
    assert worker.process_outbox() and worker.process_outbox()
    assert sent[0] == "OY859210230BR" and "Status: Em trânsito" in sent[1]
    assert not worker.process_outbox()


def test_unverified_tracking_code_cannot_be_sent_as_verified_result(setup, monkeypatch):
    factory, _, user_id = setup
    replies = iter([
        {"tool_calls": [{"id": "fake", "type": "function", "function": {"name": "responder_rastreio", "arguments": '{"codigo":"FAKE123"}'}}]},
        {"content": "Não encontrei um rastreio identificado."},
    ])
    monkeypatch.setattr(agent, "complete", lambda _: next(replies))
    with factory() as db:
        msg = incoming(db, user_id, "Qual o rastreio?")
        answer = agent.respond(db, msg, channels.authorized_identity(db, msg.channel, msg.sender_id))
        assert "FAKE123" not in str(answer)


def test_calendar_write_rolls_back_if_processing_fails(setup, monkeypatch):
    factory, client, user_id = setup
    with factory() as db:
        action, identity = prepare_calendar(db, user_id)
        action_id = action.id
        db.commit()
    post_telegram(client, telegram_update(f"/confirmar {action_id}"))
    original = worker.respond
    def fail_after_confirm(db, message, identity):
        original(db, message, identity)
        raise agent.AgentError("simulated_processing_failure")
    monkeypatch.setattr(worker, "respond", fail_after_confirm)
    # The setup message itself is not part of this confirmation test.
    with factory() as db:
        db.query(AssistantMessage).filter(AssistantMessage.id == db.get(AssistantAction, action_id).source_message_id).update({"status": "done"})
        db.commit()
    assert worker.process_inbox()
    with factory() as db:
        assert db.query(Folga).count() == 0
        assert db.get(AssistantAction, action_id).status == "draft"


def test_calendar_confirmation_with_multiple_previews_requires_id(setup):
    factory, _, user_id = setup
    with factory() as db:
        action, identity = prepare_calendar(db, user_id)
        msg = incoming(db, user_id, "Cadastre outra", channel="telegram")
        prepare_schedule(db, msg, identity, ScheduleWriteArgs(vendedor="Maria", data=date(2026, 9, 25)))
        confirm = incoming(db, user_id, "confirmo", channel="telegram")
        assert "Há mais de uma prévia" in agent.respond(db, confirm, identity)
        assert db.query(Folga).count() == 0


def test_normal_telegram_followups_and_confirmations_need_no_commands(setup):
    for text in ("Últimos cinco envios", "E ontem?", "Quem folga amanhã?", "Cadastre folga para Maria amanhã", "confirmo", "cancela"):
        assert channels.telegram_message(telegram_update(text)).should_reply


def test_group_service_events_do_not_trigger_conversation(setup):
    update = telegram_update("")
    update["message"]["new_chat_members"] = [{"id": 999, "is_bot": True}]
    assert channels.telegram_message(update) is None
    update["message"].pop("new_chat_members")
    update["message"]["photo"] = [{"file_id": "image-test"}]
    assert channels.telegram_message(update).text.startswith("[Mídia recebida.")


def test_natural_cancel_and_note_confirmation(setup):
    factory, _, user_id = setup
    with factory() as db:
        action, identity = prepare_calendar(db, user_id)
        cancel = incoming(db, user_id, "cancela", channel="telegram")
        assert "cancelado" in agent.respond(db, cancel, identity)
        assert action.status == "cancelled" and db.query(Folga).count() == 0
        from app.services.assistant_tools import draft_note
        note_msg = incoming(db, user_id, "Recebemos a devolução da Ana", channel="telegram")
        draft_note(db, note_msg, identity, "devolucao", note_msg.text)
        confirm = incoming(db, user_id, "confirmo", channel="telegram")
        assert "salvo na memória" in agent.respond(db, confirm, identity)


def test_long_answers_are_split_without_discarding_the_end():
    from app.services.assistant_replies import text_reply
    content = "Linha com dados.\n" * 500 + "Última linha relevante."
    result = text_reply(content, "telegram")
    assert len(result.parts) > 1
    assert all(len(x) <= 3500 for x in result.parts)
    assert result.parts[-1].endswith("Última linha relevante.")
