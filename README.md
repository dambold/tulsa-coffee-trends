# ☕ Tulsa Coffee Trends — AI-Powered Dashboard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.37+-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight AI + data project that pulls **real-time Tulsa coffee shop data** from Google Places (and optionally Yelp), cleans and ranks them, and displays an **interactive dashboard** with maps, bar charts, and keyword insights from review text.

---

## 🚀 Features

- ✅ **Google Places Integration** – Fetches shop names, ratings, locations & review counts  
- ✅ **Optional Yelp Reviews** – Adds NLP sentiment analysis (VADER) and word cloud  
- ✅ **Ranking Engine** – Combines rating, review volume, and sentiment into a single score  
- ✅ **Interactive Dashboard** – Streamlit app with maps, top shop charts, and data table  
---

## 🛠 Setup & Installation

### 1. Clone This Repo
```bash
git clone https://github.com/your-username/tulsa_coffee_ai.git
cd tulsa_coffee_ai


# Tulsa Coffee AI — Step 1: Data Collection

This starter collects coffee shop data for Tulsa from **Google Places** API.
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
- `data/interim/merged_coffee_brands.csv` (name/location dedupe for later NLP)

## Notes
- Google Places returns **name, rating, user_ratings_total, geometry, place_id**
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
---

## 📊 Tech Stack

Python 3.10+

Pandas – Data cleaning & aggregation

NLTK (VADER) – Sentiment analysis

Matplotlib + WordCloud – Visualization

Streamlit – Interactive web app

## 🔒 Security Notes

Never commit your real .env file.

Always regenerate your API keys if accidentally pushed to a public repo.

This repo includes .env.example as a safe template for others to replicate.

## 📄 License

This project is licensed under the MIT License

## ✨ Author

Built by Michael Dambold, data analyst, AI builder, and coffee enthusiast ☕.
