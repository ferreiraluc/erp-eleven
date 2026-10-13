import io
import uuid
import pytest
from pypdf import PdfReader
from app.schemas.address_book import LayoutConfig
from app.services.address_layouts import TEMPLATES, select_layout
from app.services.assistant_printing import AddressArgs, render_address


@pytest.mark.parametrize('template', TEMPLATES)
@pytest.mark.parametrize('country', ['BR', 'PY'])
def test_all_presentations_preserve_data_on_one_page(template, country):
    args = AddressArgs(pais=country, nome='Destinatária de Teste', telefone='+595 900 123456',
                       endereco='Rua de Exemplo', numero='123', bairro='Centro', complemento='Casa 2',
                       cidade='Foz do Iguaçu' if country == 'BR' else 'Asunción',
                       estado='PR' if country == 'BR' else '', cep='85855000' if country == 'BR' else '',
                       cpf='12345678901' if country == 'BR' else 'A-4.567.890', remetente='test')
    payload = dict(endereco=args.model_dump(), remetente={'nome':'Remetente Real','linhas':['Remetente Real','Rua do Remetente 45','Complemento sem estrutura']},
                   layout=LayoutConfig(template=template).model_dump())
    reader = PdfReader(io.BytesIO(render_address(payload)))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert 'Destinatária de Teste' in text and '+595 900 123456' in text
    assert 'Casa 2' in text and 'Centro' in text
    if country == 'BR':
        assert 'CPF: 123.456.789-01' in text
        assert 'Remetente Real' in text and 'Complemento sem estrutura' in text
    else:
        assert 'RUC/C.I: A-4.567.890' in text and 'REMETENTE' not in text


def test_rotation_stable_per_request_and_fixed_models():
    config = LayoutConfig().model_dump()
    key = uuid.uuid4()
    selected = select_layout(config, key)
    assert select_layout(config, key) == selected
    assert select_layout(selected, uuid.uuid4()) == selected
    assert config['rotate_templates'] is True  # Never mutate the saved configuration.
    assert {select_layout(config, uuid.UUID(int=i))['template'] for i in range(100)} == set(TEMPLATES)
    for template in TEMPLATES:
        assert select_layout(config | {'template':template,'rotate_templates':False}, key)['template'] == template


@pytest.mark.parametrize('template', TEMPLATES)
def test_py_minimal_and_omitted_document(template):
    args = AddressArgs(pais='PY', nome='Teste PY', cidade='Asunción', telefone='123456')
    payload = dict(endereco=args.model_dump(),remetente=None,layout=LayoutConfig(template=template).model_dump())
    text = PdfReader(io.BytesIO(render_address(payload))).pages[0].extract_text()
    assert 'Teste PY' in text and '123456' in text
    assert 'CPF' not in text and 'RUC/C.I' not in text and 'REMETENTE' not in text


def test_historical_snapshots_keep_classic_without_template():
    args = AddressArgs(pais='PY', nome='Teste antigo', cidade='Asunción')
    old = dict(endereco=args.model_dump(),remetente=None,layout={})
    a = PdfReader(io.BytesIO(render_address(old))).pages[0].extract_text()
    old['layout'] = {'template':'classic','rotate_templates':True}
    b = PdfReader(io.BytesIO(render_address(old))).pages[0].extract_text()
    assert a == b


@pytest.mark.parametrize('template', TEMPLATES)
def test_oversized_blocks_fail_as_validation_errors(template):
    args = AddressArgs(pais='BR',nome='Destinatário '*8,endereco='Rua Exemplo '*20,
                       cidade='Cidade '*12,estado='PR',cep='85855000',remetente='test')
    payload = dict(endereco=args.model_dump(),remetente={'nome':'Teste','linhas':['Informações do remetente ' * 6] * 10},
                   layout=LayoutConfig(template=template,font_size=24,sender_font_size=20,margin=80).model_dump())
    with pytest.raises(ValueError, match='página A4'):
        render_address(payload)
