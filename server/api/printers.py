from flask import Blueprint, request, jsonify, abort
from models.printers import Printer
from models import db
from datetime import datetime

printer_bp = Blueprint('printer', __name__, url_prefix='/printers')

@printer_bp.route('/', methods=['GET'])
def get_printers():
    """
    Retrieves all printers stored in the database.
    """
    printers = Printer.query.all()
    printer_list = [printer.to_dict() for printer in printers]
    return jsonify(printer_list), 200

@printer_bp.route('/', methods=['POST'])
def add_printer():
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")
    
    # Validate required fields.
    required_fields = ["ip_address", "port", "printer_name", "printer_model"]
    for field in required_fields:
        if field not in data:
            abort(400, description=f"Missing required field: {field}")
    
    # Parse optional time fields (expected format "HH:MM:SS")
    available_start_time = None
    available_end_time = None
    if "available_start_time" in data and data["available_start_time"]:
        try:
            available_start_time = datetime.strptime(data["available_start_time"], "%H:%M:%S").time()
        except ValueError:
            abort(400, description="Invalid format for available_start_time; expected HH:MM:SS")
    if "available_end_time" in data and data["available_end_time"]:
        try:
            available_end_time = datetime.strptime(data["available_end_time"], "%H:%M:%S").time()
        except ValueError:
            abort(400, description="Invalid format for available_end_time; expected HH:MM:SS")
    
    # Create the new printer.
    new_printer = Printer(
        ip_address=data["ip_address"],
        port=int(data["port"]),
        printer_name=data["printer_name"],
        printer_model=data["printer_model"],
        available_start_time=available_start_time,
        available_end_time=available_end_time
    )
    
    # Optionally set initial state; here we mark the printer as offline until connected.
    new_printer.is_online = False
    
    db.session.add(new_printer)
    db.session.commit()
    
    return jsonify(new_printer.to_dict()), 201

@printer_bp.route('/connect', methods=['POST'])
def connect_printer():
    """
    Connect a printer by IP address. Expects a JSON body with:
    {
        "ip_address": "192.168.1.100"
    }
    """
    data = request.get_json()
    print(data)
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400
    
    # Lazy import realtime functions.
    from services.realtime import check_printer_connection, start_printer_scheduler

    if check_printer_connection(printer):
        printer.is_online = True
        db.session.commit()
        
        # Import shared SocketIO instance from extensions
        from extensions import socketio
        
        start_printer_scheduler(printer, socketio, interval=10)
        
        return jsonify({
            "message": "Printer connected successfully and polling started.",
            "printer": printer.to_dict()
        }), 200
    else:
        printer.is_online = False
        db.session.commit()
        return jsonify({
            "message": "Printer connection failed.",
            "printer": printer.to_dict()
        }), 400