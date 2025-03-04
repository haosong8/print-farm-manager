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
    
    # Mark the printer as offline until connected.
    new_printer.is_online = False
    
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
      - Checks connectivity to the printer.
      - Initiates (or reuses) the Moonraker websocket connection.
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
    from services.realtime import check_printer_connection, get_ws_subscription

    # Check if there is already an active websocket connection for this printer.
    if check_printer_connection(printer):
        # Ensure a new subscription is added for this connection.
        get_ws_subscription(printer)
        return jsonify({
            "message": "This printer is already connected and the websocket is active.",
            "printer": printer.to_dict()
        }), 200

    # Otherwise, try to initiate the connection by calling get_ws_subscription.
    # This function will create a new websocket connection if one doesn't exist.
    get_ws_subscription(printer)
    
    return jsonify({
        "message": "Printer connected successfully and websocket initiated.",
        "printer": printer.to_dict()
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