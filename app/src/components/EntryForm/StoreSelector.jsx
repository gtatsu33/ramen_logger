export function StoreSelector({ stores, selectedStoreId, onChange }) {
  return (
    <div className="field">
      <label>お店を選択</label>
      <select value={selectedStoreId} onChange={e => onChange(e.target.value)}>
        <option value="new">新しいお店を登録</option>
        {stores.map(s => (
          <option key={s.id} value={String(s.id)}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  )
}
