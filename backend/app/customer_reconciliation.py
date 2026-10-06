"""Preview by default; --apply explicitly commits audited customer reconciliation."""
import argparse
import json
from pathlib import Path
from .database import SessionLocal
from .models.usuario import Usuario
from .services.access_policy import OWNER_EMAIL
from .services.customer_reconciliation import reconcile
from .services.user_audit import bind_actor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    with SessionLocal() as db:
        owner = db.query(Usuario).filter_by(email=OWNER_EMAIL, ativo=True).one()
        bind_actor(db, owner, source='reconciliation')
        result = reconcile(db)
        from .services.vendor_activity import reconcile_vendors
        result.update(reconcile_vendors(db))
        if args.apply: db.commit()
        else: db.rollback()
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        args.report.chmod(0o600)
    print(json.dumps({'applied': args.apply, **{key: len(value) if isinstance(value, list) else value for key, value in result.items()}}))


if __name__ == '__main__': main()
