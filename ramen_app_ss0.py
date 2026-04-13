import uuid
import datetime
import io
from collections import Counter
from PIL import Image, ImageOps
import streamlit as st
from supabase import create_client, Client
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET_NAME = "ramen-photos"


@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_stores():
    res = get_supabase().table("stores").select("*").order("name").execute()
    return res.data


def insert_store(name: str, latitude: float | None, longitude: float | None) -> int:
    res = get_supabase().table("stores").insert({
        "name": name.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "created_at": datetime.datetime.now().isoformat(),
    }).execute()
    return res.data[0]["id"]


def insert_entry(date, store_id, ramen_name, score, comment, photo_url, thumb_url=None):
    get_supabase().table("entries").insert({
        "date": date,
        "store_id": store_id,
        "ramen_name": ramen_name.strip(),
        "score": score,
        "comment": comment.strip() if comment else "",
        "photo_path": photo_url,
        "thumbnail_path": thumb_url,   # 追加
        "created_at": datetime.datetime.now().isoformat(),
    }).execute()

def fetch_entries():
    res = (
        get_supabase()
        .table("entries")
        .select("*, stores(name, latitude, longitude)")
        .order("date", desc=True)
        .execute()
    )
    return res.data

def compress_image(file_bytes: bytes, max_size: int = 1280, quality: int = 80) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # スマホ写真の回転補正
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

