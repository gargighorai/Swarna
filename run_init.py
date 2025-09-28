# run_init.py
from app import app
from flask_migrate import init
with app.app_context():
    init(directory='migrations')