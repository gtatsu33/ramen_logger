import { useEffect, useRef, useState } from 'react'
import { loadGoogleMaps } from '../utils/loadGoogleMaps'

export function StoreMap({ stores }) {
  const mapRef = useRef(null)
  const [loadError, setLoadError] = useState('')

  const validStores = stores.filter(s => s.latitude && s.longitude)

  useEffect(() => {
    if (validStores.length === 0 || !mapRef.current) return
    let cancelled = false

    loadGoogleMaps()
      .then(() => {
        if (cancelled || !mapRef.current) return

        const center = { lat: validStores[0].latitude, lng: validStores[0].longitude }
        const map = new google.maps.Map(mapRef.current, { center, zoom: 12 })
        const infoWindow = new google.maps.InfoWindow()

        validStores.forEach(s => {
          const marker = new google.maps.Marker({
            position: { lat: s.latitude, lng: s.longitude },
            map,
            title: s.name,
          })
          marker.addListener('click', () => {
            infoWindow.setContent(`<b>${s.name}</b>`)
            infoWindow.open(map, marker)
          })
        })
      })
      .catch(err => { if (!cancelled) setLoadError(err.message) })

    return () => { cancelled = true }
  }, [validStores.length])

  if (validStores.length === 0) return null
  if (loadError) return <p style={{ color: 'var(--danger)', fontSize: '0.875rem' }}>{loadError}</p>

  return (
    <div
      ref={mapRef}
      style={{ height: '320px', width: '100%', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)', marginTop: '0.5rem' }}
    />
  )
}
