"""Plan one explicit customer merge; use --apply --expected-plan to persist it."""
import argparse
import json
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from .database import SessionLocal
from .services.customer_maintenance import merge_customers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['merge'])
    parser.add_argument('--target', type=uuid.UUID, required=True, help='Cadastro principal que continuará visível')
    parser.add_argument('--source', type=uuid.UUID, required=True, help='Cadastro que será preservado como referência ao principal')
    parser.add_argument('--apply', action='store_true', help='Aplicar o par explicitamente revisado; por padrão apenas simula')
    parser.add_argument('--expected-plan', help='plan_token retornado pela simulação imediatamente anterior')
    parser.add_argument('--reviewed-conflicts', action='store_true', help='Somente após o proprietário confirmar dados divergentes; mantém os dados do destino')
    args = parser.parse_args(argv)
    if args.apply and not args.expected_plan:
        parser.error('--apply exige --expected-plan retornado pela simulação')
    with SessionLocal() as db:
        try:
            if args.apply:
                from .models.usuario import Usuario
                from .services.access_policy import OWNER_EMAIL
                from .services.user_audit import bind_actor
                owner = db.query(Usuario).filter_by(email=OWNER_EMAIL, ativo=True).one_or_none()
                from .services.access_policy import is_owner
                if not owner or not is_owner(owner):
                    raise SystemExit('Administrador ativo não encontrado para registrar a auditoria.')
                bind_actor(db, owner, source='reconciliation')
            result = merge_customers(db, args.target, args.source, apply=args.apply, expected_plan=args.expected_plan, reviewed_conflicts=args.reviewed_conflicts)
            if args.apply:
                db.commit()
            else:
                db.rollback()
        except HTTPException as error:
            db.rollback()
            raise SystemExit(error.detail) from None
        except SQLAlchemyError:
            db.rollback()
            raise SystemExit('Não foi possível confirmar o resultado no banco. Confira o par antes de repetir; nenhum dado do cadastro foi exibido.') from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
