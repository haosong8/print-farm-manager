from flask import Blueprint, request, jsonify, abort
from models.scheduled_print import ScheduledPrint
from models import db
from datetime import datetime

scheduled_print_bp = Blueprint('scheduled_print', __name__, url_prefix='/scheduled_prints')

@scheduled_print_bp.route('/', methods=['GET'])
def get_scheduled_prints():
    """
    Fetch all scheduled prints from the database and return them as JSON.
    """
    scheduled_prints = ScheduledPrint.query.all()
    scheduled_list = [sp.to_dict() for sp in scheduled_prints]
    return jsonify(scheduled_list), 200

@scheduled_print_bp.route('/<int:scheduled_id>', methods=['GET'])
def get_scheduled_print(scheduled_id):
    """
    Fetch a single scheduled print by its ID.
    """
    scheduled_print = ScheduledPrint.query.get(scheduled_id)
    if scheduled_print is None:
        abort(404, description=f"Scheduled print with id {scheduled_id} not found")
    return jsonify(scheduled_print.to_dict()), 200

@scheduled_print_bp.route('/', methods=['POST'])
def add_scheduled_print():
    """
    Create a new scheduled print.

    Expected JSON payload example:
    {
       "deadline": "2025-06-01T15:00:00",
       "gcode_id": 10,
       "assigned_printer_id": 2,         // Optional
       "scheduled_start_time": "2025-06-01T14:30:00",  // Optional
       "status": "pending",              // Optional, defaults to "pending"
       "product_id": 5                   // Optional, if part of a product package
    }
    """
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")

    # Make sure the required fields are provided.
    deadline_str = data.get("deadline")
    gcode_id = data.get("gcode_id")
    if not deadline_str or gcode_id is None:
        abort(400, description="Missing required fields: deadline, gcode_id")

    try:
        deadline = datetime.fromisoformat(deadline_str)
    except ValueError:
        abort(400, description="Invalid deadline format; use ISO format (YYYY-MM-DDTHH:MM:SS)")

    # Parse the optional fields.
    scheduled_start_time = None
    if data.get("scheduled_start_time"):
        try:
            scheduled_start_time = datetime.fromisoformat(data.get("scheduled_start_time"))
        except ValueError:
            abort(400, description="Invalid scheduled_start_time format; use ISO format (YYYY-MM-DDTHH:MM:SS)")

    new_sp = ScheduledPrint(
        deadline=deadline,
        gcode_id=data.get("gcode_id"),
        assigned_printer_id=data.get("assigned_printer_id"),
        scheduled_start_time=scheduled_start_time,
        status=data.get("status", "pending"),
        product_id=data.get("product_id")
    )

    db.session.add(new_sp)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))

    return jsonify(new_sp.to_dict()), 201

@scheduled_print_bp.route('/<int:scheduled_id>', methods=['PUT'])
def update_scheduled_print(scheduled_id):
    """
    Update an existing scheduled print.
    Accepts a JSON payload containing any of these fields to update:
       - deadline (in ISO format)
       - gcode_id
       - assigned_printer_id
       - scheduled_start_time (in ISO format)
       - status
       - product_id
    """
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")

    scheduled_print = ScheduledPrint.query.get(scheduled_id)
    if scheduled_print is None:
        abort(404, description=f"Scheduled print with id {scheduled_id} not found")

    if "deadline" in data:
        deadline_str = data.get("deadline")
        if deadline_str:
            try:
                scheduled_print.deadline = datetime.fromisoformat(deadline_str)
            except ValueError:
                abort(400, description="Invalid deadline format; use ISO format (YYYY-MM-DDTHH:MM:SS)")
        else:
            abort(400, description="Deadline cannot be empty")

    if "gcode_id" in data:
        scheduled_print.gcode_id = data.get("gcode_id")

    if "assigned_printer_id" in data:
        scheduled_print.assigned_printer_id = data.get("assigned_printer_id")

    if "scheduled_start_time" in data:
        start_time_str = data.get("scheduled_start_time")
        if start_time_str:
            try:
                scheduled_print.scheduled_start_time = datetime.fromisoformat(start_time_str)
            except ValueError:
                abort(400, description="Invalid scheduled_start_time format; use ISO format (YYYY-MM-DDTHH:MM:SS)")
        else:
            scheduled_print.scheduled_start_time = None

    if "status" in data:
        scheduled_print.status = data.get("status")

    if "product_id" in data:
        scheduled_print.product_id = data.get("product_id")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))

    return jsonify(scheduled_print.to_dict()), 200

@scheduled_print_bp.route('/<int:scheduled_id>', methods=['DELETE'])
def delete_scheduled_print(scheduled_id):
    """
    Delete the scheduled print with the given ID.
    """
    scheduled_print = ScheduledPrint.query.get(scheduled_id)
    if scheduled_print is None:
        abort(404, description=f"Scheduled print with id {scheduled_id} not found")

    db.session.delete(scheduled_print)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))
    return jsonify({"message": f"Scheduled print {scheduled_id} deleted."}), 200
