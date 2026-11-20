/**
 * Journal photos are kept in THIS browser only (localStorage), keyed by
 * the server entry id. They are re-encoded to a small JPEG via a canvas
 * before saving, which strips EXIF metadata (camera, GPS, timestamps).
 * Nothing is uploaded to the server. Photos survive refresh on this
 * device but do not sync to other devices — matching the app's privacy
 * note on the Journal page.
 */
const KEY = (id: number) => `journal.photo.${id}`

export function getJournalPhoto(id: number): string | null {
  try {
    return localStorage.getItem(KEY(id))
  } catch {
    return null
  }
}

/** Returns false if the browser refused to store it (e.g. quota full). */
export function setJournalPhoto(id: number, dataUrl: string): boolean {
  try {
    localStorage.setItem(KEY(id), dataUrl)
    return true
  } catch {
    return false
  }
}

export function removeJournalPhoto(id: number): void {
  try {
    localStorage.removeItem(KEY(id))
  } catch {
    /* ignore */
  }
}

/**
 * Re-encode an image Blob/File to a JPEG data URL, scaled so its longest
 * side is at most `maxDim` px. Drops metadata by drawing to a canvas.
 */
export async function encodePhoto(source: Blob, maxDim = 1000, quality = 0.75): Promise<string> {
  const url = URL.createObjectURL(source)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image()
      im.onload = () => resolve(im)
      im.onerror = () => reject(new Error('decode failed'))
      im.src = url
    })
    const scale = Math.min(1, maxDim / Math.max(img.width, img.height))
    const w = Math.max(1, Math.round(img.width * scale))
    const h = Math.max(1, Math.round(img.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('no canvas context')
    ctx.drawImage(img, 0, 0, w, h)
    return canvas.toDataURL('image/jpeg', quality)
  } finally {
    URL.revokeObjectURL(url)
  }
}
