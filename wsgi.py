"""正式環境的進入點：gunicorn wsgi:app"""
from app import create_app

app = create_app()
