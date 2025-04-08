from flask import Blueprint, request, jsonify, abort
from models.printers import Printer
from models import db
from datetime import datetime
import csv
from io import StringIO
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
    
    required_fields = ["ip_address", "port", "printer_name", "printer_model", "webcam_address", "webcam_port"]
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
        ip_address = data["ip_address"],
        port = int(data["port"]),
        webcam_address = data["webcam_address"],
        webcam_port = int(data["webcam_port"]),
        printer_name = data["printer_name"],
        printer_model = data["printer_model"],
        available_start_time = available_start_time,
        available_end_time = available_end_time,
        # New camera configuration fields (optional)
        camera_resolution_width = int(data["camera_resolution_width"]) if data.get("camera_resolution_width") else None,
        camera_resolution_height = int(data["camera_resolution_height"]) if data.get("camera_resolution_height") else None,
        camera_scaling_factor = float(data["camera_scaling_factor"]) if data.get("camera_scaling_factor") else None
    )
    
    db.session.add(new_printer)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description="A printer with that IP address already exists.")
    
    return jsonify(new_printer.to_dict()), 201

@printer_bp.route('/<string:ip_address>', methods=['PUT'])
def update_printer(ip_address):
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")

    # Allowed fields for update.
    allowed_fields = [
        "ip_address", "port", "printer_name", "printer_model",
        "webcam_address", "webcam_port", "available_start_time", "available_end_time", "status",
        "camera_resolution_width", "camera_resolution_height", "camera_scaling_factor"
    ]
    
    # Retrieve the printer by its current IP address.
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        abort(404, description=f"Printer with IP {ip_address} not found")
    
    # Update each allowed field if provided.
    for field, value in data.items():
        if field not in allowed_fields:
            abort(400, description=f"Field '{field}' is not allowed to be updated")
        
        if field in ["port", "webcam_port", "camera_resolution_width", "camera_resolution_height"]:
            try:
                setattr(printer, field, int(value))
            except ValueError:
                abort(400, description=f"Field '{field}' must be an integer")
        elif field == "camera_scaling_factor":
            try:
                setattr(printer, field, float(value))
            except ValueError:
                abort(400, description=f"Field '{field}' must be a number")
        elif field in ["available_start_time", "available_end_time"]:
            if value:
                try:
                    parsed_time = datetime.strptime(value, "%H:%M:%S").time()
                    setattr(printer, field, parsed_time)
                except ValueError:
                    abort(400, description=f"Invalid format for {field}; expected HH:MM:SS")
            else:
                setattr(printer, field, None)
        else:
            setattr(printer, field, value)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))
    
    return jsonify(printer.to_dict()), 200

