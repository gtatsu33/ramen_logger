import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabase'

export function useStores() {
  const [stores, setStores] = useState([])

  const fetchStores = useCallback(async () => {
    const { data } = await supabase.from('stores').select('*').order('name')
    if (data) setStores(data)
  }, [])

  useEffect(() => { fetchStores() }, [fetchStores])

  const insertStore = async (name, latitude, longitude) => {
    const { data } = await supabase.from('stores').insert({
      name,
      latitude,
      longitude,
      created_at: new Date().toISOString(),
    }).select()
    await fetchStores()
    return data[0].id
  }

  return { stores, fetchStores, insertStore }
}
