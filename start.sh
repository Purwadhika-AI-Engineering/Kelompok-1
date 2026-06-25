#!/bin/bash
# Jalankan FastAPI di background dan Streamlit di foreground.
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
streamlit run app/main.py --server.port 8080 --server.address 0.0.0.0