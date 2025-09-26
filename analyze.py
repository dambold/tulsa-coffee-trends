#!/usr/bin/env python3
"""
Step 2: Analysis & Sentiment
- Reads raw CSVs from data/raw
- Cleans + dedupes
- Sentiment from Yelp review text (VADER)
- Outputs analysis CSVs and charts to data/interim and data/outputs
"""
import os
import re
import json
import math
import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# Sentiment
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Viz
import matplotlib.pyplot as plt
from wordcloud import WordCloud

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
INTERIM = BASE / "data" / "interim"
OUTPUTS = BASE / "data" / "outputs"
for p in (INTERIM, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)

def ensure_vader():
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon")

def load_raw():
    g = pd.DataFrame()
    y = pd.DataFrame()
    gpath = RAW / "google_places_coffee.csv"
    ypath = RAW / "yelp_coffee.csv"
    if gpath.exists():
        g = pd.read_csv(gpath)
    if ypath.exists():
        y = pd.read_csv(ypath)
    return g, y

def canonical_merge(g, y):
    # If Yelp is empty or missing columns, build canonical from Google only
    if y is None or y.empty or not {"name","lat","lng"}.issubset(set(y.columns)):
        gg = g.copy()
        if gg.empty:
            return pd.DataFrame(columns=[
                "canonical_name","canonical_lat","canonical_lng","address",
                "rating_google","user_ratings_total","rating_yelp","review_count",
                "place_id","yelp_id","url"
            ])
        gg["canonical_name"] = gg.get("name")
        gg["canonical_lat"] = gg.get("lat")
        gg["canonical_lng"] = gg.get("lng")
        gg["address"] = gg.get("address")
        gg["rating_google"] = gg.get("rating")
        gg["user_ratings_total"] = gg.get("user_ratings_total")
        gg["rating_yelp"] = pd.NA
        gg["review_count"] = pd.NA
        gg["yelp_id"] = pd.NA
        gg["url"] = pd.NA
        keep = ["canonical_name","canonical_lat","canonical_lng","address",
                "rating_google","user_ratings_total","rating_yelp","review_count",
                "place_id","yelp_id","url"]
        for c in keep:
            if c not in gg.columns:
                gg[c] = pd.NA
        return gg[keep].drop_duplicates(subset=["canonical_name","canonical_lat","canonical_lng"]).reset_index(drop=True)

    # Otherwise, prep both and merge on normalized name + rounded coords
    def prep(df):
        df = df.copy()
        df["norm_name"] = df["name"].str.lower().str.replace(r"[^a-z0-9]+"," ", regex=True).str.strip()
        df["lat_r"] = df["lat"].round(3)
        df["lng_r"] = df["lng"].round(3)
        return df

    g2 = prep(g)
    y2 = prep(y)

    merged = pd.merge(
        g2, y2,
        on=["norm_name","lat_r","lng_r"],
        how="outer",
        suffixes=("_google","_yelp")
    )

    merged["canonical_name"] = merged.get("name_google").fillna(merged.get("name_yelp"))
    merged["canonical_lat"] = merged.get("lat_google").fillna(merged.get("lat_yelp"))
    merged["canonical_lng"] = merged.get("lng_google").fillna(merged.get("lng_yelp"))
    merged["address"] = merged.get("address_google").fillna(merged.get("address_yelp"))
    merged["rating_google"] = merged.get("rating_google", merged.get("rating")).fillna(merged.get("rating_google"))
    merged["rating_yelp"] = merged.get("rating_yelp", merged.get("rating")).fillna(merged.get("rating_yelp"))
    merged["review_count"] = merged.get("review_count")
    merged["user_ratings_total"] = merged.get("user_ratings_total")

    keep = ["canonical_name","canonical_lat","canonical_lng","address",
            "rating_google","user_ratings_total","rating_yelp","review_count",
            "place_id","yelp_id","url"]
    for c in keep:
        if c not in merged.columns:
            merged[c] = pd.NA
    return merged[keep].drop_duplicates(subset=["canonical_name","canonical_lat","canonical_lng"]).reset_index(drop=True)

def collect_review_text(y):
    if y.empty:
        return pd.DataFrame(columns=["yelp_id","review_text"])
    # Flatten the review_1_text..review_3_text into single rows per business
    text_cols = [c for c in y.columns if re.match(r"review_\d+_text", c)]
    rows = []
    for _, r in y.iterrows():
        texts = []
        for c in text_cols:
            t = r.get(c)
            if pd.notnull(t) and isinstance(t, str) and t.strip():
                texts.append(t.strip())
        if texts:
            rows.append({"yelp_id": r.get("yelp_id"), "review_text": " ".join(texts)})
    df = pd.DataFrame(rows).dropna()
    return df

