import { useState } from 'react'
import { useStores } from './hooks/useStores'
import { useEntries } from './hooks/useEntries'
import { EntryForm } from './components/EntryForm/EntryForm'
import { PhotoModal } from './components/PhotoModal'
import { StatsArea } from './components/Stats/StatsArea'
import './App.css'

function App() {
  const { stores, fetchStores } = useStores()
  const { entries, fetchEntries } = useEntries()
  const [modalEntry, setModalEntry] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const handleSaved = async () => {
    await Promise.all([fetchStores(), fetchEntries()])
    setShowForm(false)
  }

  return (
    <div>
      <header className="app-header">
        <div>
          <h1>🍜 ラーメンロガー</h1>
          <p className="caption">{entries.length}件の記録</p>
        </div>
      </header>

      <StatsArea entries={entries} stores={stores} onClickEntry={setModalEntry} />

      <button className="fab" onClick={() => setShowForm(true)} aria-label="記録を追加">＋</button>

      {showForm && (
        <div className="form-overlay" onClick={() => setShowForm(false)}>
          <div className="form-sheet" onClick={e => e.stopPropagation()}>
            <EntryForm stores={stores} onSaved={handleSaved} onCancel={() => setShowForm(false)} />
          </div>
        </div>
      )}

      <PhotoModal entry={modalEntry} onClose={() => setModalEntry(null)} />
    </div>
  )
}

export default App
