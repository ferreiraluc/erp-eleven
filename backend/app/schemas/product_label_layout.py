"""Bounded design objects for the existing 60 × 30 mm raster pipeline."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Element(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,40}$')
    x: int = Field(ge=0, le=479)
    y: int = Field(ge=0, le=239)


class TextElement(Element):
    type: Literal['text'] = 'text'
    field: Literal['title', 'name', 'size', 'color', 'code', 'price', 'barcode', 'text']
    width: int = Field(ge=16, le=480)
    height: int = Field(ge=8, le=240)
    font_size: int = Field(default=16, ge=10, le=72)
    font: Literal['arimo', 'barlow'] = 'arimo'
    bold: bool = False
    align: Literal['left', 'center', 'right'] = 'left'
    uppercase: bool = True
    lines: int = Field(default=1, ge=1, le=4)
    text: str = Field(default='', max_length=100)
    visible: bool = True


class QrElement(Element):
    type: Literal['qr'] = 'qr'
    module_size: int = Field(default=3, ge=2, le=5)


class LineElement(Element):
    type: Literal['line'] = 'line'
    width: int = Field(ge=1, le=480)
    height: int = Field(default=2, ge=1, le=8)
    visible: bool = True


DesignElement = Annotated[TextElement | QrElement | LineElement, Field(discriminator='type')]


def element_size(element):
    if element.type == 'qr':
        # Fixed version 3: 29 modules plus a four-module quiet zone on each side.
        return (37 * element.module_size,) * 2
    return element.width, element.height


class LabelDesign(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: Literal[1] = 1
    elements: list[DesignElement] = Field(min_length=2, max_length=16)

    @model_validator(mode='after')
    def printable(self):
        if len({e.id for e in self.elements}) != len(self.elements):
            raise ValueError('Cada campo precisa de uma identificação diferente.')
        qr = [e for e in self.elements if e.type == 'qr']
        codes = [e for e in self.elements if e.type == 'text' and e.field == 'code' and e.visible]
        if len(qr) != 1 or len(codes) != 1:
            raise ValueError('Mantenha um QR e um código interno visível na etiqueta.')
        if codes[0].width < 90 or codes[0].height < 12 or codes[0].lines != 1:
            raise ValueError('O código interno precisa de uma linha com pelo menos 11,25 × 1,5 mm.')
        q = qr[0]
        qw, qh = element_size(q)
        for e in self.elements:
            w, h = element_size(e)
            if e.x + w > 480 or e.y + h > 240:
                raise ValueError('Todos os campos devem ficar dentro do papel de 60 × 30 mm.')
            if e.type != 'qr' and e.visible and e.x < q.x + qw and e.x + w > q.x and e.y < q.y + qh and e.y + h > q.y:
                raise ValueError('Os campos não podem cobrir a área de leitura do QR.')
        return self


class LayoutInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=0, strict=True)
    config: LabelDesign

    @model_validator(mode='after')
    def clean_name(self):
        self.name = ' '.join(self.name.split())
        if not self.name:
            raise ValueError('Informe o nome do modelo.')
        return self


class DesignPreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: LabelDesign
    item_id: UUID | None = None
