import uuid
import datetime
import io
from collections import Counter
from PIL import Image, ImageOps
import streamlit as st
from supabase import create_client, Client
import folium
from streamlit_folium import st_folium
from streamlit_image_coordinates import streamlit_image_coordinates


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
        "thumbnail_path": thumb_url,
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
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def upload_photo(file_bytes: bytes, original_name: str) -> str:
    file_bytes = compress_image(file_bytes)
    file_name = f"{uuid.uuid4().hex}.jpg"
    get_supabase().storage.from_(BUCKET_NAME).upload(
        file_name, file_bytes, {"content-type": "image/jpeg"}
    )
    original_url = get_supabase().storage.from_(BUCKET_NAME).get_public_url(file_name)

    thumb_bytes = make_thumbnail(file_bytes)
    thumb_name = f"thumb_{file_name}"
    get_supabase().storage.from_(BUCKET_NAME).upload(
        thumb_name, thumb_bytes, {"content-type": "image/jpeg"}
    )
    thumb_url = get_supabase().storage.from_(BUCKET_NAME).get_public_url(thumb_name)

    return original_url, thumb_url


def make_thumbnail(file_bytes: bytes, size: int = 300) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)
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


# ─── モーダルダイアログ ────────────────────────────────────────────────────────
@st.dialog("ラーメン詳細", width="large")
def show_photo_modal():
    entry = st.session_state.get("modal_entry")
    if not entry:
        return
    store_info = entry.get("stores", {}) or {}

    if entry.get("photo_path"):
        st.image(entry["photo_path"], width="stretch")

    st.markdown(f"### 🍜 {entry.get('ramen_name', '')}")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"📅 {entry.get('date', '')}")
        st.write(f"📍 {store_info.get('name', '')}")
    with col2:
        st.write(f"⭐ {entry.get('score', '')} 点")
    if entry.get("comment"):
        st.write(f"💬 {entry.get('comment')}")

    if st.button("閉じる", use_container_width=True):
        del st.session_state["modal_entry"]
        st.rerun()


