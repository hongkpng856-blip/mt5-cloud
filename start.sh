#!/bin/bash
cd server
pip install -r requirements.txt
gunicorn -k eventlet -w 1 -b 0.0.0.0:${PORT:-5000} app:app
