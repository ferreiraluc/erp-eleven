from fastapi import APIRouter, Depends, HTTPException, Response
from ...config import settings
from ...dependencies import require_role
from ...models.usuario import Usuario
from ...schemas.product_photo import PhotoRequest, PhotoEditRequest, ProductPhotoResponse, PhotoEditResponse
from ...services.ocr_images import prepare_label_image, OcrImageError
from ...services import product_photo

router = APIRouter()
operator = require_role(['ADMIN', 'GERENTE'])


@router.get('/status')
def status(current_user: Usuario = Depends(operator)):
    return {'editing_available': bool(settings.OPENAI_API_KEY), 'model': settings.PRODUCT_PHOTO_IMAGE_MODEL}


def process(request, response, user, operation, fn):
    response.headers['Cache-Control'] = 'no-store'
    try:
        image = prepare_label_image(request.image)
    except OcrImageError:
        raise HTTPException(422, 'invalid_image') from None
    try:
        return product_photo.bounded_call(user.id, operation, image, fn)
    except product_photo.PhotoError as exc:
        raise HTTPException(exc.status, exc.code) from None


@router.post('/analyze', response_model=ProductPhotoResponse)
def analyze(request: PhotoRequest, response: Response, current_user: Usuario = Depends(operator)):
    return process(request, response, current_user, 'analyze', product_photo.analyze)


@router.post('/catalog', response_model=PhotoEditResponse)
def catalog(request: PhotoEditRequest, response: Response, current_user: Usuario = Depends(operator)):
    return process(request, response, current_user, 'catalog', product_photo.edit_catalog)
