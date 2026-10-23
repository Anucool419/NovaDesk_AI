#!/bin/bash
# 1. Activate Azure's virtual environment
source /tmp/*df28*/antenv/bin/activate 2>/dev/null || source antenv/bin/activate 2>/dev/null

# 2. Run FastAPI in the background on port 8000
(cd fast && python -m uvicorn main:app --host 127.0.0.1 --port 8001) &

# 3. Run Chainlit in the foreground on port 8080 (the public-facing port) changing it back to 8000 as Azure wants it as default
python -m chainlit run app.py --host 0.0.0.0 --port 8000
