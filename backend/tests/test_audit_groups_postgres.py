"""PostgreSQL JSON extraction, UUID fallback and grouping before pagination."""
import uuid
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.usuario import Usuario, UsuarioRole
from app.models.vendedor import Vendedor
from app.models.access import AuditEvent, now
from app.services import audit_groups
from test_access_postgres import pg  # noqa: F401


def test_postgres_grouped_pagination_and_detail_scope_preserve_raw_events(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[Usuario.__table__,Vendedor.__table__,AuditEvent.__table__])
    factory=sessionmaker(bind=isolated)
    owner=uuid.uuid4();first,second=str(uuid.uuid4()),str(uuid.uuid4())
    request=str(uuid.uuid4());stamp=now()-timedelta(minutes=1)
    try:
        with factory() as db:
            # This isolated fixture only needs the user identity; no vendor relation is used.
            db.add(Usuario(id=owner,nome='Fixture',email='audit@example.test',senha_hash='unused',role=UsuarioRole.GERENTE));db.flush()
            base=dict(user_id=owner,actor_name='Fixture',source='web',action='create',module='pdv',occurred_at=stamp)
            db.add_all([AuditEvent(**base,entity='pdv_sales',entity_id=first,request_id=request,changes={}),
                        AuditEvent(**base,entity='pdv_payments',entity_id=str(uuid.uuid4()),request_id=request,changes={}),
                        AuditEvent(**base,entity='pdv_sale_items',entity_id=str(uuid.uuid4()),request_id=str(uuid.uuid4()),changes={'_context':{'sale_id':first}}),
                        AuditEvent(**base,entity='pdv_sales',entity_id=second,request_id=str(uuid.uuid4()),changes={}),
                        AuditEvent(**base,entity='pdv_payments',entity_id=str(uuid.uuid4()),request_id=None,changes={})])
            db.commit()
            scoped=audit_groups.scope(db,now()-timedelta(days=1))
            total,groups=audit_groups.grouped(db,scoped,0,1)
            assert total==3 and len(groups)==1
            all_groups=[audit_groups.grouped(db,scoped,page,1)[1][0] for page in range(total)]
            assert len({g['key'] for g in all_groups})==3
            group=next(g for g in all_groups if g['sale_id']==first)
            assert group['event_count']==3 and len(group['samples'])==3
            details=audit_groups.details(db,scoped,group['key'],1,1)
            assert details['total']==3 and len(details['events'])==1
            assert audit_groups.operations_by_user(db,scoped)[owner]==3
            assert db.query(AuditEvent).count()==5
    finally: isolated.dispose()
