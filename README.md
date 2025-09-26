# Tulsa Coffee AI — Step 1: Data Collection

This starter collects coffee shop data for Tulsa from **Google Places** and **Yelp Fusion** APIs.
- Outputs clean CSVs in `data/raw/`
- Handles pagination, basic rate limiting, and deduping
- Stores secrets via `.env`

## Quickstart
1. Create a virtualenv and install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add your API keys.
3. Run the collector:
   ```bash
   python collect_data.py --location "Tulsa, OK" --radius 15000 --providers google yelp
   ```

## Outputs
- `data/raw/google_places_coffee.csv`
- `data/raw/yelp_coffee.csv`
- `data/interim/merged_coffee_brands.csv` (name/location dedupe for later NLP)

## Notes
- Google Places returns **name, rating, user_ratings_total, geometry, place_id**.
- Yelp returns **name, rating, review_count, price, categories, coordinates, yelp_id**, plus **up to 3 latest reviews** per business (optional extra call).
- Reviews from Google are restricted; for this quick win we use Yelp reviews text.



---

## Step 2 – Analysis & Sentiment

1. Install extra deps (already added to `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```
2. Run the analyzer:
   ```bash
   python analyze.py
   ```
3. Outputs:
   - `data/interim/step2_canonical.csv`
   - `data/interim/step2_yelp_reviews_scored.csv`
   - `data/interim/step2_ranked_shops.csv`
   - `data/outputs/top_stars.png`
   - `data/outputs/top_volume.png`
   - `data/outputs/reviews_wordcloud.png` (if Yelp reviews were fetched)

## Step 3 – Streamlit App (Optional but flashy)
1. Make sure Step 2 produced the interim CSVs.
2. Run:
   ```bash
   streamlit run app/streamlit_app.py
   ```
3. Open the local URL shown in your terminal to interact.

