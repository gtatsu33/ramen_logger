/**
 * Supabase Storage の写真を全件ローカルにダウンロードする
 * entries テーブルの photo_path / thumbnail_path URL から直接取得する方式
 *
 * 実行方法:
 *   cd scripts
 *   npm install   # 初回のみ
 *   $env:SUPABASE_URL="https://xxx.supabase.co"
 *   $env:SUPABASE_KEY="eyJ..."
 *   node backup_photos.mjs
 *
 * ダウンロード先: scripts/backup/
 */

import { createClient } from '@supabase/supabase-js'
import { writeFileSync, mkdirSync } from 'fs'
import { join } from 'path'

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_KEY
const BACKUP_DIR = './backup'

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('SUPABASE_URL と SUPABASE_KEY を環境変数に設定してください。')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

async function downloadFile(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return Buffer.from(await res.arrayBuffer())
}

async function main() {
  mkdirSync(BACKUP_DIR, { recursive: true })

  console.log('entriesからURL一覧を取得中...')
  const { data: entries, error } = await supabase
    .from('entries')
    .select('id, photo_path, thumbnail_path')

  if (error) { console.error(error.message); process.exit(1) }

  // photo_path と thumbnail_path の両方を収集（重複除去）
  const urls = new Set()
  for (const e of entries) {
    if (e.photo_path) urls.add(e.photo_path)
    if (e.thumbnail_path) urls.add(e.thumbnail_path)
  }

  const urlList = [...urls]
  console.log(`対象: ${urlList.length} ファイル\n`)

  let success = 0, skip = 0

  for (const url of urlList) {
    const fileName = url.split('/').pop().split('?')[0]
    process.stdout.write(`[${success + skip + 1}/${urlList.length}] ${fileName} ... `)

    try {
      const buffer = await downloadFile(url)
      writeFileSync(join(BACKUP_DIR, fileName), buffer)
      console.log('✓')
      success++
    } catch (err) {
      console.log(`スキップ (${err.message})`)
      skip++
    }
  }

  console.log(`\n完了: ${success} 件保存 / ${skip} 件スキップ`)
  console.log(`保存先: scripts/backup/`)
}

main()
