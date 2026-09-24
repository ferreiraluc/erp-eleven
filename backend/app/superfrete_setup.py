"""Run on the deployed server: python -m app.superfrete_setup --url https://BACKEND/api/freight/webhooks/superfrete"""
import argparse
from urllib.parse import urlsplit
from .database import SessionLocal
from .models.address_book import FreightWebhook
from .services import superfrete as sf
from .services.freight_webhook import cipher, signing_secret


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    args=parser.parse_args()
    url=urlsplit(args.url)
    if url.scheme!='https' or not url.netloc or url.path!='/api/freight/webhooks/superfrete' or url.query or url.fragment:
        raise SystemExit('Informe a URL HTTPS pública do webhook SuperFrete do ERP.')
    with SessionLocal() as db:
        old=db.get(FreightWebhook,sf.environment())
        if old and old.url==args.url and signing_secret(db):
            print('Webhook já configurado; nenhuma duplicação.');return
        # Never rotate/delete an existing app automatically.
        if old:raise SystemExit('Já existe configuração. Confira o webhook antes de alterá-lo.')
        result=sf.call('POST','webhook',{'name':'ERP Eleven - etiquetas','url':args.url,
            'events':['order.generated','order.released','order.cancelled','order.posted','order.delivered']})
        if isinstance(result.get('data'),dict):result=result['data']
        if not result.get('id') or not result.get('secret_token'):
            raise SystemExit('Criação sem chave de assinatura confirmada. Confira o webhook na SuperFrete antes de repetir.')
        db.add(FreightWebhook(environment=sf.environment(),provider_id=str(result['id']),url=args.url,
            secret_encrypted=cipher().encrypt(result['secret_token'].encode()).decode()))
        db.commit()
        print('Webhook SuperFrete configurado. Chave cifrada no banco; nenhuma etiqueta comprada.')


if __name__=='__main__':main()
