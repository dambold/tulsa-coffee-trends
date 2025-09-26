#!/usr/bin/env python3
import os
import time
import math
import argparse
import requests
import pandas as pd
from typing import List, Dict, Any
from urllib.parse import urlencode
from dotenv import load_dotenv

GOOGLE_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
YELP_REVIEWS_URL_TMPL = "https://api.yelp.com/v3/businesses/{id}/reviews"

def env_or_default(key: str, default: Any) -> Any:
    v = os.getenv(key)
    return v if v is not None and v != "" else default

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def google_places_search(location: str, radius_m: int, api_key: str, keyword="coffee") -> pd.DataFrame:
    """
    Uses 'textsearch via nearbysearch' approach by first geocoding the location implicitly through 'location bias'.
    For simplicity here, we use the first page + pagination via next_page_token.
    """
    # Geocode center via a simple search using Yelp to get coords, or fallback hard-code Tulsa center if not provided.
    # To avoid extra APIs, we allow user to pass radius + location using Google Places directly with text 'coffee' and rankby prominence.
    params = dict(
        keyword=keyword,
        radius=radius_m,
        key=api_key
    )
    # We need lat/lng; use a lightweight hack: Google Places Nearby requires 'location' lat,lng.
    # We will geocode via the 'textsearch' endpoint would be better, but to keep keys minimal we use a static Tulsa centroid.
    # Tulsa centroid:
    tulsa_lat, tulsa_lng = 36.15398, -95.99277
    params["location"] = f"{tulsa_lat},{tulsa_lng}"
    url = GOOGLE_NEARBY_URL + "?" + urlencode(params)
    rows = []
    page_count = 0
    while True:
        resp = requests.get(url, timeout=30)
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            print("Google Places status:", data.get("status"), data.get("error_message"))
        for r in data.get("results", []):
            rows.append({
                "provider": "google",
                "name": r.get("name"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "price_level": r.get("price_level"),
                "lat": r.get("geometry", {}).get("location", {}).get("lat"),
                "lng": r.get("geometry", {}).get("location", {}).get("lng"),
                "address": r.get("vicinity"),
                "place_id": r.get("place_id"),
                "types": ",".join(r.get("types", [])),
                "business_status": r.get("business_status")
            })
        next_token = data.get("next_page_token")
        if not next_token:
            break
        page_count += 1
        if page_count > 3:  # safety
            break
        time.sleep(2)  # required wait before next page token becomes valid
        url = GOOGLE_NEARBY_URL + "?" + urlencode({
            "pagetoken": next_token,
            "key": api_key
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["place_id"]).reset_index(drop=True)
    return df

def yelp_search(location: str, radius_m: int, api_key: str, term="coffee", limit=50, include_reviews=False, max_pages=4) -> pd.DataFrame:
    headers = {"Authorization": f"Bearer {api_key}"}
    radius = min(radius_m, 40000)  # Yelp max ~40km
    rows = []
    for page in range(max_pages):
        params = {
            "term": term,
            "location": location,
            "radius": radius,
            "limit": limit,
            "offset": page * limit,
            "categories": "coffee,coffeeroasteries,cafes"
        }
        resp = requests.get(YELP_SEARCH_URL, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            print("Yelp error:", resp.status_code, resp.text)
            break
        data = resp.json()
        businesses = data.get("businesses", [])
        if not businesses:
            break
        for b in businesses:
            row = {
                "provider": "yelp",
                "name": b.get("name"),
                "rating": b.get("rating"),
                "review_count": b.get("review_count"),
                "price": b.get("price"),
                "categories": ",".join([c.get("title") for c in b.get("categories", []) if c.get("title")]),
                "lat": b.get("coordinates", {}).get("latitude"),
                "lng": b.get("coordinates", {}).get("longitude"),
                "address": " ".join([p for p in b.get("location", {}).get("display_address", []) if p]),
                "phone": b.get("display_phone"),
                "yelp_id": b.get("id"),
                "url": b.get("url")
            }
            if include_reviews and b.get("id"):
                rresp = requests.get(YELP_REVIEWS_URL_TMPL.format(id=b["id"]), headers=headers, timeout=30)
                if rresp.status_code == 200:
                    rdata = rresp.json()
                    rlist = rdata.get("reviews", [])
                    # Flatten up to 3 reviews
                    for i, rv in enumerate(rlist[:3]):
                        row[f"review_{i+1}_text"] = rv.get("text")
                        row[f"review_{i+1}_rating"] = rv.get("rating")
                        row[f"review_{i+1}_time"] = rv.get("time_created")
                time.sleep(0.1)
            rows.append(row)
        time.sleep(0.2)  # gentle rate limit
    df = pd.DataFrame(rows).drop_duplicates(subset=["yelp_id"]).reset_index(drop=True)
    return df

def merge_brands(google_df: pd.DataFrame, yelp_df: pd.DataFrame) -> pd.DataFrame:
    g = google_df.copy()
    y = yelp_df.copy()

    # Normalize names and rough geohash via rounding coords
    for df in (g, y):
        df["norm_name"] = df["name"].str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
        df["lat_r"] = df["lat"].round(3)
        df["lng_r"] = df["lng"].round(3)

    merged = pd.merge(
        g,
        y,
        left_on=["norm_name", "lat_r", "lng_r"],
        right_on=["norm_name", "lat_r", "lng_r"],
        how="outer",
        suffixes=("_google", "_yelp")
    )

    # Simple canonical fields
    merged["canonical_name"] = merged["name_google"].fillna(merged["name_yelp"])
    merged["canonical_lat"] = merged["lat_google"].fillna(merged["lat_yelp"])
    merged["canonical_lng"] = merged["lng_google"].fillna(merged["lng_yelp"])
    merged["source_flags"] = merged.apply(lambda r: "+".join([s for s in ["google"] if pd.notnull(r.get("place_id"))] + [s for s in ["yelp"] if pd.notnull(r.get("yelp_id"))]), axis=1)

    cols = ["canonical_name","canonical_lat","canonical_lng","address_google","address_yelp",
            "rating_google","user_ratings_total","rating_yelp","review_count","price","categories",
            "place_id","yelp_id","url","source_flags"]
    # Rename ratings for clarity
    merged = merged.rename(columns={
        "rating_google": "rating_google",
        "rating_yelp": "rating_yelp"
    })
    # Ensure columns exist
    for c in cols:
        if c not in merged.columns:
            merged[c] = None
    return merged[cols]

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Collect Tulsa coffee shop data from Google Places and Yelp")
    parser.add_argument("--location", default=env_or_default("SEARCH_LOCATION", "Tulsa, OK"))
    parser.add_argument("--radius", type=int, default=int(env_or_default("SEARCH_RADIUS_METERS", 15000)))
    parser.add_argument("--providers", nargs="+", choices=["google","yelp"], default=["google","yelp"])
    parser.add_argument("--include_yelp_reviews", action="store_true", help="Fetch up to 3 Yelp reviews per business")
    parser.add_argument("--outdir", default="data/raw")
    parser.add_argument("--merge", action="store_true", help="Create interim merged canonical file")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    google_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    yelp_key = os.getenv("YELP_API_KEY", "")

    google_df = pd.DataFrame()
    yelp_df = pd.DataFrame()

    if "google" in args.providers:
        if not google_key:
            print("WARNING: GOOGLE_PLACES_API_KEY missing; skipping Google collection.")
        else:
            print("Collecting from Google Places...")
            google_df = google_places_search(args.location, args.radius, google_key)
            google_df.to_csv(os.path.join(args.outdir, "google_places_coffee.csv"), index=False)
            print(f"Saved {len(google_df)} rows to {os.path.join(args.outdir,'google_places_coffee.csv')}")

    if "yelp" in args.providers:
        if not yelp_key:
            print("WARNING: YELP_API_KEY missing; skipping Yelp collection.")
        else:
            print("Collecting from Yelp...")
            yelp_df = yelp_search(args.location, args.radius, yelp_key, include_reviews=args.include_yelp_reviews)
            yelp_df.to_csv(os.path.join(args.outdir, "yelp_coffee.csv"), index=False)
            print(f"Saved {len(yelp_df)} rows to {os.path.join(args.outdir,'yelp_coffee.csv')}")

    if args.merge and (len(google_df) or len(yelp_df)):
        print("Merging canonical list...")
        merged = merge_brands(google_df, yelp_df)
        os.makedirs("data/interim", exist_ok=True)
        merged.to_csv("data/interim/merged_coffee_brands.csv", index=False)
        print(f"Merged file -> data/interim/merged_coffee_brands.csv with {len(merged)} rows")

if __name__ == "__main__":
    main()
