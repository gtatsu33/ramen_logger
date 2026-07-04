import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabase'

export function useEntries() {
  const [entries, setEntries] = useState([])

  const fetchEntries = useCallback(async () => {
    const { data } = await supabase
      .from('entries')
      .select('*, stores(name, latitude, longitude)')
      .order('date', { ascending: false })
    if (data) setEntries(data)
  }, [])

  useEffect(() => { fetchEntries() }, [fetchEntries])

  const insertEntry = async (payload) => {
    await supabase.from('entries').insert({
      ...payload,
      created_at: new Date().toISOString(),
    })
    await fetchEntries()
  }

  return { entries, fetchEntries, insertEntry }
}
