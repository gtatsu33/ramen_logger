import { useState } from 'react'
import { YearMonthTab } from './YearMonthTab'
import { StoreTab } from './StoreTab'

export function StatsArea({ entries, stores, onClickEntry }) {
  const [activeTab, setActiveTab] = useState('year-month')

  return (
    <div className="stats-section">
      <div className="tabs">
        <button
          className={`tab-btn ${activeTab === 'year-month' ? 'active' : ''}`}
          onClick={() => setActiveTab('year-month')}
        >年・月別</button>
        <button
          className={`tab-btn ${activeTab === 'store' ? 'active' : ''}`}
          onClick={() => setActiveTab('store')}
        >店舗別</button>
      </div>

      {activeTab === 'year-month' && (
        <YearMonthTab entries={entries} onClickEntry={onClickEntry} />
      )}
      {activeTab === 'store' && (
        <StoreTab entries={entries} stores={stores} onClickEntry={onClickEntry} />
      )}
    </div>
  )
}
