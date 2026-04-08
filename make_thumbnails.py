import io
import os
import requests
from PIL import Image
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
BUCKET_NAME = "ramen-photos"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def make_thumbnail(file_bytes: bytes, size: int = 300) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    w, h = img.size
    crop_size = min(w, h)
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    img = img.crop((left, top, left + crop_size, top + crop_size))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def main():
    # thumbnail_pathが未設定のエントリーを取得
    res = supabase.table("entries").select("id, photo_path, thumbnail_path").execute()
    entries = [e for e in res.data if e.get("photo_path") and not e.get("thumbnail_path")]

    print(f"処理対象: {len(entries)}件")

    for entry in entries:
        entry_id = entry["id"]
        photo_url = entry["photo_path"]
        print(f"  処理中 id={entry_id} ...", end=" ")

        try:
            # オリジナル画像をダウンロード
            response = requests.get(photo_url, timeout=30)
            response.raise_for_status()

            # サムネイル生成
            thumb_bytes = make_thumbnail(response.content)

            # ファイル名はオリジナルのURLから取得してthumb_プレフィックスを付与
            original_name = photo_url.split("/")[-1].split("?")[0]
            thumb_name = f"thumb_{original_name}"

            # Supabaseにアップロード（既存ファイルがあればスキップ）
            try:
                supabase.storage.from_(BUCKET_NAME).upload(
                    thumb_name, thumb_bytes, {"content-type": "image/jpeg"}
                )
            except Exception as upload_err:
                if "already exists" in str(upload_err).lower() or "Duplicate" in str(upload_err):
                    print("(既存サムネイルを再利用)", end=" ")
                else:
                    raise

            thumb_url = supabase.storage.from_(BUCKET_NAME).get_public_url(thumb_name)

            # entriesテーブルのthumbnail_pathを更新
            supabase.table("entries").update({"thumbnail_path": thumb_url}).eq("id", entry_id).execute()
            print("完了")

        except Exception as e:
            print(f"エラー: {e}")

    print("全処理完了")


if __name__ == "__main__":
    main()