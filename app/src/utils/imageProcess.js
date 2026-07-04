import ExifReader from 'exifreader'

export async function uploadPhoto(file, supabase) {
  const blob = await processImage(file)
  const fileName = crypto.randomUUID().replace(/-/g, '') + '.jpg'
  await supabase.storage.from('ramen-photos').upload(fileName, blob, {
    contentType: 'image/jpeg',
  })
  const { data } = supabase.storage.from('ramen-photos').getPublicUrl(fileName)
  return data.publicUrl
}

async function processImage(file) {
  const orientation = await getOrientation(file)
  const img = await loadImage(file)

  const { sw, sh, dw, dh, rotate } = getCropParams(img.naturalWidth, img.naturalHeight, orientation)

  const canvas = document.createElement('canvas')
  canvas.width = dw
  canvas.height = dh
  const ctx = canvas.getContext('2d')

  applyTransform(ctx, orientation, dw, dh)
  ctx.drawImage(img,
    (img.naturalWidth - sw) / 2, (img.naturalHeight - sh) / 2, sw, sh,
    0, 0, rotate ? dh : dw, rotate ? dw : dh
  )

  return await canvasToBlob(canvas)
}

async function getOrientation(file) {
  try {
    const tags = await ExifReader.load(file, { expanded: true })
    return tags?.exif?.Orientation?.value ?? 1
  } catch {
    return 1
  }
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
    img.onerror = reject
    img.src = url
  })
}

function getCropParams(w, h, orientation) {
  const cropSize = Math.min(w, h)
  const rotate = orientation >= 5
  return {
    sw: cropSize,
    sh: cropSize,
    dw: 512,
    dh: 512,
    rotate,
  }
}

function applyTransform(ctx, orientation, dw, dh) {
  switch (orientation) {
    case 2: ctx.transform(-1, 0, 0, 1, dw, 0); break
    case 3: ctx.transform(-1, 0, 0, -1, dw, dh); break
    case 4: ctx.transform(1, 0, 0, -1, 0, dh); break
    case 5: ctx.transform(0, 1, 1, 0, 0, 0); break
    case 6: ctx.transform(0, 1, -1, 0, dh, 0); break
    case 7: ctx.transform(0, -1, -1, 0, dh, dw); break
    case 8: ctx.transform(0, -1, 1, 0, 0, dw); break
    default: break
  }
}

function canvasToBlob(canvas) {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.80))
}
