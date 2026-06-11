# yt-ex-c-pb
Script buat ambil data video trending + komentar YouTube per negara.

## Install
```pip install pandas pyarrow google-api-python-client pytz```

## Setup
1. Isi API key di main.py
   api_key = "YOUR_KEY"
2. Bikin kode_negara.json
   {"kode_negara": ["ID", "US"]}

## Run
python main.py

## Output
- komentar_only_ID_20260611.parquet
- data_gabungan_ID_20260611.parquet

Note: Kuota 10,000 unit/hari. Auto stop kalau habis.