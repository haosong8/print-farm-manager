from flask import Blueprint, request, jsonify, abort, Response, stream_with_context
from models.printers import Printer
from models import db
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import time
import json

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
    
    db.session.add(new_printer)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description="A printer with that IP address already exists.")
    
    return jsonify(new_printer.to_dict()), 201

@printer_bp.route('/connect', methods=['POST'])
def connect_printer():
    """
    Connect a printer by IP address. Expects a JSON body with:
    {
        "ip_address": "192.168.1.100"
    }
    When successfully connected, this endpoint:
      - Sends an initial JSON-RPC request to retrieve printer state.
      - Checks connectivity to the printer.
      - Reuses an existing Moonraker websocket connection if one exists, or initiates a new one.
      - Updates the printer status based on the response.
      - Returns the initial state along with the printer data.
    """
    data = request.get_json()
    print(data)
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400

    # Send initial JSON-RPC request to get the printer objects state.
    import requests, random
    PAYLOAD_TEMPLATE = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None,
                "print_stats": None,
            }
        }
    }
    # Generate a random ID for the JSON-RPC request.
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
        # Extract status from the response.
        # We use print_stats.state if available.
        status_value = "Idle"  # fallback default
        if "result" in initial_state and "status" in initial_state["result"]:
            print_stats = initial_state["result"]["status"].get("print_stats", {})
            if "state" in print_stats:
                status_value = print_stats["state"]
        print(f"Extracted printer status: {status_value}")
    except Exception as e:
        return jsonify({"error": f"Failed to fetch initial state: {str(e)}"}), 500

    # Lazy import realtime functions.
    from services.realtime import check_printer_connection, get_ws_subscription

    # Check if there is already an active websocket connection for this printer.
    if check_printer_connection(printer):
        # Reuse the existing connection: add a new subscription if needed.
        get_ws_subscription(printer)
        printer.status = status_value
        db.session.commit()
        return jsonify({
            "message": "Existing printer connection reused; status updated.",
            "printer": printer.to_dict(),
            "initial_state": initial_state
        }), 200

    # Otherwise, initiate a new connection.
    get_ws_subscription(printer)
    printer.status = status_value
    db.session.commit()
    
    return jsonify({
        "message": "Printer connected successfully, websocket initiated, and status updated.",
        "printer": printer.to_dict(),
        "initial_state": initial_state
    }), 200

@printer_bp.route('/connect/stream/<string:ip_address>', methods=['GET'])
def connect_printer_stream(ip_address):
    """
    SSE endpoint for streaming real-time printer data.
    This endpoint reuses the existing Moonraker websocket connection (started by /connect)
    by creating a new subscription. Clients connect here to receive SSE updates.
    """
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"error": "Printer not found"}), 404

    from services.realtime import get_ws_subscription, remove_ws_subscription
    import queue

    sub_q = get_ws_subscription(printer)

    def event_stream():
        try:
            while True:
                try:
                    # Wait for a message; if none, use an empty keepalive message.
                    message = sub_q.get(timeout=10)
                except queue.Empty:
                    message = "{}"
                # Try to yield the message; if the connection is aborted, break out.
                try:
                    yield f"data: {message}\n\n"
                except Exception as e:
                    print(f"[SSE][{ip_address}] Error yielding data: {e}")
                    break
        finally:
            remove_ws_subscription(printer, sub_q)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(event_stream()), headers=headers, mimetype="text/event-stream")


@printer_bp.route('/disconnect', methods=['POST'])
def disconnect_printer_endpoint():
    """
    Disconnect a printer by IP address. Expects a JSON body with:
    {
        "ip_address": "192.168.1.100"
    }
    This endpoint will close the active websocket connection (if any)
    for the specified printer.
    """
    data = request.get_json()
    if not data or "ip_address" not in data:
        abort(400, description="ip_address field is required")
    
    ip_address = data["ip_address"]
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"message": "Printer not found"}), 400
    
    from services.realtime import disconnect_printer as disconnect_printer_func
    disconnect_printer_func(printer)
    
    return jsonify({"message": "Printer disconnected"}), 200