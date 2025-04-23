import argparse
import os

def load_config(file_path):
    """Load configuration from a .conf file."""
    config = {}
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split('=', 1)
            config[key.strip()] = value.strip().strip('"')
    return config

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Start Flask server with specified configuration file.'
    )
    parser.add_argument('--config', type=str, help='Path to the configuration file', required=True)
    parser.add_argument('-i', '--init', type=str, help='Initialize database. Use "base" to create base database schema', default="")
    # New argument for database migration
    parser.add_argument('--migrate', action='store_true', help='Migrate database to latest schema', default=False)
    return parser.parse_args()

class Config:
    def __init__(self, host, db_host, db_port, flask_port, db_name, db_user, db_password, debug, db_uri="default"):
        # HOST: Public host used for binding the Flask app.
        self.HOST = host
        # DB_HOST: Host address for the PostgreSQL database.
        self.DB_HOST = db_host
        self.DB_PORT = db_port
        self.FLASK_PORT = flask_port
        self.DB_NAME = db_name
        self.DB_USER = db_user
        self.DB_PASSWORD = db_password
        self.DB_DEBUG = debug
        # SQLALCHEMY_DATABASE_URI will be built later (for example, in your server.py)
        self.SQLALCHEMY_DATABASE_URI = db_uri
        # Set the debug flag appropriately.
        self.DEBUG = debug.lower() == 'true'
