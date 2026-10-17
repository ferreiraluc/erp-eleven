import { catalogForStorage, imageElement, preparePhoto } from './productPhoto'

export const MAX_PRODUCT_PHOTOS = 5

/** Process sequentially: five camera originals must not be decoded together. */
export async function prepareGalleryFile(file: File): Promise<string> {
  return catalogForStorage(await preparePhoto(file))
}

/** The strip renders small rasters, not five full-size decoded images. */
export async function galleryPreview(source: string): Promise<string> {
  const image = await imageElement(source)
  const canvas = document.createElement('canvas')
  try {
    const scale = Math.min(1, 128 / Math.max(image.naturalWidth, image.naturalHeight))
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    const context = canvas.getContext('2d')
    if (!context) throw new Error('invalid_image')
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.7)
  } finally {
    image.src = ''
    canvas.width = canvas.height = 1
  }
}
