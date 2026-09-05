#!/usr/bin/env bash
# Convenience script: sets up venv, installs deps, seeds DB, runs the API.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example - add your Razorpay TEST keys if you have them."
fi

uvicorn app.main:app --reload --port 8000
