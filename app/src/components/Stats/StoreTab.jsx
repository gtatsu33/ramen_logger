import { useState, useMemo, useEffect } from 'react'
import { PhotoGrid } from '../PhotoGrid'
import { StoreMap } from '../StoreMap'

export function StoreTab({ entries, stores, onClickEntry }) {
  const availableYears = useMemo(() => {
    const years = [...new Set(entries.map(e => e.date.slice(0, 4)))].sort().reverse()
    return years
  }, [entries])

  const [selectedYear, setSelectedYear] = useState('')

  useEffect(() => {
    if (availableYears.length === 0) return
    setSelectedYear(prev =>
      prev && availableYears.includes(prev) ? prev : availableYears[0]
    )
  }, [availableYears])

  const storeGroups = useMemo(() => {
    const yearEntries = entries.filter(e => e.date.slice(0, 4) === selectedYear)
    const counts = {}
    yearEntries.forEach(e => {
      const name = e.stores?.name ?? '不明'
      if (!counts[name]) counts[name] = []
      counts[name].push(e)
    })
    return Object.entries(counts).sort(([, a], [, b]) => b.length - a.length)
  }, [entries, selectedYear])

  return (
    <div>
      <select
        className="year-select"
        value={selectedYear}
        onChange={e => setSelectedYear(e.target.value)}
      >
        {availableYears.map(y => <option key={y} value={y}>{y}年</option>)}
      </select>

      {storeGroups.map(([storeName, storeEntries]) => {
        const photoEntries = storeEntries
          .filter(e => e.photo_path)
          .sort((a, b) => b.date.localeCompare(a.date))
        return (
          <div key={storeName}>
            <p className="group-label">{storeName} · {storeEntries.length}件</p>
            {photoEntries.length > 0 && (
              <PhotoGrid entries={photoEntries} onClickEntry={onClickEntry} />
            )}
          </div>
        )
      })}

      <p className="group-label" style={{ marginTop: '2rem' }}>登録済みの店舗</p>
      <StoreMap stores={stores} />
      <ul style={{ padding: '0 0 0 1rem', margin: '0.75rem 0 0', color: 'var(--muted)', fontSize: '0.875rem' }}>
        {stores.map(s => <li key={s.id} style={{ padding: '3px 0' }}>{s.name}</li>)}
      </ul>
    </div>
  )
}