def crop_square(url: str) -> bytes:
    import requests
    response = requests.get(url)
    img = Image.open(io.BytesIO(response.content))
    img = ImageOps.exif_transpose(img)
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    img = img.crop((left, top, left + size, top + size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def upload_photo(file_bytes: bytes, original_name: str) -> str:
    # オリジナル（既存処理）
    file_bytes = compress_image(file_bytes)
    file_name = f"{uuid.uuid4().hex}.jpg"
    get_supabase().storage.from_(BUCKET_NAME).upload(
        file_name, file_bytes, {"content-type": "image/jpeg"}
    )
    original_url = get_supabase().storage.from_(BUCKET_NAME).get_public_url(file_name)

    # サムネイル生成（正方形クロップ＋小さいサイズ）
    thumb_bytes = make_thumbnail(file_bytes)
    thumb_name = f"thumb_{file_name}"
    get_supabase().storage.from_(BUCKET_NAME).upload(
        thumb_name, thumb_bytes, {"content-type": "image/jpeg"}
    )
    thumb_url = get_supabase().storage.from_(BUCKET_NAME).get_public_url(thumb_name)

    return original_url, thumb_url

def make_thumbnail(file_bytes: bytes, size: int = 300) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # スマホ写真の回転補正
    w, h = img.size
    crop_size = min(w, h)
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    img = img.crop((left, top, left + crop_size, top + crop_size))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()

def stats_by_year(entries):
    counter = Counter(e["date"][:4] for e in entries)
    return [{"year": k, "count": v} for k, v in sorted(counter.items())]


def stats_by_month(entries):
    counter = Counter(e["date"][:7] for e in entries)
    return [{"month": k, "count": v} for k, v in sorted(counter.items())]


def stats_by_store_year(entries):
    counter = Counter((e["stores"]["name"], e["date"][:4]) for e in entries)
    return [{"store_name": k[0], "year": k[1], "count": v} for k, v in sorted(counter.items())]


def stats_by_store_month(entries):
    counter = Counter((e["stores"]["name"], e["date"][:7]) for e in entries)
    return [{"store_name": k[0], "month": k[1], "count": v} for k, v in sorted(counter.items())]


def main():
    st.set_page_config(page_title="ラーメンロガー", page_icon="images/rlicon.png",)
    st.markdown("<h2 style='margin-bottom:0'>🍜 ラーメンロガー</h2>", unsafe_allow_html=True)
    st.caption("訪問日、写真、お店、ラーメン名、点数、コメントを登録して統計を確認できます。")

    stores = fetch_stores()
    store_options = ["新しいお店を登録"] + [
        f"{s['name']} ({s['latitude']},{s['longitude']})" for s in stores
    ]
    selected_store = st.selectbox("お店を選択", store_options)

    if selected_store == "新しいお店を登録":
        new_store = True
        store_name = st.text_input("お店の名前")

        st.subheader("📍 お店の場所を選択")
        st.write("地図をクリックして場所を選択してください。")

        # デフォルトの地図中心（東京）
        default_lat, default_lon = 35.681236, 139.767125

        # 地図を作成
        m = folium.Map(location=[default_lat, default_lon], zoom_start=15)

        # クリックで位置を取得するためのプラグイン
        m.add_child(folium.LatLngPopup())

        # Streamlitで地図を表示し、クリック位置を取得
        map_data = st_folium(m, height=400, width=700)

        # クリックされた位置を取得
        if map_data and 'last_clicked' in map_data and map_data['last_clicked']:
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lng = map_data['last_clicked']['lng']
            st.success(f"選択された位置: 緯度 {clicked_lat:.6f}, 経度 {clicked_lng:.6f}")
            store_lat = clicked_lat
            store_lon = clicked_lng
        else:
            st.info("地図をクリックして場所を選択してください。")
            store_lat = None
            store_lon = None
    else:
        new_store = False
        store_index = store_options.index(selected_store) - 1
        store_name = stores[store_index]["name"]
        store_lat = stores[store_index]["latitude"]
        store_lon = stores[store_index]["longitude"]

    st.subheader("記録を追加")
    with st.form("entry_form"):
        visit_date = st.date_input("訪問日", value=datetime.date.today())
        ramen_name = st.text_input("ラーメンの名前")
        score = st.slider("点数（5点満点）", min_value=1, max_value=5, value=4)
        comment = st.text_area("コメント")
        photo = st.file_uploader("写真をアップロード（ファイルサイズが自動的に調整されます）", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("保存する")

        if submitted:
            if not ramen_name.strip():
                st.error("ラーメンの名前を入力してください。")
            elif new_store and not store_name.strip():
                st.error("新しいお店の名前を入力してください。")
            else:
                if new_store:
                    store_id = insert_store(store_name, store_lat, store_lon)
                else:
                    store_id = stores[store_index]["id"]

                photo_url = None
                if photo is not None:
                    photo_url, thumb_url = upload_photo(photo.read(), photo.name)

                insert_entry(visit_date.isoformat(), store_id, ramen_name, score, comment, photo_url, thumb_url)
                st.success("記録を保存しました！")
                st.session_state["do_reload"] = True
#                components.html("<script>window.location.reload();</script>", height=0)
#                st.rerun()

#    st.markdown("---")
#    st.subheader("最新の記録")

    if st.session_state.get("do_reload"):
        st.session_state["do_reload"] = False
        components.html("<script>window.parent.location.reload();</script>", height=0)
        st.stop()

    entries = fetch_entries()

#    if not entries:
#        st.info("まだ記録がありません。上のフォームから追加してください。")
#    else:
#        for entry in entries[:10]:
#            store_info = entry.get("stores", {}) or {}
#            with st.expander(
#                f"{entry['date']} - {store_info.get('name', '?')} / {entry['ramen_name']} ({entry['score']}点)"
#            ):
#                st.write(f"**お店:** {store_info.get('name', '-')}")
#                lat = store_info.get("latitude")
#                lon = store_info.get("longitude")
#                if lat is not None and lon is not None:
#                    st.write(f"**GPS:** {lat}, {lon}")
#                st.write(f"**日付:** {entry['date']}")
#                st.write(f"**ラーメン名:** {entry['ramen_name']}")
#                st.write(f"**点数:** {entry['score']}")
#                if entry.get("comment"):
#                    st.write(f"**コメント:** {entry['comment']}")
#                if entry.get("photo_path"):
#                    st.image(entry["photo_path"], caption="ラーメンの写真", width='stretch')

    st.markdown("---")
    st.subheader("統計")
    year_stats = stats_by_year(entries)
    month_stats = stats_by_month(entries)
    store_year_stats = stats_by_store_year(entries)
    store_month_stats = stats_by_store_month(entries)

    tab_year_month, tab_store = st.tabs(["年・月別", "店舗別"])

    with tab_year_month:
        if year_stats:
            st.write("### 年別の来店回数")
            st.table([{"年": r["year"], "回数": r["count"]} for r in year_stats])
#            st.bar_chart({r["year"]: r["count"] for r in year_stats})
        else:
            st.info("年別統計はまだありません。")

        if month_stats:
            st.write("### 月別の来店回数")
            available_years = sorted(set(r["month"][:4] for r in month_stats), reverse=True)
            current_year = str(datetime.date.today().year)
            default_idx = available_years.index(current_year) if current_year in available_years else 0
            selected_year = st.selectbox("年を選択", available_years, index=default_idx, key="month_year_select")
            filtered = [r for r in month_stats if r["month"][:4] == selected_year]
            st.table([{"年月": r["month"], "回数": r["count"]} for r in filtered])
        else:
            st.info("月別統計はまだありません。")

        if store_month_stats:
            available_years = sorted(set(r["month"][:4] for r in store_month_stats), reverse=True)
            available_months = [f"{m:02d}" for m in range(1, 13)]
            current_year = str(datetime.date.today().year)
            current_month = f"{datetime.date.today().month:02d}"
            default_year_idx = available_years.index(current_year) if current_year in available_years else 0
            default_month_idx = available_months.index(current_month)

            col1, col2 = st.columns(2)
            with col1:
                selected_year = st.selectbox("年を選択", available_years, index=default_year_idx, key="store_month_year_select")
            with col2:
                selected_month = st.selectbox("月を選択", available_months, index=default_month_idx, key="store_month_month_select")

            target = f"{selected_year}-{selected_month}"
            filtered_stats = sorted([r for r in store_month_stats if r["month"] == target], key=lambda r: r["count"], reverse=True)

            if not filtered_stats:
                st.info("該当する記録がありません。")
            else:
                photo_entries = sorted(
                    [e for stat in filtered_stats
                       for e in entries
                       if e["stores"]["name"] == stat["store_name"] and e["date"][:7] == stat["month"]],
                    key=lambda e: e["date"]
                )

                img_html = """
                <style>
                .tile { aspect-ratio:1/1; overflow:hidden; cursor:pointer; }
                .tile img { width:100%; height:100%; object-fit:cover; display:block; transition:opacity 0.2s; }
                .tile:hover img { opacity:0.85; }
                .rl-modal-bg {
                    display:none; position:fixed; inset:0;
                    background:rgba(0,0,0,0.7); z-index:9999;
                    align-items:center; justify-content:center;
                }
                .rl-modal-bg.active { display:flex; }
                .rl-modal {
                    background:#fff; border-radius:12px; overflow:hidden;
                    max-width:360px; width:90%; box-shadow:0 8px 32px rgba(0,0,0,0.4);
                }
                .rl-modal img { width:100%; aspect-ratio:1/1; object-fit:cover; display:block; }
                .rl-modal .info { padding:12px 16px; font-size:0.9em; line-height:1.8; }
                .rl-modal .info .ramen-name { font-size:1.1em; font-weight:bold; margin-bottom:4px; }
                .rl-modal .close-btn {
                    display:block; width:100%; padding:10px;
                    background:#f0f0f0; border:none; cursor:pointer;
                    font-size:0.9em; color:#333;
                }
                .rl-modal .close-btn:hover { background:#e0e0e0; }
                </style>
                <div class="rl-modal-bg" id="rlModalBg" onclick="if(event.target===this)closeModal()">
                    <div class="rl-modal">
                        <img id="rlModalImg" src="">
                        <div class="info">
                            <div class="ramen-name" id="rlModalRamen"></div>
                            <div id="rlModalDate"></div>
                            <div id="rlModalStore"></div>
                            <div id="rlModalComment"></div>
                        </div>
                        <button class="close-btn" onclick="closeModal()">閉じる</button>
                    </div>
                </div>
                <script>
                function openModal(src, date, store, ramen, comment) {
                    document.getElementById('rlModalImg').src = src;
                    document.getElementById('rlModalDate').textContent = '📅 ' + date;
                    document.getElementById('rlModalStore').textContent = '📍 ' + store;
                    document.getElementById('rlModalRamen').textContent = '🍜 ' + ramen;
                    var c = document.getElementById('rlModalComment');
                    c.textContent = comment ? '💬 ' + comment : '';
                    document.getElementById('rlModalBg').classList.add('active');
                }
                function closeModal() {
                    document.getElementById('rlModalBg').classList.remove('active');
                }
                </script>
                """
                for entry in photo_entries:
                    store_info = entry.get("stores", {}) or {}
                    store = store_info.get("name", "").replace("'", "\\'")
                    date = entry.get("date", "").replace("'", "\\'")
                    ramen = entry.get("ramen_name", "").replace("'", "\\'")
                    comment = (entry.get("comment") or "").replace("'", "\\'")
                    src = entry.get("thumbnail_path") or entry.get("photo_path") or ""
                    full_src = entry.get("photo_path") or src

                    if src:
                        img_html += (
                            f'<div class="tile" onclick="openModal(\'{full_src}\',\'{date}\',\'{store}\',\'{ramen}\',\'{comment}\')">'
                            f'<img src="{src}"></div>'
                        )
                    else:
                        img_html += '<div class="tile" style="background:#f0f0f0;display:flex;align-items:center;justify-content:center;color:#999;">📷</div>'
                tile_height = (len(photo_entries) // 4 + 1) * 220
                modal_height = 600
                components.html(
                    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;">'
                    f'{img_html}'
                    f'</div>',
                    height=max(tile_height, modal_height),
                    scrolling=False
                )
        else:
            st.info("月別の履歴はまだありません。")

    with tab_store:
        if store_year_stats:
            st.write("### お店別・年別の来店回数")
            available_years = sorted(set(r["year"] for r in store_year_stats), reverse=True)
            selected_year = st.selectbox("年を選択", available_years, key="store_year_select")
            filtered = sorted([r for r in store_year_stats if r["year"] == selected_year], key=lambda r: r["count"], reverse=True)
            st.table([{"お店と年": f"{r['store_name']} ({r['year']})", "回数": r["count"]} for r in filtered])
        else:
            st.info("お店別・年別の統計はまだありません。")

        st.write("### 登録済みのお店")
        if stores:
            if any(s['latitude'] and s['longitude'] for s in stores):
                st.write("### 🗺️ お店の場所")
                center_lat = stores[0]['latitude'] if stores[0]['latitude'] else 35.681236
                center_lon = stores[0]['longitude'] if stores[0]['longitude'] else 139.767125

                m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

                for store in stores:
                    if store['latitude'] and store['longitude']:
                        folium.Marker(
                            location=[store['latitude'], store['longitude']],
                            popup=f"<b>{store['name']}</b><br>GPS: {store['latitude']}, {store['longitude']}",
                            tooltip=store['name']
                        ).add_to(m)

                st_folium(m, height=400, width=700)
            else:
                st.table([{"お店": s['name']} for s in stores])
        else:
            st.info("まだお店が登録されていません。記録登録で追加できます。")



if __name__ == "__main__":
    main()