/**
 * 既存写真の一括変換バッチ (spec.txt 付録A)
 *
 * 処理内容:
 *   - entries の photo_path 画像を 512×512 正方形クロップに変換して上書き
 *   - thumb_ プレフィックスのサムネイルファイルを削除
 *
 * 事前準備:
 *   cd scripts
 *   npm install @supabase/supabase-js sharp
 *
 * 実行方法:
 *   SUPABASE_URL=https://xxx.supabase.co \
 *   SUPABASE_KEY=eyJ... \
 *   node convert_photos.mjs
 *
 * 注意: 上書き前に Supabase Storage のバックアップを推奨
 */

import { createClient } from '@supabase/supabase-js'
import sharp from 'sharp'

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_KEY
const BUCKET = 'ramen-photos'

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('SUPABASE_URL と SUPABASE_KEY を環境変数に設定してください。')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

async function convertTo512(buffer) {
  return sharp(buffer)
    .rotate()                                          // EXIF orientation を自動補正
    .resize(512, 512, { fit: 'cover', position: 'centre' })  // 中央正方形クロップ
    .jpeg({ quality: 80 })
    .toBuffer()
}

async function main() {
  // 1. entries の photo_path を全件取得
  console.log('エントリーを取得中...')
  const { data: entries, error: fetchError } = await supabase
    .from('entries')
    .select('id, photo_path')

  if (fetchError) { console.error(fetchError.message); process.exit(1) }

  const targets = entries.filter(e => e.photo_path)
  console.log(`対象: ${targets.length} 件\n`)

  let success = 0, skip = 0

  // 2. 各画像を変換して上書きアップロード
  for (const entry of targets) {
    const fileName = entry.photo_path.split('/').pop().split('?')[0]
    process.stdout.write(`[${success + skip + 1}/${targets.length}] ${fileName} ... `)

    // ダウンロード
    const { data: fileData, error: dlError } = await supabase.storage
      .from(BUCKET).download(fileName)

    if (dlError) {
      console.log(`スキップ (ダウンロード失敗: ${dlError.message})`)
      skip++; continue
    }

    // 変換
    let converted
    try {
      const inputBuffer = Buffer.from(await fileData.arrayBuffer())
      converted = await convertTo512(inputBuffer)
    } catch (err) {
      console.log(`スキップ (変換失敗: ${err.message})`)
      skip++; continue
    }

    // 上書きアップロード
    const { error: upError } = await supabase.storage
      .from(BUCKET).upload(fileName, converted, {
        contentType: 'image/jpeg',
        upsert: true,
      })

    if (upError) {
      console.log(`スキップ (アップロード失敗: ${upError.message})`)
      skip++; continue
    }

    console.log('✓')
    success++
  }

  console.log(`\n変換完了: ${success} 件成功 / ${skip} 件スキップ`)

  // 3. サムネイルファイルを削除
  console.log('\nサムネイルファイルを削除中...')
  const { data: allFiles } = await supabase.storage.from(BUCKET).list('', { limit: 1000 })
  const thumbFiles = (allFiles ?? []).filter(f => f.name.startsWith('thumb_'))

  if (thumbFiles.length === 0) {
    console.log('サムネイルファイルなし')
  } else {
    const { error: rmError } = await supabase.storage
      .from(BUCKET).remove(thumbFiles.map(f => f.name))
    if (rmError) {
      console.warn(`サムネイル削除エラー: ${rmError.message}`)
    } else {
      console.log(`${thumbFiles.length} 件のサムネイルを削除しました`)
    }
  }

  console.log('\n完了！')
}

main()