@printer_bp.route('/connect', methods=['POST'])
def connect_printer():
    data = request.get_json()
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400

    # Instead of sending an HTTP JSON-RPC request, we simply open the MoonrakerSocket.
    from sockets.moonraker_socket import MoonrakerSocket

    if ip_address in moonrakerSockets:
        print(f"Reusing existing MoonrakerSocket for printer {ip_address}")
        ms = moonrakerSockets[ip_address]
    else:
        print(f"Starting MoonrakerSocket for printer {ip_address}")
        ms = MoonrakerSocket(printer, poll_interval=1)
        ms.start()
        moonrakerSockets[ip_address] = ms

    # Update the printer status (this may be further updated by the websocket polling)
    printer.status = "connected"
    db.session.commit()
    
    return jsonify({
        "message": "Printer connected successfully, websocket initiated, and status updated.",
        "printer": printer.to_dict()
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
    
    from sockets.moonraker_socket import MoonrakerSocket
    
    if ip_address in moonrakerSockets:
        ms = moonrakerSockets[ip_address]
        ms.disconnect()
        del moonrakerSockets[ip_address]
    
    printer.status = "disconnected"
    db.session.commit()
    
    return jsonify({"message": "Printer disconnected"}), 200

@printer_bp.route('/upload_csv', methods=['POST'])
def upload_printers_csv():
    """
    Endpoint to upload printers via a CSV file.
    The endpoint expects a file to be sent as form-data under the key "file".
    It will update existing printers (by ip_address) and add new ones as needed.
    Expected CSV headers:
      ip_address, port, webcam_address, webcam_port, printer_name, printer_model,
      available_start_time, available_end_time, prepare_time, supported_materials, status,
      camera_resolution_width, camera_resolution_height, camera_scaling_factor
    Times should be in HH:MM:SS format.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided in form-data with key 'file'"}), 400

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        stream = StringIO(file.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        results = []
        for row in reader:
            required_fields = ["ip_address", "port", "webcam_address", "webcam_port", "printer_name", "printer_model"]
            if not all(row.get(field) for field in required_fields):
                print(row)
                continue

            available_start_time = None
            available_end_time = None
            if row.get("available_start_time"):
                try:
                    available_start_time = datetime.strptime(row["available_start_time"], "%H:%M:%S").time()
                except ValueError:
                    available_start_time = None
            if row.get("available_end_time"):
                try:
                    available_end_time = datetime.strptime(row["available_end_time"], "%H:%M:%S").time()
                except ValueError:
                    available_end_time = None

            try:
                port = int(row["port"])
                webcam_port = int(row["webcam_port"])
            except ValueError:
                continue

            prepare_time = int(row["prepare_time"]) if row.get("prepare_time") else None
            supported_materials = row.get("supported_materials", "")
            status = row.get("status", "disconnected")

            # New camera configuration fields.
            camera_resolution_width = int(row["camera_resolution_width"]) if row.get("camera_resolution_width") else None
            camera_resolution_height = int(row["camera_resolution_height"]) if row.get("camera_resolution_height") else None
            camera_scaling_factor = float(row["camera_scaling_factor"]) if row.get("camera_scaling_factor") else None

            printer = Printer.query.filter_by(ip_address=row["ip_address"]).first()
            if printer:
                printer.port = port
                printer.webcam_address = row["webcam_address"]
                printer.webcam_port = webcam_port
                printer.printer_name = row["printer_name"]
                printer.printer_model = row["printer_model"]
                printer.available_start_time = available_start_time
                printer.available_end_time = available_end_time
                printer.prepare_time = prepare_time
                printer.supported_materials = supported_materials
                printer.status = status
                printer.camera_resolution_width = camera_resolution_width
                printer.camera_resolution_height = camera_resolution_height
                printer.camera_scaling_factor = camera_scaling_factor
                results.append({"action": "updated", "printer": printer.to_dict()})
            else:
                new_printer = Printer(
                    ip_address = row["ip_address"],
                    port = port,
                    webcam_address = row["webcam_address"],
                    webcam_port = webcam_port,
                    printer_name = row["printer_name"],
                    printer_model = row["printer_model"],
                    available_start_time = available_start_time,
                    available_end_time = available_end_time,
                    prepare_time = prepare_time,
                    supported_materials = supported_materials,
                    status = status,
                    camera_resolution_width = camera_resolution_width,
                    camera_resolution_height = camera_resolution_height,
                    camera_scaling_factor = camera_scaling_factor,
                )
                db.session.add(new_printer)
                results.append({"action": "added", "printer": new_printer.to_dict()})
        db.session.commit()
        return jsonify({
            "message": f"Processed {len(results)} printer rows.",
            "results": results
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@printer_bp.route('/<string:ip_address>/details', methods=['GET'])
def printer_details_json(ip_address):
    """
    Returns detailed information about a printer and its associated gcodes as JSON.
    This endpoint is intended for consumption by your React frontend.
    """
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"error": f"Printer with IP {ip_address} not found"}), 404

    gcodes = printer.gcodes.all()
    printer_data = printer.to_dict()
    printer_data["gcodes"] = [g.to_dict() for g in gcodes]
    return jsonify(printer_data), 200
