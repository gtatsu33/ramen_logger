import uuid
import datetime
import io
import json
from collections import Counter
from PIL import Image, ImageOps
import streamlit as st
from supabase import create_client, Client
from streamlit_image_coordinates import streamlit_image_coordinates


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GMAPS_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
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


# ─── 新規店舗登録確認ダイアログ ──────────────────────────────────────────────
@st.dialog("登録確認", width="small")
def confirm_save_dialog():
    pending = st.session_state.get("_pending_save", {})
    store_name = pending.get("store_name", "")
    st.markdown(f'店舗名「**{store_name}**」で登録します。よろしいですか？')
    col1, col2 = st.columns(2)
    with col1:
        if st.button("はい", use_container_width=True, type="primary"):
            store_id = insert_store(store_name, pending["store_lat"], pending["store_lon"])
            photo_url = thumb_url = None
            if pending.get("photo_bytes"):
                photo_url, thumb_url = upload_photo(pending["photo_bytes"], pending["photo_name"])
            insert_entry(
                pending["visit_date"], store_id, pending["ramen_name"],
                pending["score"], pending["comment"], photo_url, thumb_url,
            )
            st.session_state.pop("_pending_save", None)
            for k in ["_last_action", "_prev_manual", "_prev_map_coords", "store_name_input"]:
                st.session_state.pop(k, None)
            st.session_state["do_reload"] = True
            st.rerun()
    with col2:
        if st.button("キャンセル", use_container_width=True):
            st.session_state.pop("_pending_save", None)
            st.rerun()


# ─── モーダルダイアログ ────────────────────────────────────────────────────────
@st.dialog("ラーメン詳細", width="large")
def show_photo_modal():
    st.markdown(
        "<style>button[data-testid='baseButton-headerNoPadding']"
        "{display:none !important;}</style>",
        unsafe_allow_html=True,
    )
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

        # ── URL パラメータ（地図クリックでJSが書き込む） ──────────────────────
        params = st.query_params
        has_map_selection = "map_lat" in params and "map_lng" in params
        init_lat = float(params.get("map_lat", 35.681236))
        init_lng = float(params.get("map_lng", 139.767125))
        map_name = params.get("map_name", "")
        init_has_js = "true" if has_map_selection else "false"
        init_name_js = json.dumps(map_name)

        # ── 地図クリック検知：座標が変わったら _last_action = "map" ───────────
        current_coords = (params.get("map_lat", ""), params.get("map_lng", ""))
        prev_coords = st.session_state.get("_prev_map_coords", ("", ""))
        if current_coords != ("", "") and current_coords != prev_coords:
            st.session_state["_last_action"] = "map"
            st.session_state["_prev_map_coords"] = current_coords

        # ── 手入力フィールド（マップとは独立・自動入力なし） ──────────────────
        prev_manual = st.session_state.get("_prev_manual", "")
        manual_name = st.text_input("お店の名前（手入力）", key="store_name_input")
        if manual_name != prev_manual and manual_name:
            st.session_state["_last_action"] = "manual"
        st.session_state["_prev_manual"] = manual_name

        # ── 登録に使う店舗名を決定 ────────────────────────────────────────────
        last_action = st.session_state.get("_last_action", "")
        store_name = map_name if last_action == "map" else manual_name

        st.subheader("📍 お店の場所を選択")

        pick_map_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin: 0; }}
  #map {{ height: 400px; width: 100%; }}
  #info {{ padding: 6px 10px; font-size: 13px; color: #555;
           background: #f5f5f5; border-bottom: 1px solid #ddd; }}
