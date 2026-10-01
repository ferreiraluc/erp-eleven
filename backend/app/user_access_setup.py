"""Idempotent provisioning of the five accounts requested by the store owner.

Dry run by default. With --apply, read the initial password from getpass or
ELEVEN_INITIAL_PASSWORD. Existing individual passwords are never reset on reruns.
Run only after the access migration. User IDs and bot identities are preserved.
"""
import argparse
import getpass
import os
import uuid

from sqlalchemy import func
from .database import SessionLocal
from .models.usuario import Usuario, UsuarioRole
from .models.vendedor import Vendedor
from .services.user_sessions import get_password_hash, revoke_all
from .services.user_audit import bind_actor, record

EMPLOYEES = (
    ('Lucas','lucas@eleven.com','all',('Lucas',),('admin@loja.com',)),
    ('Wissam','wissam@eleven.com','all',('Wissam','Wiss'),('whatsapp-595972974734@assistant.invalid',)),
    ('Denis','denis@eleven.com','own',('Denis',),('whatsapp-595972394123@assistant.invalid',)),
    ('Sol','sol@eleven.com','own',('Sol',),('whatsapp-595973665736@assistant.invalid',)),
    ('Junior','junior@eleven.com','own',('Junior','Juninho'),('whatsapp-595992933955@assistant.invalid',)),
)


def plan(db):
    result=[]
    for name,email,scope,aliases,legacy in EMPLOYEES:
        matches=db.query(Usuario).filter(func.lower(Usuario.email).in_((email,*legacy))).all()
        if len(matches)>1:
            raise ValueError(f'{name}: há conta individual e legado separados; revise os vínculos antes de consolidar.')
        vendors=db.query(Vendedor).filter(Vendedor.ativo.is_(True),func.lower(Vendedor.nome).in_([v.lower() for v in aliases])).all()
        if len(vendors)!=1:
            raise ValueError(f'{name}: esperado exatamente um vendedor ativo; encontrados {len(vendors)}.')
        user=matches[0] if matches else None
        role=UsuarioRole.ADMIN if name=='Lucas' else UsuarioRole.GERENTE
        target={'nome':name,'email':email,'role':role,'ativo':True,'sales_scope':scope,'sales_seller':name,'vendedor_id':vendors[0].id}
        result.append({'name':name,'user':user,'vendor':vendors[0],'target':target,
                       'initial_password':not user or user.email.lower()!=email,
                       'changed':not user or any(getattr(user,k)!=v for k,v in target.items())})
    return result


def provision(db, initial_password):
    rows=plan(db)
    hashed=get_password_hash(initial_password) if any(r['initial_password'] for r in rows) else None
    for row in rows:
        if not row['user']:
            row['user']=Usuario(id=uuid.uuid4(),senha_hash=hashed,**row['target'])
            db.add(row['user'])
    db.flush()
    owner=rows[0]['user']
    bind_actor(db,owner,source='setup')
    for row in rows:
        user=row['user']
        if row['changed']:
            for key,value in row['target'].items():setattr(user,key,value)
        if row['initial_password']:
            user.senha_hash=hashed
            user.must_change_password=True
        if row['changed'] or row['initial_password']:
            revoke_all(db,user)
            record(db,'access_provisioned','users',entity='usuarios',entity_id=str(user.id),
                   changes={'sales_scope':{'after':row['target']['sales_scope']}})
        row['vendor'].usuario_id=user.id
    for user in db.query(Usuario).filter(Usuario.role==UsuarioRole.ADMIN,Usuario.id!=owner.id):
        user.role=UsuarioRole.GERENTE
        revoke_all(db,user)
        record(db,'access_changed','users',entity='usuarios',entity_id=str(user.id))
    db.flush()
    return [{'name':r['name'],'email':r['target']['email'],'scope':r['target']['sales_scope'],
             'changed':r['changed'],'initial_password':r['initial_password']} for r in rows]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    with SessionLocal() as db:
        rows=plan(db)
        for r in rows:
            print(f"{r['name']}: {r['target']['email']} | vendas={r['target']['sales_scope']} | alterar={r['changed']} | senha inicial={r['initial_password']}")
        if not args.apply:
            print('Simulação: nenhuma alteração gravada. Use --apply para executar.')
            return
        password=os.environ.get('ELEVEN_INITIAL_PASSWORD') or getpass.getpass('Senha inicial: ')
        provision(db,password)
        db.commit()
        print('Contas configuradas. IDs anteriores preservados; senha inicial exige troca no próximo login.')


if __name__=='__main__':main()
