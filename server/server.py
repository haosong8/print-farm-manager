import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
from config import parse_arguments, load_config, Config
from models import db  # shared DB instance
from extensions import socketio
from sockets.utils import set_app_instance  # import the setter
import sys

def create_app(config_file=None):
    # Allow a default config file if none is provided.
    if config_file is None:
        config_file = os.environ.get("CONFIG_FILE", "config.conf")
    
    app = Flask(__name__)
    CORS(app)
    
    # Load configuration from the specified file.
    config_data = load_config(config_file)
    server_config = Config(
        config_data['HOST'],
        config_data['DB_HOST'],
        config_data['DB_PORT'],
        config_data['FLASK_PORT'],
        config_data['DB_NAME'],
        config_data['DB_USER'],
        config_data['DB_PASSWORD'],
        config_data['DEBUG']
    )
    
    # Build the SQLALCHEMY_DATABASE_URI using the correct attribute names.
    server_config.SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{server_config.DB_USER}:{server_config.DB_PASSWORD}@"
        f"{server_config.DB_HOST}:{server_config.DB_PORT}/{server_config.DB_NAME}"
    )
    print(server_config.SQLALCHEMY_DATABASE_URI)
    
    app.config.from_object(server_config)
    db.init_app(app)
    
    try:
        from api import register_blueprints
        register_blueprints(app)
    except ImportError:
        pass

    socketio.init_app(app, async_mode="eventlet", cors_allowed_origins="*")
    print("SocketIO instance:", socketio)
    
    @socketio.on("connect")
    def handle_connect():
        printer_ip = request.args.get("printerIp")
        if printer_ip:
            join_room(printer_ip)
            print(f"Client joined room for printer {printer_ip}")
        else:
            print("Client connected without printerIp query parameter.")
    
    return app

if __name__ == '__main__':
    args = parse_arguments()
    app = create_app(args.config)  # Use the provided config file.
    
    # If a migration flag is provided, run the migration and exit.
    if any(flag in sys.argv for flag in ["migrate", "-m"]):
        with app.app_context():
            from flask_migrate import upgrade
            upgrade()
            print("Database migration applied successfully.")
        sys.exit(0)
    
    # If the init flag is set to "base", create all tables and exit.
    if args.init.lower() == "base":
        with app.app_context():
            print("Registered tables:", list(db.metadata.tables.keys()))
            db.create_all()
            print("Database tables and relationships created successfully.")
        sys.exit(0)
    
    with app.app_context():
        from models.printers import Printer
        printers = Printer.query.all()
        for printer in printers:
            printer.status = "disconnected"
        db.session.commit()
        print("All printer statuses have been set to disconnected.")
    
    # Set the global app instance for socket usage.
    from sockets.utils import set_app_instance
    set_app_instance(app)
    
    print("Starting server with configuration:")
    print(f"Host: {app.config['HOST']}")
    print(f"Flask Port: {app.config['FLASK_PORT']}")
    print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    socketio.run(app, host=app.config['HOST'], port=int(app.config['FLASK_PORT']),
                 debug=app.config['DEBUG'], use_reloader=False)
