from flask import Blueprint, request, jsonify, abort
from models.printers import Printer
from models.gcode import Gcode
from models import db
from datetime import datetime, timedelta
import json
import random
import requests

gcode_bp = Blueprint('gcode', __name__, url_prefix='/gcode')

# Existing endpoint: Get all gcodes
@gcode_bp.route('/', methods=['GET'])
def get_gcode():
    gcodes = Gcode.query.all()
    gcode_list = [g.to_dict() for g in gcodes]
    return jsonify(gcode_list), 200

# Existing endpoint: Get printer info (and associated Gcode records) by IP address
@gcode_bp.route('/printer/<string:ip_address>', methods=['GET'])
def get_printer_by_ip(ip_address):
    printer = Printer.query.filter_by(ip_address=ip_address).first()
    if not printer:
        return jsonify({"error": f"No printer found with IP {ip_address}"}), 404

    gcodes = Gcode.query.filter_by(printer_id=printer.printer_id).all()
    printer_data = printer.to_dict()
    printer_data['gcodes'] = [g.to_dict() for g in gcodes]
    return jsonify(printer_data), 200

@gcode_bp.route('/<string:printer_ip>/get_gcode', methods=['POST'])
def combined_bulk_fetch_and_history(printer_ip):
    """
    Combined bulk endpoint:
    - Deletes existing Gcode records for the printer.
    - Uses HTTP GET requests to fetch the list of Gcode files from the printer.
    - Uses HTTP GET requests to fetch printer job history.
    - For each file, retrieves metadata via HTTP GET (e.g., estimated_time, filament_total, filament_type)
      and looks up the historical print time from the job history (if any).
    - Creates complete Gcode objects and bulk-inserts them into the database.
    - Returns a combined JSON response with both added and updated records.
    """
    # 1. Look up the printer by its IP.
    printer = Printer.query.filter_by(ip_address=printer_ip).first()
    if not printer:
        return jsonify({"error": f"No printer found with IP {printer_ip}"}), 404

    # 2. Delete existing gcodes for this printer.
    deleted = Gcode.query.filter_by(printer_id=printer.printer_id).delete()
    db.session.commit()
    print(f"Deleted {deleted} existing gcodes for printer {printer_ip}.")

    # 3. Build the base URL for HTTP endpoints.
    base_url = f"http://{printer.ip_address}:{printer.port}/server"

    # 4. Fetch the list of Gcode files via HTTP GET.
    try:
        response_list = requests.get(f"{base_url}/files/list", params={"root": "gcodes"}, timeout=5)
        response_list.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Error connecting to printer for file list: {str(e)}"}), 500

    data = response_list.json()
    if "result" not in data:
        return jsonify({"error": "Invalid response from printer for file list"}), 500

    file_list = data["result"]

    # 5. Fetch printer job history via HTTP GET.
    try:
        response_history = requests.get(f"{base_url}/history/list", params={"limit": 50, "start": 10, "order": "asc"}, timeout=10)
        response_history.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Error connecting to printer history: {str(e)}"}), 500

    history_data = response_history.json()
    if "result" not in history_data or "jobs" not in history_data["result"]:
        return jsonify({"error": "Invalid history response from printer"}), 500

    jobs = history_data["result"]["jobs"]

    # 6. Process each file: for each file in the file list, fetch metadata via HTTP GET and then match with job history.
    new_gcodes = []
    for file_info in file_list:
        file_path = file_info.get("path")
        if not file_path:
            continue

        try:
            response_metadata = requests.get(f"{base_url}/files/metadata", params={"filename": file_path}, timeout=5)
            response_metadata.raise_for_status()
            result = response_metadata.json().get("result", {})
        except Exception as e:
            print(f"Error fetching metadata for {file_path}: {e}")
            result = {}

        # Process metadata.
        est_print_time = (
            timedelta(seconds=int(result['estimated_time']))
            if 'estimated_time' in result and result['estimated_time'] != ""
            else None
        )
        filament_total = (
            float(result['filament_total'])
            if 'filament_total' in result and result['filament_total'] != ""
            else None
        )
        material = result['filament_type'] if 'filament_type' in result else "unknown"

        # Look up matching completed jobs for this gcode (by filename) to determine historical_print_time.
        historical_print_time = None
        matching_jobs = [
            job for job in jobs
            if job.get("filename") == file_path
            and job.get("status") == "completed"
            and job.get("end_time") is not None
        ]
        if matching_jobs:
            latest_job = max(matching_jobs, key=lambda j: j.get("end_time", 0))
            total_duration = latest_job.get("total_duration")
            if total_duration is not None and total_duration != "":
                historical_print_time = timedelta(seconds=int(total_duration))

        # Create a new Gcode record.
        new_gcode = Gcode(
            printer_id=printer.printer_id,
            gcode_name=file_path,
            estimated_print_time=est_print_time,
            historical_print_time=historical_print_time,
            filament_total=filament_total,
            material=material,
        )
        new_gcodes.append(new_gcode)

    # 7. Bulk insert new Gcode records.
    try:
        db.session.bulk_save_objects(new_gcodes)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error inserting new gcodes into database: {str(e)}"}), 500

    inserted = [g.to_dict() for g in new_gcodes]
    return jsonify({
        "added": inserted,
        "total_files_found": len(file_list)
    }), 200
