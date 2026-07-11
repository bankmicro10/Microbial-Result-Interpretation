"""Vercel serverless entry — expose Flask WSGI app (@vercel/python จับตัวแปร `app`)"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, os.path.join(ROOT, "prototype"))

from app import app  # noqa: E402  (webapp/app.py)
