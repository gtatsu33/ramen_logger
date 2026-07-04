export function PhotoGrid({ entries, onClickEntry }) {
  if (!entries || entries.length === 0) return null

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '2px',
    }}>
      {entries.map(entry => (
        <div
          key={entry.id}
          style={{ aspectRatio: '1 / 1', overflow: 'hidden', cursor: 'pointer' }}
          onClick={() => onClickEntry(entry)}
        >
          {entry.photo_path ? (
            <img
              src={entry.photo_path}
              alt={entry.ramen_name}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transition: 'opacity 0.15s' }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            />
          ) : (
            <div style={{
              width: '100%', height: '100%',
              background: '#1c1810',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.5rem',
            }}>📷</div>
          )}
        </div>
      ))}
    </div>
  )
}