# ─── 写真タイルグリッド ────────────────────────────────────────────────────────
def render_photo_tiles(photo_entries, key_prefix: str = "tile"):
    """
    写真グリッドを描画する。クリックを検出したら session_state にフラグを立てるだけ。
    ダイアログは main() の末尾で一度だけ開く。
    常に5列固定で表示する。
    """
    if not photo_entries:
        st.info("該当する写真はありません。")
        return

    NUM_COLS = 4

    # Streamlit がモバイルでカラムを縦積みにする CSS を上書き。
    # :has(> …:nth-child(4)) で「4列ブロックだけ」をターゲットにするため
    # 他のカラムレイアウト（2列など）には影響しない。
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"]:has(
            > div[data-testid="stColumn"]:nth-child(4)
        ) {
            flex-wrap: nowrap !important;
            gap: 2px !important;
            margin-bottom: 0 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(
            > div[data-testid="stColumn"]:nth-child(4)
        ) > div[data-testid="stColumn"] {
            min-width: 0 !important;
            flex: 1 1 0 !important;
            max-width: none !important;
            box-sizing: border-box !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(
            > div[data-testid="stColumn"]:nth-child(4)
        ) > div[data-testid="stColumn"] > div {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 0 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(
            > div[data-testid="stColumn"]:nth-child(4)
        ) > div[data-testid="stColumn"] iframe {
            display: block !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(NUM_COLS)

    for idx, entry in enumerate(photo_entries):
        src = entry.get("thumbnail_path") or entry.get("photo_path") or ""
        entry_id = entry.get("id", f"{idx}")
        img_key = f"{key_prefix}_{entry_id}"
        ts_key = f"_seen_ts_{img_key}"

        with cols[idx % NUM_COLS]:
            if src:
                clicked = streamlit_image_coordinates(
                    src,
                    key=img_key,
                    use_column_width="always",
                )
                if clicked is not None:
                    ts = clicked.get("timestamp", 0)
                    if ts != st.session_state.get(ts_key):
                        st.session_state[ts_key] = ts
                        st.session_state["modal_entry"] = entry
                        st.session_state["_open_modal"] = True
            else:
                st.markdown(
                    "<div style='aspect-ratio:1/1;background:#f0f0f0;"
                    "display:flex;align-items:center;justify-content:center;"
                    "border-radius:4px;color:#aaa;font-size:1.5em;'>📷</div>",
                    unsafe_allow_html=True,
                )


# ─── メイン ───────────────────────────────────────────────────────────────────
def main():
    import streamlit.components.v1 as components

    st.set_page_config(page_title="ラーメンロガー", page_icon="images/rlicon.png")
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

        default_lat, default_lon = 35.681236, 139.767125
        m = folium.Map(location=[default_lat, default_lon], zoom_start=15)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=400, width=700)

        if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lng = map_data["last_clicked"]["lng"]
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
        photo = st.file_uploader(
            "写真をアップロード（ファイルサイズが自動的に調整されます）",
            type=["png", "jpg", "jpeg"],
        )
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

                photo_url = thumb_url = None
                if photo is not None:
                    photo_url, thumb_url = upload_photo(photo.read(), photo.name)

                insert_entry(
                    visit_date.isoformat(), store_id, ramen_name, score, comment, photo_url, thumb_url
                )
                st.success("記録を保存しました！")
                st.session_state["do_reload"] = True

    if st.session_state.get("do_reload"):
        st.session_state["do_reload"] = False
        components.html("<script>window.parent.location.reload();</script>", height=0)
        st.stop()

    entries = fetch_entries()

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
        else:
            st.info("年別統計はまだありません。")

        if month_stats:
            st.write("### 月別の来店回数")
            available_years = sorted(set(r["month"][:4] for r in month_stats), reverse=True)
            current_year = str(datetime.date.today().year)
            default_idx = available_years.index(current_year) if current_year in available_years else 0
            selected_year = st.selectbox(
                "年を選択", available_years, index=default_idx, key="month_year_select"
            )
            # 選択された年の全エントリを取得（写真があるもののみ）
            year_entries = sorted(
                [e for e in entries if e["date"][:4] == selected_year and e.get("photo_path")],
                key=lambda e: e["date"],
                reverse=True,
            )
            if not year_entries:
                st.info("該当する写真がありません。")
            else:
                # 月ごとにグループ化
                from collections import defaultdict
                monthly_entries = defaultdict(list)
                for entry in year_entries:
                    month = entry["date"][:7]  # YYYY-MM
                    monthly_entries[month].append(entry)
                
                # 月を降順でソート
                for month in sorted(monthly_entries.keys(), reverse=True):
                    month_entries = monthly_entries[month]
                    month_name = f"{int(month[5:]):d}月"  # MM を数値に変換して月
                    count = len(month_entries)
                    st.write(f"**{month_name} {count}件**")
                    render_photo_tiles(month_entries, key_prefix=f"month_{month}")
        else:
            st.info("月別統計はまだありません。")

    with tab_store:
        if store_year_stats:
            st.write("### お店別・年別の来店回数")
            available_years = sorted(set(r["year"] for r in store_year_stats), reverse=True)
            selected_year = st.selectbox("年を選択", available_years, key="store_year_select")
            filtered = sorted(
                [r for r in store_year_stats if r["year"] == selected_year],
                key=lambda r: r["count"],
                reverse=True,
            )

            for row in filtered:
                store_name = row["store_name"]
                count = row["count"]
                st.write(f"**{store_name} {count}件**")
                photo_entries = sorted(
                    [
                        e
                        for e in entries
                        if e["stores"]["name"] == store_name
                        and e["date"][:4] == selected_year
                        and e.get("photo_path")
                    ],
                    key=lambda e: e["date"],
                    reverse=True,
                )
                if photo_entries:
                    render_photo_tiles(photo_entries, key_prefix=f"store_{store_name}_{selected_year}")
        else:
            st.info("お店別・年別の統計はまだありません。")

        st.write("### 登録済みのお店")
        if stores:
            if any(s["latitude"] and s["longitude"] for s in stores):
                st.write("### 🗺️ お店の場所")
                center_lat = stores[0]["latitude"] if stores[0]["latitude"] else 35.681236
                center_lon = stores[0]["longitude"] if stores[0]["longitude"] else 139.767125

                m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                for store in stores:
                    if store["latitude"] and store["longitude"]:
                        folium.Marker(
                            location=[store["latitude"], store["longitude"]],
                            popup=f"<b>{store['name']}</b><br>GPS: {store['latitude']}, {store['longitude']}",
                            tooltip=store["name"],
                        ).add_to(m)
                st_folium(m, height=400, width=700)
            else:
                st.table([{"お店": s["name"]} for s in stores])
        else:
            st.info("まだお店が登録されていません。記録登録で追加できます。")

    # ─── ダイアログはここで一度だけ開く ───────────────────────────────────────
    # render_photo_tiles がフラグを立てた場合のみ実行される
    if st.session_state.pop("_open_modal", False):
        show_photo_modal()


if __name__ == "__main__":
    main()
