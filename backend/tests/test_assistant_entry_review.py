"""An AI preview authorizes the reviewed variant, not a later metadata edit."""
import pytest
from test_assistant import setup, incoming
from test_inventory_ocr import stock_app, item
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.assistant import AssistantAction
from app.models.inventory import Item, StockMovement
from app.services.assistant_channels import authorized_identity
from app.services.assistant_inventory import EntryArgs, prepare_inventory
from app.services.assistant_schedule import confirm_action


@pytest.mark.parametrize('field,value', [('size','L'),('color','Preto'),('barcode','000123'),('group_key','other-family'),('legacy',None)])
def test_entry_requires_a_new_preview_after_variant_identity_changes(stock_app,field,value):
    factory,_,uid=stock_app
    with factory() as db:
        db.get(Usuario,uid).role=UsuarioRole.GERENTE
        product=item(db,loja=3,deposito=7,size='M',color='Azul')
        message=incoming(db,uid,'Entrada de duas peças M azul',channel='telegram')
        identity=authorized_identity(db,'telegram','123')
        prepare_inventory(db,message,identity,'preparar_entrada_estoque',EntryArgs(item_id=product.id,quantidade=2,local='loja'))
        action=db.query(AssistantAction).one()
        if field=='legacy':action.payload={k:v for k,v in action.payload.items() if k!='reviewed_identity'}
        else:setattr(product,field,value)
        db.commit()
        confirm=incoming(db,uid,'confirmo',channel='telegram')
        response=confirm_action(db,confirm,identity,action)
        assert 'Nenhuma entrada registrada' in response
        assert action.status=='cancelled' and db.query(StockMovement).count()==0
        assert (product.stock_loja,product.stock_deposito,product.current_stock)==(3,7,10)
