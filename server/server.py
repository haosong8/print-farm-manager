from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import parse_arguments, load_config, Config

# Create a shared SQLAlchemy instance.
db = SQLAlchemy()

def create_app(config_file):
    """Factory function to create and configure the Flask app."""
    app = Flask(__name__)
    CORS(app)
    
    # Load configuration from file.
    config_data = load_config(config_file)
    server_config = Config(
        config_data['HOST'],
        config_data['DB_PORT'],
        config_data['FLASK_PORT'],
        config_data['DB_NAME'],
        config_data['DB_USER'],
        config_data['DB_PASSWORD'],
        config_data['DEBUG']
    )
    
    # Construct the PostgreSQL connection string using DB_PORT.
    server_config.SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{server_config.DB_USER}:{server_config.DB_PASSWORD}@"
        f"{server_config.HOST}:{server_config.DB_PORT}/{server_config.DB_NAME}"
    )
    
    # Load configuration into the Flask app.
    app.config.from_object(server_config)
    
    # Initialize SQLAlchemy with the app.
    db.init_app(app)
    
    # Register blueprints or endpoints (if any)
    # For example, if you have an api/ folder with blueprint registration:
    try:
        from api import register_blueprints
        register_blueprints(app)
    except ImportError:
        pass  # No blueprints defined yet.
    
    return app

if __name__ == '__main__':
    args = parse_arguments()
    app = create_app(args.config)
    
    # If the -i flag is provided with "base", initialize the database schema and exit.
    if args.init.lower() == "base":
        with app.app_context():
            print("Registered tables:", db.metadata.tables.keys())
            db.create_all()
            print("Base database initialized.")
        import sys
        sys.exit(0)
    
    # Otherwise, run the Flask server.
    print("Starting server with configuration:")
    print(f"Host: {app.config['HOST']}")
    print(f"Flask Port: {app.config['FLASK_PORT']}")
    print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.run(host=app.config['HOST'], port=int(app.config['FLASK_PORT']), debug=app.config['DEBUG'])
