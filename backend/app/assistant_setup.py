"""Explicit setup commands. Credentials are read from the environment, never printed."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .config import settings


def telegram(method, payload=None):
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN no ambiente do servidor.")
    try:
        response = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
                                 json=payload or {}, timeout=(5, 20))
        if response.status_code != 200:
            raise SystemExit(f"Telegram retornou HTTP {response.status_code}. Verifique token/webhook sem expor a chave.")
        body = response.json()
        if not body.get("ok"):
            raise SystemExit("Telegram recusou a operação.")
        return body["result"]
    except (requests.RequestException, ValueError, KeyError):
        raise SystemExit("Não foi possível concluir a chamada ao Telegram.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "telegram-info", "telegram-discover", "telegram-webhook",
                                            "shipping-defaults-show", "shipping-defaults-set"])
    parser.add_argument("--url", help="URL HTTPS pública do webhook Telegram")
    parser.add_argument("--defaults-file", help="JSON do padrão de frete explicitamente autorizado por Lucas")
    parser.add_argument("--expected-revision", type=int, help="Revisão atual; zero apenas para o primeiro cadastro")
    args = parser.parse_args()
    if args.command.startswith('shipping-defaults-'):
        from fastapi import HTTPException
        from pydantic import ValidationError
        from sqlalchemy.exc import SQLAlchemyError
        from .database import SessionLocal
        from .models.usuario import Usuario
        from .services.access_policy import OWNER_EMAIL
        from .services.assistant_routines import RoutineArgs, get_routine, save_routine
        from .services.user_audit import bind_actor
        if args.command == 'shipping-defaults-set' and (
                not args.defaults_file or args.expected_revision is None or args.expected_revision < 0):
            parser.error('Informe --defaults-file e --expected-revision; a atualização não é automática.')
        try:
            with SessionLocal() as db:
                if args.command == 'shipping-defaults-show':
                    print(json.dumps({'padrao': get_routine(db)}, ensure_ascii=False, indent=2))
                    return
                path=Path(args.defaults_file)
                if path.stat().st_size > 65536:
                    raise ValueError('Arquivo de padrão muito grande.')
                payload=RoutineArgs.model_validate(json.loads(path.read_text(encoding='utf-8')))
                owner=db.query(Usuario).filter(Usuario.email==OWNER_EMAIL, Usuario.ativo.is_(True)).one_or_none()
                if not owner:raise SystemExit('Proprietário ativo não encontrado. Nenhuma alteração realizada.')
                bind_actor(db,owner,source='cli')
                saved=save_routine(db,payload,user_id=owner.id,expected_revision=args.expected_revision)
                db.commit()
                print(json.dumps({'salvo':True,'revisao':saved['revision'],'ativo':saved['active']}))
        except HTTPException as error:
            raise SystemExit(str(error.detail)) from None
        except (OSError,ValueError,ValidationError):
            raise SystemExit('Confira o JSON do padrão. Nenhuma alteração realizada.') from None
        except SQLAlchemyError:
            raise SystemExit('Não foi possível acessar o banco; confira a configuração sem expor credenciais.') from None
        return
    if args.command == "check":
        keys = ["DEEPSEEK_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM",
                "TWILIO_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET",
                "TELEGRAM_BOT_USERNAME", "TELEGRAM_GROUP_ID"]
        print(json.dumps({"enabled": settings.ASSISTANT_ENABLED,
                          "configured": {key: bool(getattr(settings, key)) for key in keys}}, indent=2))
    elif args.command == "telegram-info":
        bot = telegram("getMe")
        webhook = telegram("getWebhookInfo")
        print(json.dumps({"bot_id": bot["id"], "username": bot.get("username"),
                          "receives_all_group_messages": bot.get("can_read_all_group_messages", False),
                          "webhook_configured": bool(webhook.get("url")),
                          "pending_updates": webhook.get("pending_update_count", 0)}, indent=2))
    elif args.command == "telegram-discover":
        # Works before setWebhook. Never delete a live webhook to inspect updates.
        if telegram("getWebhookInfo").get("url"):
            raise SystemExit("Já existe webhook. Não foi removido. Consulte os IDs obtidos na configuração inicial.")
        updates = telegram("getUpdates", {"timeout": 0, "limit": 100, "allowed_updates": ["message"]})
        found = set()
        for update in updates:
            message = update.get("message", {})
            chat, sender = message.get("chat", {}), message.get("from", {})
            if chat.get("id") and sender.get("id"):
                found.add((chat["id"], chat.get("type", ""), sender["id"]))
        print(json.dumps([{"chat_id": c, "type": t, "user_id": u} for c, t, u in sorted(found)], indent=2))
    elif args.command == "telegram-webhook":
        url = urlsplit(args.url or "")
        if url.scheme != "https" or not url.netloc or url.path != "/api/assistant/webhooks/telegram" or url.query or url.fragment:
            raise SystemExit("Informe --url https://SEU-BACKEND/api/assistant/webhooks/telegram")
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", settings.TELEGRAM_WEBHOOK_SECRET):
            raise SystemExit("Configure TELEGRAM_WEBHOOK_SECRET com 32 a 256 caracteres alfanuméricos, _ ou -.")
        if not settings.TELEGRAM_GROUP_ID or not settings.TELEGRAM_BOT_USERNAME:
            raise SystemExit("Configure TELEGRAM_GROUP_ID e TELEGRAM_BOT_USERNAME primeiro.")
        bot = telegram("getMe")
        if bot.get("username", "").lower() != settings.TELEGRAM_BOT_USERNAME.lower():
            raise SystemExit("O token e o username configurados pertencem a bots diferentes.")
        telegram("setWebhook", {"url": args.url, "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
                                "allowed_updates": ["message", "callback_query"], "drop_pending_updates": False})
        print("Webhook configurado. Nenhuma mensagem foi enviada e nenhuma atualização pendente foi descartada.")


if __name__ == "__main__":
    main()
