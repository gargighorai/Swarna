# Imports for the application
from app import app, db

# Imports for Flask-Migrate commands
from flask_migrate import init, migrate, upgrade

# Run the database migration commands
with app.app_context():
    # This command initializes the migration directory.
    # It only needs to be run once.
    print("Initializing migration directory...")
    init(directory='migrations')

    # This command creates a new migration script based on changes to your models.
    print("Creating migration script...")
    migrate(directory='migrations', message='Initial migration')
    
    # This command applies the migration to your database.
    print("Upgrading database schema...")
    upgrade(directory='migrations')

    print("Migration process complete.")