def sentiment_scores(df_reviews):
    if df_reviews.empty:
        df_reviews["neg"]=df_reviews["neu"]=df_reviews["pos"]=df_reviews["compound"]=np.nan
        return df_reviews
    ensure_vader()
    sia = SentimentIntensityAnalyzer()
    scores = df_reviews["review_text"].apply(lambda t: sia.polarity_scores(str(t)))
    scores_df = pd.json_normalize(scores)
    out = pd.concat([df_reviews.reset_index(drop=True), scores_df], axis=1)
    return out

def rank_shops(canon, yelp_scores, y_raw):
    # If there is no canonical data, return an empty DataFrame
    if canon is None or canon.empty:
        print("[warn] No canonical data to rank — returning empty DataFrame.")
        return pd.DataFrame(columns=[
            "canonical_name","canonical_lat","canonical_lng",
            "stars","volume","sentiment","score"
        ])

    # Merge Yelp IDs if available
    if y_raw is not None and not y_raw.empty and "yelp_id" in y_raw.columns:
        base = canon.merge(y_raw[["yelp_id","name"]], on="yelp_id", how="left")
    else:
        base = canon.copy()

    # Merge Yelp sentiment if available
    if yelp_scores is not None and not yelp_scores.empty and "compound" in yelp_scores.columns:
        base = base.merge(yelp_scores[["yelp_id","compound"]], on="yelp_id", how="left")
    if "compound" not in base.columns:
        base["compound"] = np.nan

    # Clean numeric fields
    base["rating_google"] = pd.to_numeric(base.get("rating_google"), errors="coerce")
    base["rating_yelp"] = pd.to_numeric(base.get("rating_yelp"), errors="coerce")
    base["user_ratings_total"] = pd.to_numeric(base.get("user_ratings_total"), errors="coerce")
    base["review_count"] = pd.to_numeric(base.get("review_count"), errors="coerce")

    # Compute aggregate metrics
    base["stars"] = base[["rating_google","rating_yelp"]].mean(axis=1, skipna=True)
    base["volume"] = base[["user_ratings_total","review_count"]].max(axis=1, skipna=True)
    base["sentiment"] = base["compound"]

    # Normalize and compute score
    def norm(col):
        c = base[col].astype(float)
        return (c - c.min()) / (c.max() - c.min() + 1e-9) if c.notna().sum() > 1 else c.fillna(0.5)

    base["score"] = 0.6 * norm("stars") + 0.3 * norm("volume") + 0.1 * norm("sentiment")
    ranked = base.sort_values("score", ascending=False).reset_index(drop=True)
    return ranked


def save_top_charts(ranked, topn=10):
    top = ranked.head(topn)
    # Stars chart
    plt.figure()
    plt.barh(top["canonical_name"][::-1], top["stars"][::-1])
    plt.title(f"Top {topn} Tulsa Coffee Shops by Stars")
    plt.xlabel("Average Stars (Google/Yelp)")
    plt.tight_layout()
    plt.savefig(OUTPUTS / "top_stars.png", dpi=180)
    plt.close()

    # Volume chart
    plt.figure()
    plt.barh(top["canonical_name"][::-1], top["volume"][::-1])
    plt.title(f"Top {topn} by Review Volume")
    plt.xlabel("Review Count (max of Google/Yelp)")
    plt.tight_layout()
    plt.savefig(OUTPUTS / "top_volume.png", dpi=180)
    plt.close()

def save_wordcloud(df_reviews):
    if df_reviews.empty or "review_text" not in df_reviews.columns:
        return
    text = " ".join(df_reviews["review_text"].dropna().tolist())
    if not text.strip():
        return
    wc = WordCloud(width=1200, height=800, background_color="white").generate(text)
    wc.to_file(str(OUTPUTS / "reviews_wordcloud.png"))

def main():
    g, y = load_raw()
    canon = canonical_merge(g, y)
    canon.to_csv(INTERIM / "step2_canonical.csv", index=False)

    reviews = collect_review_text(y)
    scored = sentiment_scores(reviews)
    scored.to_csv(INTERIM / "step2_yelp_reviews_scored.csv", index=False)

    ranked = rank_shops(canon, scored, y)
    ranked.to_csv(INTERIM / "step2_ranked_shops.csv", index=False)

    save_top_charts(ranked, topn=10)
    save_wordcloud(reviews)

    print("Done. Outputs:")
    print(f"- {INTERIM / 'step2_canonical.csv'}")
    print(f"- {INTERIM / 'step2_yelp_reviews_scored.csv'}")
    print(f"- {INTERIM / 'step2_ranked_shops.csv'}")
    print(f"- {OUTPUTS / 'top_stars.png'}")
    print(f"- {OUTPUTS / 'top_volume.png'}")
    print(f"- {OUTPUTS / 'reviews_wordcloud.png'} (if reviews available)")

if __name__ == "__main__":
    main()
