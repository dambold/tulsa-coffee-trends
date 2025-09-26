import os
import pandas as pd
import streamlit as st

# -------- Settings / Secrets (Cloud first, local fallback) --------
def get_secret(name, default=None, cast=str):
    if hasattr(st, "secrets") and name in st.secrets:
        return cast(st.secrets[name])
    return cast(os.getenv(name, default))

GOOGLE_API_KEY = get_secret("GOOGLE_PLACES_API_KEY", "")
YELP_API_KEY = get_secret("YELP_API_KEY", "")
SEARCH_LOCATION = get_secret("SEARCH_LOCATION", "Tulsa, OK")
SEARCH_RADIUS_METERS = get_secret("SEARCH_RADIUS_METERS", 15000, int)

st.set_page_config(page_title="Tulsa Coffee Trends (AI)", layout="wide")
st.title("☕ Tulsa Coffee Trends — AI Dashboard")
st.write("Local coffee insights using ratings + light NLP on review text (Yelp).")

BASE = os.path.dirname(__file__)
RAW = os.path.join(BASE, "data", "raw")
INTERIM = os.path.join(BASE, "data", "interim")
os.makedirs(RAW, exist_ok=True)
os.makedirs(INTERIM, exist_ok=True)

# -------- One-time bootstrap: collect + analyze if files missing --------
@st.cache_resource(show_spinner=True)
def bootstrap_if_needed():
    needed = [
        os.path.join(INTERIM, "step2_canonical.csv"),
        os.path.join(INTERIM, "step2_ranked_shops.csv"),
    ]
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in needed):
        return  # already good

    # Collect (Google only, since Yelp key is optional)
    from collect_data import google_places_search
    import pandas as pd

    if not GOOGLE_API_KEY:
        st.error("Missing GOOGLE_PLACES_API_KEY. Add it in Streamlit → Settings → Secrets.")
        st.stop()

    st.info("Collecting Google Places data...")
    gdf = google_places_search(
        location=SEARCH_LOCATION,
        radius_m=SEARCH_RADIUS_METERS,
        api_key=GOOGLE_API_KEY,
        keyword="coffee"
    )
    gpath = os.path.join(RAW, "google_places_coffee.csv")
    gdf.to_csv(gpath, index=False)

    # (Optional) Yelp if key provided
    if YELP_API_KEY:
        from collect_data import yelp_search
        st.info("Collecting Yelp data...")
        ydf = yelp_search(
            location=SEARCH_LOCATION,
            radius_m=SEARCH_RADIUS_METERS,
            api_key=YELP_API_KEY,
            include_reviews=True
        )
        ypath = os.path.join(RAW, "yelp_coffee.csv")
        ydf.to_csv(ypath, index=False)

    # Analyze
    st.info("Running analysis…")
    import analyze as analyzer
    analyzer.main()

bootstrap_if_needed()

# -------- Load analyzed data --------
try:
    canon = pd.read_csv(os.path.join(INTERIM, "step2_canonical.csv"))
    ranked = pd.read_csv(os.path.join(INTERIM, "step2_ranked_shops.csv"))
except Exception as e:
    st.error(f"Data not found and auto-setup failed: {e}")
    st.stop()

# -------- UI --------
with st.sidebar:
    st.header("Filters")
    min_stars = st.slider("Min average stars", 3.5, 5.0, 4.0, 0.1)
    show_n = st.slider("How many to show", 5, 50, 15, 1)

# Filtered view
ranked["stars"] = pd.to_numeric(ranked.get("stars"), errors="coerce")
view = ranked[ranked["stars"] >= min_stars].head(show_n)

st.subheader("Map: Top Picks")
if {"canonical_lat","canonical_lng"}.issubset(view.columns) and view[["canonical_lat","canonical_lng"]].notna().all().all():
    st.map(view.rename(columns={"canonical_lat":"lat","canonical_lng":"lon"}), size=20)
else:
    st.info("Coordinates missing for some entries — map limited.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Top by Stars")
    st.bar_chart(view.set_index("canonical_name")["stars"])
with c2:
    st.subheader("Top by Review Volume")
    st.bar_chart(view.set_index("canonical_name")["volume"])

st.subheader("Raw Canonical (preview)")
st.dataframe(canon.head(100))
