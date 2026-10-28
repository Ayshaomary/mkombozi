import { BASE_URL } from './api'

// Where a profile photo can be seen (see avatar_image in accounts/views.py)
export function avatarUrl(key) {
  return key ? `${BASE_URL}/avatars/${key}/` : null
}

// Turns a photo from the phone into a small square JPEG (centre part), ready to upload.
// Drawing it again also removes hidden details such as the place where it was taken.
export async function photoToDataUrl(file, size = 256) {
  const url = URL.createObjectURL(file)
  try {
    const image = await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = url
    })
    const side = Math.min(image.naturalWidth, image.naturalHeight)
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    canvas
      .getContext('2d')
      .drawImage(image, (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side, 0, 0, size, size)
    return canvas.toDataURL('image/jpeg', 0.85)
  } finally {
    URL.revokeObjectURL(url)
  }
}
