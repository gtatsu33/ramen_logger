export function PhotoModal({ entry, onClose }) {
  if (!entry) return null
  const store = entry.stores || {}

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        {entry.photo_path && (
          <img src={entry.photo_path} alt={entry.ramen_name} />
        )}
        <div className="modal-body">
          <p className="modal-title">🍜 {entry.ramen_name}</p>
          <div className="modal-meta">
            <span>📅 {entry.date}</span>
            <span>⭐ {entry.score}点</span>
            <span>📍 {store.name}</span>
          </div>
          {entry.comment && (
            <p className="modal-comment">💬 {entry.comment}</p>
          )}
          <button className="btn-primary" onClick={onClose}>閉じる</button>
        </div>
      </div>
    </div>
  )
}
