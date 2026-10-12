#!/bin/bash

# 1. Start FastAPI in the background on port 8000
# Replace 'main:app' with your actual FastAPI filename and app instance
uvicorn fast.main:app --host 127.0.0.1 --port 8000 &

# 2. Start Chainlit in the foreground on port 8001
chainlit run app.py --host 0.0.0.0 --port 8001 --headless
