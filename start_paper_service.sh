#!/bin/bash
cd services/paper-trading-service
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 7012 --reload
