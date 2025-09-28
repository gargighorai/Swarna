# run_migrate.py
from app import app, db
from flask_migrate import migrate, upgrade
with app.app_context():
    migrate(directory='migrations', message='Initial migration')
    upgrade(directory='migrations')