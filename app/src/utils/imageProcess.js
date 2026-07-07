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
  const img = await loadImage(file)
  const cropSize = Math.min(img.naturalWidth, img.naturalHeight)

  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const ctx = canvas.getContext('2d')

  ctx.drawImage(img,
    (img.naturalWidth - cropSize) / 2,
    (img.naturalHeight - cropSize) / 2,
    cropSize, cropSize,
    0, 0, 512, 512
  )
  return await canvasToBlob(canvas)
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

function canvasToBlob(canvas) {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.80))
}
