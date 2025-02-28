from apscheduler.schedulers.background import BackgroundScheduler
import time
import requests
import random

def fetch_printer_dynamic_data(printer):
    """
    Sends a JSON-RPC request to the printer's Moonraker API to query dynamic printer objects.
    
    Expected response format (example):
    {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": null,
                "extruder": null,
                "toolhead": null
            }
        },
        "id": 4654
    }
    
    Returns:
        dict: The JSON response from the printer's API, or None if an error occurs.
    """
    # Construct the URL using the printer's IP and port.
    url = f"http://{printer.ip_address}:{printer.port}/server/jsonrpc"
    
    # Build the JSON-RPC payload.
    payload = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None
            }
        },
        "id": random.randint(1000, 9999)
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()  # Raise exception for HTTP errors.
        return response.json()
    except Exception as e:
        print(f"Error fetching dynamic data for printer {printer.printer_id}: {e}")
        return None

def check_printer_connection(printer):
    """
    Checks connectivity to the printer's Moonraker API by sending a JSON-RPC request
    to the "printer.info" method. Returns True if the printer responds with valid data,
    otherwise returns False.
    
    Args:
        printer: A printer object that has attributes 'ip_address', 'port', and 'printer_id'
    
    Returns:
        bool: True if the connection is successful, False otherwise.
    """
    url = f"http://{printer.ip_address}:{printer.port}/server/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": "printer.info",
        "id": 5445
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        # Check if the response contains a "result" key (adjust based on Moonraker's spec)
        if "result" in data:
            return True
        else:
            print(f"Printer {printer.printer_id} responded but no 'result' key found.")
            return False
    except Exception as e:
        print(f"Error checking printer connection for printer {printer.printer_id}: {e}")
        return False

def start_printer_scheduler(printer, socketio, interval=10, scheduler=None):
    """
    Starts a polling job for the specified printer.
    The job polls dynamic data from the printer's Moonraker API and emits an update via SocketIO.
    """
    if scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.start()
    
    job_id = f"printer_{printer.printer_id}_poll"
    
    def poll_printer():
        try:
            data = fetch_printer_dynamic_data(printer)
            socketio.emit("printer_update", data)
            print(f"{data} polled printer {printer.printer_id} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"Error polling printer {printer.printer_id}: {e}")
    
    scheduler.add_job(func=poll_printer, trigger="interval", seconds=interval, id=job_id, replace_existing=True)
    return scheduler
