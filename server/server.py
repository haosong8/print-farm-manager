from flask import Flask
from flask_cors import CORS
from config import parse_arguments, load_config, Config
from models import db  # Import the shared db instance from models/__init__.py
from extensions import socketio

def create_app(config_file):
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
    
    # Register blueprints (if any)
    try:
        from api import register_blueprints
        register_blueprints(app)
    except ImportError:
        pass

    socketio.init_app(app)
    print("SocketIO instance:", socketio)
    
    return app

if __name__ == '__main__':
    args = parse_arguments()
    app = create_app(args.config)
    
    if args.init.lower() == "base":
        with app.app_context():
            print("Registered tables:", list(db.metadata.tables.keys()))
            db.create_all()
            print("Database tables and relationships created successfully.")
        import sys
        sys.exit(0)
    
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    try:
        from services.realtime import start_realtime_scheduler
        start_realtime_scheduler(app, socketio, interval=10)
    except ImportError:
        pass
    
    print("Starting server with configuration:")
    print(f"Host: {app.config['HOST']}")
    print(f"Flask Port: {app.config['FLASK_PORT']}")
    print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Run server with reloader disabled to avoid duplicate app instances.
    socketio.run(app, host=app.config['HOST'], port=int(app.config['FLASK_PORT']), debug=app.config['DEBUG'], use_reloader=False)