</style>
</head>
<body>
<div id="info">地図をクリックして場所を選択してください。</div>
<div id="map"></div>
<script>
const HAS = {init_has_js};
const ILAT = {init_lat};
const ILNG = {init_lng};
const INAME = {init_name_js};
function gm_authFailure() {{
  document.getElementById('map').innerHTML =
    '<p style="color:red;padding:16px">Maps認証エラー: APIキーが無効か、Maps JavaScript APIが有効になっていません。</p>';
}}
function initMap() {{
  const map = new google.maps.Map(document.getElementById('map'), {{
    center: {{lat: ILAT, lng: ILNG}},
    zoom: 15,
  }});
  let marker = null;
  let currentLocationMarker = null;
  if (HAS) {{
    marker = new google.maps.Marker({{position: {{lat: ILAT, lng: ILNG}}, map: map}});
    document.getElementById('info').textContent = INAME
      ? '📍 ' + INAME
      : '選択中: 緯度 ' + ILAT.toFixed(6) + ', 経度 ' + ILNG.toFixed(6);
  }} else if (navigator.geolocation) {{
    document.getElementById('info').textContent =
      '現在地を取得しています。許可すると地図の初期位置に反映されます。';
    navigator.geolocation.getCurrentPosition(
      pos => {{
        const current = {{
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        }};
        map.setCenter(current);
        currentLocationMarker = new google.maps.Marker({{
          position: current,
          map: map,
          title: '現在地',
          icon: {{
            path: google.maps.SymbolPath.CIRCLE,
            scale: 7,
            fillColor: '#4285F4',
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2,
          }},
        }});
        document.getElementById('info').textContent =
          '現在地周辺を表示しています。地図をクリックして場所を選択してください。';
      }},
      () => {{
        document.getElementById('info').textContent =
          '地図をクリックして場所を選択してください。';
      }},
      {{enableHighAccuracy: true, timeout: 10000, maximumAge: 300000}}
    );
  }}
  map.addListener('click', e => {{
    const lat = e.latLng.lat();
    const lng = e.latLng.lng();
    if (marker) marker.setMap(null);
    marker = new google.maps.Marker({{position: e.latLng, map: map}});
    document.getElementById('info').textContent = '周辺のラーメン店を検索中...';
    const svc = new google.maps.places.PlacesService(map);
    svc.nearbySearch({{
      location: e.latLng,
      rankBy: google.maps.places.RankBy.DISTANCE,
      keyword: 'ラーメン',
    }}, (results, status) => {{
      let name = '';
      if (status === google.maps.places.PlacesServiceStatus.OK && results.length > 0) {{
        name = results[0].name;
        document.getElementById('info').textContent = '📍 ' + name;
      }} else {{
        document.getElementById('info').textContent =
          '選択中: 緯度 ' + lat.toFixed(6) + ', 経度 ' + lng.toFixed(6) + '（店舗名未検出）';
      }}
      window.parent.history.replaceState(null, '',
        '?map_lat=' + lat + '&map_lng=' + lng + '&map_name=' + encodeURIComponent(name));
    }});
  }});
}}
</script>
<script src="https://maps.googleapis.com/maps/api/js?key={GMAPS_KEY}&libraries=places&callback=initMap" async defer></script>
</body>
</html>"""
        components.html(pick_map_html, height=430)

        if has_map_selection:
            store_lat = init_lat
            store_lon = init_lng
            st.success(f"選択された位置: 緯度 {store_lat:.6f}, 経度 {store_lon:.6f}")
        else:
            st.info("地図をクリックしてから「保存する」を押してください。")
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
                photo_bytes = photo.read() if photo is not None else None
                photo_name = photo.name if photo is not None else None

                if new_store:
                    # 確認ダイアログに委ねる
                    st.session_state["_pending_save"] = {
                        "store_name": store_name,
                        "store_lat": store_lat,
                        "store_lon": store_lon,
                        "visit_date": visit_date.isoformat(),
                        "ramen_name": ramen_name,
                        "score": score,
                        "comment": comment,
                        "photo_bytes": photo_bytes,
                        "photo_name": photo_name,
                    }
                else:
                    store_id = stores[store_index]["id"]
                    photo_url = thumb_url = None
                    if photo_bytes:
                        photo_url, thumb_url = upload_photo(photo_bytes, photo_name)
                    insert_entry(
                        visit_date.isoformat(), store_id, ramen_name, score, comment, photo_url, thumb_url
                    )
                    st.success("記録を保存しました！")
                    st.session_state["do_reload"] = True

    if st.session_state.get("do_reload"):
        st.session_state["do_reload"] = False
        components.html("<script>window.parent.history.replaceState(null,'',window.parent.location.pathname);window.parent.location.reload();</script>", height=0)
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
            st.write("### 月別の記録")
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
                    st.markdown(
                        f"<p style='margin-top:14px; margin-bottom:2px; font-weight:bold;'>{month_name} {count}件</p>",
                        unsafe_allow_html=True,
                )   
                    render_photo_tiles(month_entries, key_prefix=f"month_{month}")
        else:
            st.info("月別統計はまだありません。")

    with tab_store:
        if store_year_stats:
            st.write("### お店別の記録")
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
                st.markdown(
                    f"<p style='margin-top:14px; margin-bottom:2px; font-weight:bold;'>{store_name} {count}件</p>",
                    unsafe_allow_html=True,
                )
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
                valid_stores = [s for s in stores if s["latitude"] and s["longitude"]]
                center_lat = valid_stores[0]["latitude"]
                center_lon = valid_stores[0]["longitude"]
                markers_json = json.dumps(
                    [{"lat": s["latitude"], "lng": s["longitude"], "name": s["name"]}
                     for s in valid_stores],
                    ensure_ascii=False,
                )
                list_map_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin: 0; }}
  #map {{ height: 400px; width: 100%; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
const MARKERS = {markers_json};
const CENTER = {{lat: {center_lat}, lng: {center_lon}}};
function gm_authFailure() {{
  document.getElementById('map').innerHTML =
    '<p style="color:red;padding:16px">Maps認証エラー: APIキーが無効か、Maps JavaScript APIが有効になっていません。</p>';
}}
function initMap() {{
  const map = new google.maps.Map(document.getElementById('map'), {{
    center: CENTER,
    zoom: 12,
  }});
  const infoWindow = new google.maps.InfoWindow();
  MARKERS.forEach(m => {{
    const marker = new google.maps.Marker({{
      position: {{lat: m.lat, lng: m.lng}},
      map: map,
      title: m.name,
    }});
    marker.addListener('click', () => {{
      infoWindow.setContent('<b>' + m.name + '</b>');
      infoWindow.open(map, marker);
    }});
  }});
}}
</script>
<script src="https://maps.googleapis.com/maps/api/js?key={GMAPS_KEY}&callback=initMap" async defer></script>
</body>
</html>"""
                components.html(list_map_html, height=420)
            else:
                st.table([{"お店": s["name"]} for s in stores])
        else:
            st.info("まだお店が登録されていません。記録登録で追加できます。")

    # ─── ダイアログはここで一度だけ開く ───────────────────────────────────────
    if st.session_state.get("_pending_save"):
        confirm_save_dialog()

    # render_photo_tiles がフラグを立てた場合のみ実行される
    if st.session_state.pop("_open_modal", False):
        show_photo_modal()


if __name__ == "__main__":
    main()
