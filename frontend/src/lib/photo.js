import { BASE_URL } from './api'

// Where a profile photo can be seen (see avatar_image in accounts/views.py)
export function avatarUrl(key) {
  return key ? `${BASE_URL}/avatars/${key}/` : null
}

// Where a business logo can be seen (see logo_image in accounts/views.py)
export function logoUrl(key) {
  return key ? `${BASE_URL}/logos/${key}/` : null
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = url
  })
}

// The server accepts up to 300 KB; stay well below it
const MAX_LOGO_BYTES = 250 * 1024

// Turns a logo into a PNG of at most `maxSide` pixels, keeping its whole shape and see-through parts.
// A busy picture that makes too big a PNG becomes a JPEG on white instead.
export async function logoToDataUrl(file, maxSide = 400) {
  const url = URL.createObjectURL(file)
  try {
    const image = await loadImage(url)
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(image.naturalWidth * scale)
    canvas.height = Math.round(image.naturalHeight * scale)
    const context = canvas.getContext('2d')
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    const png = canvas.toDataURL('image/png')
    // Base64 is about 4 characters for every 3 bytes
    if ((png.length * 3) / 4 <= MAX_LOGO_BYTES) return png
    context.globalCompositeOperation = 'destination-over'
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.9)
  } finally {
    URL.revokeObjectURL(url)
  }
}

// Turns a photo from the phone into a small square JPEG (centre part), ready to upload.
// Drawing it again also removes hidden details such as the place where it was taken.
export async function photoToDataUrl(file, size = 256) {
  const url = URL.createObjectURL(file)
  try {
    const image = await loadImage(url)
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
