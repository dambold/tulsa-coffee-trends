import os
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="Tulsa Coffee Trends (AI)", layout="wide")

st.title("☕ Tulsa Coffee Trends — AI Dashboard")
st.write("Local coffee insights using ratings + light NLP on review text (Yelp).")

# Load data
@st.cache_data
def load_data():
    base = os.path.dirname(os.path.dirname(__file__))
    canon = pd.read_csv(os.path.join(base, "data", "interim", "step2_canonical.csv"))
    ranked = pd.read_csv(os.path.join(base, "data", "interim", "step2_ranked_shops.csv"))
    return canon, ranked

try:
    canon, ranked = load_data()
except Exception as e:
    st.error("Data not found. Run `python analyze.py` first.")
    st.stop()

# Controls
with st.sidebar:
    st.header("Filters")
    min_stars = st.slider("Min average stars", 3.5, 5.0, 4.0, 0.1)
    show_n = st.slider("How many to show", 5, 50, 15, 1)

# Filtered view
ranked["stars"] = pd.to_numeric(ranked["stars"], errors="coerce")
view = ranked[ranked["stars"] >= min_stars].head(show_n)

# Map
st.subheader("Map: Top Picks")
if {"canonical_lat","canonical_lng"}.issubset(view.columns) and view[["canonical_lat","canonical_lng"]].notna().all().all():
    st.map(view.rename(columns={"canonical_lat":"lat","canonical_lng":"lon"}), size=20)
else:
    st.info("Coordinates missing for some entries — map limited.")

# Tables & charts
c1, c2 = st.columns(2)
with c1:
    st.subheader("Top by Stars")
    st.bar_chart(view.set_index("canonical_name")["stars"])

with c2:
    st.subheader("Top by Review Volume")
    st.bar_chart(view.set_index("canonical_name")["volume"])

st.subheader("Raw Canonical")
st.dataframe(canon.head(100))
