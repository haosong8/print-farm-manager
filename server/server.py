import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
from config import parse_arguments, load_config, Config
from models import db  # shared DB instance
from extensions import socketio
from sockets.utils import set_app_instance  # import the setter

def create_app(config_file):
    app = Flask(__name__)
    CORS(app)
    
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
    
    server_config.SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{server_config.DB_USER}:{server_config.DB_PASSWORD}@"
        f"{server_config.HOST}:{server_config.DB_PORT}/{server_config.DB_NAME}"
    )
    
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
    app = create_app(args.config)
    
    # Set the global app instance for socket usage.
    from sockets.utils import set_app_instance
    set_app_instance(app)
    
    if args.init.lower() == "base":
        with app.app_context():
            print("Registered tables:", list(db.metadata.tables.keys()))
            db.create_all()
            print("Database tables and relationships created successfully.")
        import sys
        sys.exit(0)
    
    with app.app_context():
        from models.printers import Printer
        printers = Printer.query.all()
        for printer in printers:
            printer.status = "disconnected"
        db.session.commit()
        print("All printer statuses have been set to disconnected.")
    
    # (Optionally start MoonrakerSocket instances here if needed.)
    
    print("Starting server with configuration:")
    print(f"Host: {app.config['HOST']}")
    print(f"Flask Port: {app.config['FLASK_PORT']}")
    print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    socketio.run(app, host=app.config['HOST'], port=int(app.config['FLASK_PORT']),
                 debug=app.config['DEBUG'], use_reloader=False)
