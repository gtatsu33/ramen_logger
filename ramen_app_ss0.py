import uuid
import datetime
from collections import Counter
import streamlit as st
from supabase import create_client, Client

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


def main():
    st.set_page_config(page_title="ラーメン記録帳", page_icon="🍜")
    st.title("🍜 ラーメン記録帳")
    st.caption("訪問日、写真、お店、ラーメン名、点数、コメントを登録して統計を確認できます。")

    stores = fetch_stores()
    store_options = ["新しいお店を登録"] + [
        f"{s['name']} ({s['latitude']},{s['longitude']})" for s in stores
    ]
    selected_store = st.selectbox("お店を選択", store_options)

    if selected_store == "新しいお店を登録":
        new_store = True
        store_name = st.text_input("お店の名前")
        store_lat = None
        store_lon = None
        lat_input = st.text_input("GPS 緯度")
        lon_input = st.text_input("GPS 経度")
        if lat_input.strip():
            try:
                store_lat = float(lat_input)
            except ValueError:
                st.warning("緯度は数値で入力してください。例: 35.681236")
        if lon_input.strip():
            try:
                store_lon = float(lon_input)
            except ValueError:
                st.warning("経度は数値で入力してください。例: 139.767125")
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
        score = st.slider("点数", min_value=1, max_value=10, value=8)
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
                    st.image(entry["photo_path"], caption="ラーメンの写真", use_column_width=True)

    st.markdown("---")
    st.subheader("統計")
    year_stats = stats_by_year(entries)
    month_stats = stats_by_month(entries)
    store_year_stats = stats_by_store_year(entries)

    if year_stats:
        st.write("### 年別の来店回数")
        st.table([{"年": r["year"], "回数": r["count"]} for r in year_stats])
        st.bar_chart({r["year"]: r["count"] for r in year_stats})
    else:
        st.info("年別統計はまだありません。")

    if month_stats:
        st.write("### 月別の来店回数")
        st.table([{"年月": r["month"], "回数": r["count"]} for r in month_stats])

    if store_year_stats:
        st.write("### お店別・年別の来店回数")
        grouped = {f"{r['store_name']} ({r['year']})": r["count"] for r in store_year_stats}
        st.table([{"お店と年": k, "回数": v} for k, v in grouped.items()])

    st.markdown("---")
    st.subheader("登録済みのお店")
    if stores:
        for s in stores:
            st.write(f"- {s['name']} — GPS: {s['latitude'] or '-'} / {s['longitude'] or '-'}")
    else:
        st.info("まだお店が登録されていません。記録登録で追加できます。")


if __name__ == "__main__":
    main()