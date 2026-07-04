import { useState, useCallback } from 'react'
import { StoreSelector } from './StoreSelector'
import { MapPicker } from './MapPicker'
import { supabase } from '../../lib/supabase'
import { uploadPhoto } from '../../utils/imageProcess'

const today = () => new Date().toISOString().slice(0, 10)

export function EntryForm({ stores, onSaved, onCancel }) {
  const [selectedStoreId, setSelectedStoreId] = useState('new')
  const [manualName, setManualName] = useState('')
  const [mapLat, setMapLat] = useState(null)
  const [mapLng, setMapLng] = useState(null)
  const [mapName, setMapName] = useState('')
  const [lastAction, setLastAction] = useState('')
  const [visitDate, setVisitDate] = useState(today())
  const [ramenName, setRamenName] = useState('')
  const [score, setScore] = useState(4)
  const [comment, setComment] = useState('')
  const [photoFile, setPhotoFile] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [pendingSave, setPendingSave] = useState(null)
  const [showNoPhoto, setShowNoPhoto] = useState(false)

  const selectedStore = stores.find(s => String(s.id) === selectedStoreId)
  const storeName = lastAction === 'map' ? mapName : manualName

  const handleMapSelect = useCallback((lat, lng, name) => {
    setMapLat(lat)
    setMapLng(lng)
    setMapName(name)
    setLastAction('map')
  }, [])

  const handleManualNameChange = (e) => {
    setManualName(e.target.value)
    if (e.target.value) setLastAction('manual')
  }

  const resetForm = () => {
    setSelectedStoreId('new')
    setManualName('')
    setMapLat(null); setMapLng(null); setMapName(''); setLastAction('')
    setVisitDate(today())
    setRamenName('')
    setScore(4)
    setComment('')
    setPhotoFile(null)
    setError('')
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    if (!ramenName.trim()) { setError('ラーメンの名前を入力してください。'); return }
    if (selectedStoreId === 'new' && !storeName.trim()) { setError('新しいお店の名前を入力してください。'); return }
    if (!photoFile) { setShowNoPhoto(true); return }
    if (selectedStoreId === 'new') {
      setPendingSave({ storeName: storeName.trim(), storeLat: mapLat, storeLon: mapLng })
    } else {
      doSave(selectedStore.id)
    }
  }

  const doSave = async (storeId) => {
    setSaving(true)
    try {
      const photoUrl = await uploadPhoto(photoFile, supabase)
      await supabase.from('entries').insert({
        date: visitDate,
        store_id: storeId,
        ramen_name: ramenName.trim(),
        score,
        comment: comment.trim(),
        photo_path: photoUrl,
        created_at: new Date().toISOString(),
      })
      await onSaved()  // データ再取得 + フォームクローズを待つ
    } catch {
      setSaving(false)
      setError('保存に失敗しました。もう一度お試しください。')
    }
  }

  const handleConfirmNewStore = async () => {
    setSaving(true)
    try {
      const { data } = await supabase.from('stores').insert({
        name: pendingSave.storeName,
        latitude: pendingSave.storeLat,
        longitude: pendingSave.storeLon,
        created_at: new Date().toISOString(),
      }).select()
      setPendingSave(null)
      await doSave(data[0].id)
    } catch {
      setSaving(false)
      setError('保存に失敗しました。もう一度お試しください。')
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit}>
        <h2>
          記録を追加
          <button type="button" className="close-btn" onClick={onCancel}>✕</button>
        </h2>

        <StoreSelector stores={stores} selectedStoreId={selectedStoreId} onChange={setSelectedStoreId} />

        {selectedStoreId === 'new' && (
          <>
            <div className="field">
              <label>お店の名前（手入力）</label>
              <input type="text" value={manualName} onChange={handleManualNameChange} />
            </div>
            <div className="field">
              <label>📍 お店の場所を選択</label>
              <MapPicker onSelect={handleMapSelect} />
              {mapLat && (
                <p style={{ fontSize: '0.8rem', color: 'var(--gold)', marginTop: '4px' }}>
                  選択済み: 緯度 {mapLat.toFixed(6)}, 経度 {mapLng.toFixed(6)}
                </p>
              )}
            </div>
          </>
        )}

        <div className="field">
          <label>訪問日</label>
          <input type="date" value={visitDate} onChange={e => setVisitDate(e.target.value)} />
        </div>

        <div className="field">
          <label>ラーメンの名前</label>
          <input type="text" value={ramenName} onChange={e => setRamenName(e.target.value)} />
        </div>

        <div className="field">
          <label>点数</label>
          <div className="score-row">
            <input type="range" min={1} max={5} value={score} onChange={e => setScore(Number(e.target.value))} />
            <span className="score-value">{score}</span>
          </div>
        </div>

        <div className="field">
          <label>コメント</label>
          <textarea rows={3} value={comment} onChange={e => setComment(e.target.value)} />
        </div>

        <div className="field">
          <label>写真</label>
          <input type="file" accept="image/png,image/jpeg"
            onChange={e => setPhotoFile(e.target.files[0] ?? null)}
            style={{ background: 'none', border: 'none', padding: 0, color: 'var(--text)' }}
          />
        </div>

        {error && <p className="error-msg">{error}</p>}

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? '保存中...' : '保存する'}
        </button>
      </form>

      {showNoPhoto && (
        <div className="dialog-overlay">
          <div className="dialog-box">
            <h3>確認</h3>
            <p>写真がアップロードされていません。</p>
            <button className="btn-secondary" onClick={() => setShowNoPhoto(false)}>キャンセル</button>
          </div>
        </div>
      )}

      {pendingSave && (
        <div className="dialog-overlay">
          <div className="dialog-box">
            <h3>登録確認</h3>
            <p>店舗名「<strong>{pendingSave.storeName}</strong>」で登録します。よろしいですか？</p>
            <div className="dialog-btns">
              <button className="btn-primary" onClick={handleConfirmNewStore} disabled={saving}>
                {saving ? '保存中...' : 'はい'}
              </button>
              <button className="btn-secondary" onClick={() => setPendingSave(null)}>キャンセル</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
