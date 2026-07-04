let loadPromise = null

export function loadGoogleMaps() {
  if (window.google?.maps) return Promise.resolve()
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    window.__gmapsReady = () => { resolve(); delete window.__gmapsReady }
    const script = document.createElement('script')
    script.src =
      `https://maps.googleapis.com/maps/api/js` +
      `?key=${import.meta.env.VITE_GOOGLE_MAPS_API_KEY}` +
      `&libraries=places,geometry&callback=__gmapsReady`
    script.async = true
    script.defer = true
    script.onerror = () => { loadPromise = null; reject(new Error('Maps認証エラー: APIキーが無効か、Maps JavaScript APIが有効になっていません。')) }
    document.head.appendChild(script)
  })

  return loadPromise
}
