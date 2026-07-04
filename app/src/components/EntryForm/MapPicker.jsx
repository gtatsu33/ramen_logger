import { useEffect, useRef, useState } from 'react'
import { loadGoogleMaps } from '../../utils/loadGoogleMaps'

export function MapPicker({ onSelect }) {
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const [info, setInfo] = useState('地図をクリックして場所を選択してください。')
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let cancelled = false

    loadGoogleMaps()
      .then(() => {
        if (cancelled || !mapRef.current) return

        const defaultCenter = { lat: 35.681236, lng: 139.767125 }
        const map = new google.maps.Map(mapRef.current, { center: defaultCenter, zoom: 15 })

        if (navigator.geolocation) {
          setInfo('現在地を取得しています...')
          navigator.geolocation.getCurrentPosition(
            pos => {
              if (cancelled) return
              const current = { lat: pos.coords.latitude, lng: pos.coords.longitude }
              map.setCenter(current)
              new google.maps.Marker({
                position: current, map,
                icon: {
                  path: google.maps.SymbolPath.CIRCLE,
                  scale: 7,
                  fillColor: '#4285F4', fillOpacity: 1,
                  strokeColor: '#fff', strokeWeight: 2,
                },
              })
              setInfo('地図をクリックして場所を選択してください。')
            },
            () => { if (!cancelled) setInfo('地図をクリックして場所を選択してください。') },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
          )
        }

        map.addListener('click', e => {
          const lat = e.latLng.lat()
          const lng = e.latLng.lng()
          if (markerRef.current) markerRef.current.setMap(null)
          markerRef.current = new google.maps.Marker({ position: e.latLng, map })
          setInfo('周辺の店舗を検索中...')

          const svc = new google.maps.places.PlacesService(map)

          const finalize = (name) => {
            setInfo(name ? `📍 ${name}` : `緯度 ${lat.toFixed(6)}, 経度 ${lng.toFixed(6)}（店舗名未検出）`)
            onSelect(lat, lng, name)
          }

          const searchRestaurant = () => {
            svc.nearbySearch({
              location: e.latLng, rankBy: google.maps.places.RankBy.DISTANCE, type: 'restaurant',
            }, (results, status) => {
              if (status === google.maps.places.PlacesServiceStatus.OK && results.length > 0) {
                const dist = google.maps.geometry.spherical.computeDistanceBetween(e.latLng, results[0].geometry.location)
                finalize(dist <= 50 ? results[0].name : '')
              } else {
                finalize('')
              }
            })
          }

          svc.nearbySearch({
            location: e.latLng, rankBy: google.maps.places.RankBy.DISTANCE, keyword: 'ラーメン',
          }, (results, status) => {
            if (status === google.maps.places.PlacesServiceStatus.OK && results.length > 0) {
              const dist = google.maps.geometry.spherical.computeDistanceBetween(e.latLng, results[0].geometry.location)
              if (dist <= 20) { finalize(results[0].name); return }
            }
            searchRestaurant()
          })
        })
      })
      .catch(err => { if (!cancelled) setLoadError(err.message) })

    return () => { cancelled = true }
  }, [onSelect])

  if (loadError) return <p style={{ color: 'var(--danger)', fontSize: '0.875rem' }}>{loadError}</p>

  return (
    <div>
      <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '0 0 6px' }}>{info}</p>
      <div
        ref={mapRef}
        style={{ height: '280px', width: '100%', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)' }}
      />
    </div>
  )
}
