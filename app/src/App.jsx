import { useStores } from './hooks/useStores'
import { useEntries } from './hooks/useEntries'

function App() {
  const { stores } = useStores()
  const { entries } = useEntries()

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h2>🍜 ラーメンロガー</h2>

      <h3>店舗一覧（{stores.length}件）</h3>
      <ul>
        {stores.map(s => (
          <li key={s.id}>{s.name}</li>
        ))}
      </ul>

      <h3>記録一覧（{entries.length}件）</h3>
      <ul>
        {entries.map(e => (
          <li key={e.id}>
            {e.date} / {e.stores?.name} / {e.ramen_name} / {e.score}点
          </li>
        ))}
      </ul>
    </div>
  )
}

export default App
