from flask import Blueprint, request, jsonify, abort
from models.printers import Printer
from models import db
from datetime import datetime
import json
import random
import requests

printer_bp = Blueprint('printer', __name__, url_prefix='/printers')

# Global dictionary to store active MoonrakerSocket instances keyed by printer IP.
moonrakerSockets = {}

@printer_bp.route('/', methods=['GET'])
def get_printers():
    printers = Printer.query.all()
    printer_list = [printer.to_dict() for printer in printers]
    return jsonify(printer_list), 200

@printer_bp.route('/', methods=['POST'])
def add_printer():
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")
    
    required_fields = ["ip_address", "port", "printer_name", "printer_model"]
    for field in required_fields:
        if field not in data:
            abort(400, description=f"Missing required field: {field}")
    
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
    
    new_printer = Printer(
        ip_address=data["ip_address"],
        port=int(data["port"]),
        printer_name=data["printer_name"],
        printer_model=data["printer_model"],
        available_start_time=available_start_time,
        available_end_time=available_end_time
    )
    
    db.session.add(new_printer)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description="A printer with that IP address already exists.")
    
    return jsonify(new_printer.to_dict()), 201

@printer_bp.route('/connect', methods=['POST'])
def connect_printer():
    data = request.get_json()
    print(data)
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400

    # Prepare an initial JSON-RPC request.
    PAYLOAD_TEMPLATE = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None,
                "print_stats": None,
                "display_status": None,
            }
        }
    }
    random_id = random.randint(1000, 9999)
    payload = PAYLOAD_TEMPLATE.copy()
    payload["id"] = random_id

    try:
        rpc_url = f"http://{ip_address}:{printer.port}/server/jsonrpc"
        resp = requests.post(rpc_url, json=payload, timeout=5)
        print(f"Response status: {resp.status_code}")
        print(f"Response text: '{resp.text}'")
        if not resp.text.strip():
            raise ValueError("Empty response received")
        initial_state = resp.json()
        print(f"Initial state: {initial_state}")
        if "result" in initial_state and "status" in initial_state["result"]:
            print_stats = initial_state["result"]["status"].get("print_stats", {})
            if "state" in print_stats:
                status_value = print_stats["state"]
        print(f"Extracted printer status: {status_value}")
    except Exception as e:
        return jsonify({"error": f"Failed to fetch initial state: {str(e)}"}), 500

    # Import MoonrakerSocket from your sockets package.
    from sockets.moonraker_socket import MoonrakerSocket

    # If a socket for this printer already exists, reuse it.
    if ip_address in moonrakerSockets:
        print(f"Reusing existing MoonrakerSocket for printer {ip_address}")
        ms = moonrakerSockets[ip_address]
    else:
        print(f"Starting MoonrakerSocket for printer {ip_address}")
        ms = MoonrakerSocket(printer, poll_interval=1)
        ms.start()
        moonrakerSockets[ip_address] = ms

    # Update the printer status in the database.
    printer.status = status_value
    db.session.commit()
    
    return jsonify({
        "message": "Printer connected successfully, websocket initiated, and status updated.",
        "printer": printer.to_dict(),
        "initial_state": initial_state
    }), 200

@printer_bp.route('/disconnect', methods=['POST'])
def disconnect_printer_endpoint():
    data = request.get_json()
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400
    
    # Disconnect the MoonrakerSocket if it exists.
    from sockets.moonraker_socket import MoonrakerSocket
    if ip_address in moonrakerSockets:
        ms = moonrakerSockets[ip_address]
        ms.disconnect()
        del moonrakerSockets[ip_address]
    
    printer.status = "disconnected"
    db.session.commit()
    
    return jsonify({"message": "Printer disconnected"}), 200
