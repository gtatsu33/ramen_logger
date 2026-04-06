import uuid
import datetime
from collections import Counter
import streamlit as st
from supabase import create_client, Client
import folium
from streamlit_folium import st_folium

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


def insert_entry(date: str, store_id: int, ramen_name: str, score: int, comment: str, photo_url: str | None):
    get_supabase().table("entries").insert({
        "date": date,
        "store_id": store_id,
        "ramen_name": ramen_name.strip(),
        "score": score,
        "comment": comment.strip() if comment else "",
        "photo_path": photo_url,
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


def upload_photo(file_bytes: bytes, original_name: str) -> str:
    suffix = original_name.rsplit(".", 1)[-1].lower()
    file_name = f"{uuid.uuid4().hex}.{suffix}"
    content_type = "image/png" if suffix == "png" else "image/jpeg"
    get_supabase().storage.from_(BUCKET_NAME).upload(
        file_name, file_bytes, {"content-type": content_type}
    )
    return get_supabase().storage.from_(BUCKET_NAME).get_public_url(file_name)


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
    st.set_page_config(page_title="ラーメン記録帳", page_icon="🍜")
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
        photo = st.file_uploader("写真をアップロード", type=["png", "jpg", "jpeg"])
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
                    photo_url = upload_photo(photo.read(), photo.name)

                insert_entry(visit_date.isoformat(), store_id, ramen_name, score, comment, photo_url)
                st.success("記録を保存しました！")
                st.rerun()

    st.markdown("---")
    st.subheader("最新の記録")
    entries = fetch_entries()

    if not entries:
        st.info("まだ記録がありません。上のフォームから追加してください。")
    else:
        for entry in entries[:10]:
            store_info = entry.get("stores", {}) or {}
            with st.expander(
                f"{entry['date']} - {store_info.get('name', '?')} / {entry['ramen_name']} ({entry['score']}点)"
            ):
                st.write(f"**お店:** {store_info.get('name', '-')}")
                lat = store_info.get("latitude")
                lon = store_info.get("longitude")
                if lat is not None and lon is not None:
                    st.write(f"**GPS:** {lat}, {lon}")
                st.write(f"**日付:** {entry['date']}")
                st.write(f"**ラーメン名:** {entry['ramen_name']}")
                st.write(f"**点数:** {entry['score']}")
                if entry.get("comment"):
                    st.write(f"**コメント:** {entry['comment']}")
                if entry.get("photo_path"):
                    st.image(entry["photo_path"], caption="ラーメンの写真", use_container_width=True)

    st.markdown("---")
    st.subheader("統計")
    year_stats = stats_by_year(entries)
    month_stats = stats_by_month(entries)
    store_year_stats = stats_by_store_year(entries)
    store_month_stats = stats_by_store_month(entries)

    if year_stats:
        st.write("### 年別の来店回数")
        st.table([{"年": r["year"], "回数": r["count"]} for r in year_stats])
#        st.bar_chart({r["year"]: r["count"] for r in year_stats})
    else:
        st.info("年別統計はまだありません。")

    if month_stats:
        st.write("### 月別の来店回数")
        available_years = sorted(set(r["month"][:4] for r in month_stats), reverse=True)
        selected_year = st.selectbox("年を選択", available_years, key="month_year_select")
        filtered = [r for r in month_stats if r["month"][:4] == selected_year]
        st.table([{"年月": r["month"], "回数": r["count"]} for r in filtered])

    if store_year_stats:
        st.write("### お店別・年別の来店回数")
        available_years = sorted(set(r["year"] for r in store_year_stats), reverse=True)
        selected_year = st.selectbox("年を選択", available_years, key="store_year_select")
        filtered = [r for r in store_year_stats if r["year"] == selected_year]
        grouped = {f"{r['store_name']} ({r['year']})": r["count"] for r in filtered}
        st.table([{"お店と年": k, "回数": v} for k, v in grouped.items()])
        
    if store_month_stats:
        st.write("### お店別・月別の来店回数")
        for stat in store_month_stats:
            store_name = stat['store_name']
            month = stat['month']
            count = stat['count']
            with st.expander(f"📍 {store_name} ({month}) - {count}件の来店"):
                relevant_entries = [e for e in entries if e["stores"]["name"] == store_name and e["date"][:7] == month]
                if relevant_entries:
                    for entry in relevant_entries:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**{entry['date']}** - {entry['ramen_name']}")
                            if entry.get("comment"):
                                st.caption(entry['comment'])
                        with col2:
                            st.metric("点数", entry['score'])
                        if entry.get("photo_path"):
                            st.image(entry["photo_path"], use_container_width=True, width=200)
                else:
                    st.info("この期間の来店情報はありません。")

    st.markdown("---")
    st.subheader("登録済みのお店")
    if stores:
        # お店の場所を地図に表示
        if any(s['latitude'] and s['longitude'] for s in stores):
            st.write("### 🗺️ お店の場所")
            # 地図の中心を最初の店舗の位置にする、またはデフォルト
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

        # お店リスト
        st.write("### 📋 お店一覧")
        for s in stores:
            st.write(f"- {s['name']} — GPS: {s['latitude'] or '-'} / {s['longitude'] or '-'}")
    else:
        st.info("まだお店が登録されていません。記録登録で追加できます。")


if __name__ == "__main__":
    main()