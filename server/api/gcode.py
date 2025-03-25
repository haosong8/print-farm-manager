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

# Endpoint 1: Retrieve Gcode files from a printer, delete existing entries, and store new entries in the database
@gcode_bp.route('/<string:printer_ip>/get_gcode', methods=['POST'])
def fetch_gcode_files(printer_ip):
    # Find the printer by its IP address in the database.
    printer = Printer.query.filter_by(ip_address=printer_ip).first()
    if not printer:
        return jsonify({"error": f"No printer found with IP {printer_ip}"}), 404

    # Delete all existing gcodes for this printer.
    deleted = Gcode.query.filter_by(printer_id=printer.printer_id).delete()
    db.session.commit()  # Commit deletion.
    print(f"Deleted {deleted} existing gcodes for printer {printer_ip}.")

    # Construct the JSON-RPC URL using the printer's IP and port.
    url = f"http://{printer.ip_address}:{printer.port}/server/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": "server.files.list",
        "params": {"root": "gcodes"},
        "id": 4644
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Error connecting to printer: {str(e)}"}), 500

    data = response.json()
    if "result" not in data:
        return jsonify({"error": "Invalid response from printer"}), 500

    file_list = data["result"]
    new_files = []
    for file_info in file_list:
        file_path = file_info.get("path")
        if not file_path:
            continue
        # Create a new Gcode record for each file.
        new_gcode = Gcode(printer_id=printer.printer_id, gcode_name=file_path)
        db.session.add(new_gcode)
        new_files.append(new_gcode.to_dict())
    db.session.commit()

    return jsonify({"added": new_files, "total_files_found": len(file_list)}), 200

# Endpoint 2: Retrieve metadata for each gcode file for a specific printer and update the Gcode model
@gcode_bp.route('/<string:printer_ip>/metadata', methods=['POST'])
def update_printer_gcode_metadata(printer_ip):
    printer = Printer.query.filter_by(ip_address=printer_ip).first()
    if not printer:
        return jsonify({"error": f"No printer found with IP {printer_ip}"}), 404

    # Construct the JSON-RPC URL using the printer's IP and port.
    url = f"http://{printer.ip_address}:{printer.port}/server/jsonrpc"
    gcodes = Gcode.query.filter_by(printer_id=printer.printer_id).all()
    updated_records = []
    for gcode in gcodes:
        payload = {
            "jsonrpc": "2.0",
            "method": "server.files.metadata",
            "params": {"filename": gcode.gcode_name},
            "id": 3545
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json().get("result", {})
            if result:
                # Convert seconds into timedelta for the INTERVAL columns.
                if 'estimated_time' in result:
                    seconds = int(result['estimated_time'])
                    gcode.estimated_print_time = timedelta(seconds=seconds)
                if 'historical_print_time' in result:
                    seconds = int(result['historical_print_time'])
                    gcode.historical_print_time = timedelta(seconds=seconds)
                updated_records.append(gcode.to_dict())
        except Exception as e:
            continue

    db.session.commit()
    return jsonify({"updated": updated_records}), 200

# Endpoint 3: Update historical print time estimation based on job history from Moonraker
@gcode_bp.route('/<string:printer_ip>/update_history', methods=['POST'])
def update_historical_print_time(printer_ip):
    printer = Printer.query.filter_by(ip_address=printer_ip).first()
    if not printer:
        return jsonify({"error": f"No printer found with IP {printer_ip}"}), 404

    # Construct the JSON-RPC URL using the printer's IP and port.
    url = f"http://{printer.ip_address}:{printer.port}/server/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": "server.history.list",
        "params": {
            "limit": 50,
            "start": 10,
            "order": "asc"
        },
        "id": 5656
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"Error connecting to printer history: {str(e)}"}), 500

    history_data = response.json()
    if "result" not in history_data or "jobs" not in history_data["result"]:
        return jsonify({"error": "Invalid history response from printer"}), 500

    jobs = history_data["result"]["jobs"]

    # Get all gcodes for this printer.
    gcodes = Gcode.query.filter_by(printer_id=printer.printer_id).all()
    updated_records = []
    for gcode in gcodes:
        # Find completed jobs for this gcode (matching by filename).
        matching_jobs = [
            job for job in jobs
            if job.get("filename") == gcode.gcode_name and job.get("status") == "completed" and job.get("end_time") is not None
        ]
        if matching_jobs:
            # Choose the job with the latest end_time.
            latest_job = max(matching_jobs, key=lambda j: j.get("end_time", 0))
            total_duration = latest_job.get("total_duration")
            if total_duration is not None:
                # Convert the total_duration (in seconds) into a timedelta.
                gcode.historical_print_time = timedelta(seconds=int(total_duration))
                updated_records.append(gcode.to_dict())

    db.session.commit()
    return jsonify({"updated": updated_records}), 200
