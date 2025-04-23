from flask import Blueprint, request, jsonify, abort
from models.printers import Printer
from models import db
from datetime import datetime
import csv
from io import StringIO
import requests

printer_bp = Blueprint('printer', __name__, url_prefix='/printers')

# Global dictionary to store active HTTPPoller instances keyed by printer IP.
printerPollers = {}

def _parse_bool(val):
    """Utility to parse various boolean representations."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('1', 'true', 'yes', 'y', 't')
    return False

@printer_bp.route('/', methods=['GET'])
def get_printers():
    printers = Printer.query.all()
    return jsonify([p.to_dict() for p in printers]), 200

@printer_bp.route('/', methods=['POST'])
def add_printer():
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")
    
    required = ["ip_address", "port", "printer_name", "printer_model", "webcam_address", "webcam_port"]
    for f in required:
        if f not in data:
            abort(400, description=f"Missing required field: {f}")

    # parse optional times
    start_time = None
    end_time = None
    if data.get("available_start_time"):
        try:
            start_time = datetime.strptime(data["available_start_time"], "%H:%M:%S").time()
        except ValueError:
            abort(400, description="Invalid format for available_start_time; expected HH:MM:SS")
    if data.get("available_end_time"):
        try:
            end_time = datetime.strptime(data["available_end_time"], "%H:%M:%S").time()
        except ValueError:
            abort(400, description="Invalid format for available_end_time; expected HH:MM:SS")

    # parse heated_chamber flag
    heated = _parse_bool(data.get("heated_chamber", False))

    new_printer = Printer(
        ip_address             = data["ip_address"],
        port                   = int(data["port"]),
        webcam_address         = data["webcam_address"],
        webcam_port            = int(data["webcam_port"]),
        printer_name           = data["printer_name"],
        printer_model          = data["printer_model"],
        available_start_time   = start_time,
        available_end_time     = end_time,
        camera_resolution_width  = int(data.get("camera_resolution_width")) if data.get("camera_resolution_width") else None,
        camera_resolution_height = int(data.get("camera_resolution_height")) if data.get("camera_resolution_height") else None,
        camera_scaling_factor  = float(data.get("camera_scaling_factor")) if data.get("camera_scaling_factor") else None,
        heated_chamber         = heated
    )
    
    db.session.add(new_printer)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        abort(400, description="A printer with that IP address already exists.")
    
    return jsonify(new_printer.to_dict()), 201

@printer_bp.route('/<string:ip_address>', methods=['PUT'])
def update_printer(ip_address):
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")

    allowed = [
        "ip_address", "port", "printer_name", "printer_model",
        "webcam_address", "webcam_port", "available_start_time", "available_end_time", "status",
        "camera_resolution_width", "camera_resolution_height", "camera_scaling_factor",
        "heated_chamber"
    ]
    
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        abort(404, description=f"Printer with IP {ip_address} not found")
    
    for field, value in data.items():
        if field not in allowed:
            abort(400, description=f"Field '{field}' is not allowed to be updated")
        
        if field in ("port", "webcam_port", "camera_resolution_width", "camera_resolution_height"):
            try:
                setattr(printer, field, int(value))
            except ValueError:
                abort(400, description=f"Field '{field}' must be an integer")
        elif field == "camera_scaling_factor":
            try:
                setattr(printer, field, float(value))
            except ValueError:
                abort(400, description=f"Field '{field}' must be a number")
        elif field in ("available_start_time", "available_end_time"):
            if value:
                try:
                    parsed = datetime.strptime(value, "%H:%M:%S").time()
                    setattr(printer, field, parsed)
                except ValueError:
                    abort(400, description=f"Invalid format for {field}; expected HH:MM:SS")
            else:
                setattr(printer, field, None)
        elif field == "heated_chamber":
            setattr(printer, field, _parse_bool(value))
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
    
    ip = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400

    # Connectivity check
    try:
        test_url = f"http://{ip}:{printer.port}/server/files/list"
        resp = requests.get(test_url, params={"root": "gcodes"}, timeout=2)
        resp.raise_for_status()
        printer.status = "online"
    except Exception as e:
        printer.status = "offline"
        db.session.commit()
        return jsonify({"error": f"Printer unreachable: {e}"}), 500

    # Lazy import to avoid startup-time circulars
    from http_poller import HTTPPoller, update_printer_status_callback

    if ip in printerPollers:
        poller = printerPollers[ip]
    else:
        poller = HTTPPoller(
            printer,
            poll_interval=2,
            request_method="GET",
            callback=update_printer_status_callback
        )
        poller.start()
        printerPollers[ip] = poller

    db.session.commit()
    return jsonify({
        "message": "Printer connected and polling started.",
        "printer": printer.to_dict()
    }), 200

@printer_bp.route('/disconnect', methods=['POST'])
def disconnect_printer():
    data = request.get_json()
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")

    ip = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400

    # Lazy import so we don't force the module at load time
    from http_poller import HTTPPoller

    poller = printerPollers.pop(ip, None)
    if poller:
        poller.stop()

    printer.status = "disconnected"
    db.session.commit()
    return jsonify({"message": "Printer disconnected successfully."}), 200

@printer_bp.route('/upload_csv', methods=['POST'])
def upload_printers_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided with key 'file'"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    try:
        stream = StringIO(file.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        results = []

        # now require prepare_time & supported_materials too
        required_cols = [
            "ip_address", "port", "webcam_address", "webcam_port",
            "printer_name", "printer_model",
            "prepare_time", "supported_materials"
        ]

        for row in reader:
            # skip any row missing a required field
            if not all(row.get(c) for c in required_cols):
                continue

            # parse times
            start_time = None
            end_time   = None
            if row.get("available_start_time"):
                try:
                    start_time = datetime.strptime(row["available_start_time"], "%H:%M:%S").time()
                except ValueError:
                    pass
            if row.get("available_end_time"):
                try:
                    end_time = datetime.strptime(row["available_end_time"], "%H:%M:%S").time()
                except ValueError:
                    pass

            # parse numeric/boolean fields
            port        = int(row["port"])
            webcam_port = int(row["webcam_port"])
            heated      = _parse_bool(row.get("heated_chamber", False))

            # parse the two previously missing columns
            try:
                prepare_time = int(row["prepare_time"])
            except (ValueError, TypeError):
                prepare_time = 0
            supported_materials = row["supported_materials"]

            # optional camera fields
            cam_w = int(row["camera_resolution_width"])  if row.get("camera_resolution_width")  else None
            cam_h = int(row["camera_resolution_height"]) if row.get("camera_resolution_height") else None
            cam_s = float(row["camera_scaling_factor"])  if row.get("camera_scaling_factor")   else None

            # upsert
            printer = Printer.query.filter_by(ip_address=row["ip_address"]).first()
            if printer:
                printer.port                   = port
                printer.webcam_address         = row["webcam_address"]
                printer.webcam_port            = webcam_port
                printer.printer_name           = row["printer_name"]
                printer.printer_model          = row["printer_model"]
                printer.available_start_time   = start_time
                printer.available_end_time     = end_time
                printer.prepare_time           = prepare_time
                printer.supported_materials    = supported_materials
                printer.camera_resolution_width  = cam_w
                printer.camera_resolution_height = cam_h
                printer.camera_scaling_factor  = cam_s
                printer.heated_chamber         = heated
                results.append({"action": "updated", "printer": printer.to_dict()})
            else:
                new_p = Printer(
                    ip_address               = row["ip_address"],
                    port                     = port,
                    webcam_address           = row["webcam_address"],
                    webcam_port              = webcam_port,
                    printer_name             = row["printer_name"],
                    printer_model            = row["printer_model"],
                    available_start_time     = start_time,
                    available_end_time       = end_time,
                    prepare_time             = prepare_time,
                    supported_materials      = supported_materials,
                    camera_resolution_width  = cam_w,
                    camera_resolution_height = cam_h,
                    camera_scaling_factor    = cam_s,
                    heated_chamber           = heated
                )
                db.session.add(new_p)
                results.append({"action": "added", "printer": new_p.to_dict()})

        db.session.commit()
        return jsonify({
            "message": f"Processed {len(results)} rows",
            "results": results
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@printer_bp.route('/<string:ip_address>/details', methods=['GET'])
def printer_details_json(ip_address):
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"error": f"Printer with IP {ip_address} not found"}), 404

    data = printer.to_dict()
    data["gcodes"] = [g.to_dict() for g in printer.gcodes.all()]
    return jsonify(data), 200

@printer_bp.route('/status', methods=['GET'])
def update_printers_status():
    printers = Printer.query.all()
    updated = []
    for p in printers:
        try:
            url = f"http://{p.ip_address}:{p.port}/server/files/list"
            res = requests.get(url, params={"root": "gcodes"}, timeout=2)
            res.raise_for_status()
            p.status = "online"
        except Exception:
            p.status = "offline"
        updated.append({"ip_address": p.ip_address, "status": p.status})

    try:
        db.session.commit()
    except:
        db.session.rollback()

    return jsonify({"printers_status": updated}), 200
