import threading
import queue
import websocket
import json
import time
import random
from models import db
from models.printers import Printer
from extensions import socketio  # your shared Socket.IO instance

# Global variable to store the Flask app instance.
APP_INSTANCE = None

# Global dictionary to hold active websocket clients.
# Keyed by printer IP address; each entry holds a dict with:
#   - 'thread': the thread running the websocket client
#   - 'ws_app': the current websocket application instance
#   - 'subscribers': a list of queue.Queue instances (if needed).
active_ws_clients = {}

# Payload template for polling printer objects.
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

def start_realtime_scheduler(app, socketio, interval=10):
    """
    Call this function from your server startup to store the app instance.
    You can also schedule other periodic tasks here if needed.
    """
    global APP_INSTANCE
    APP_INSTANCE = app
    print("[Realtime] Realtime scheduler started with polling interval:", interval)
    # If you have additional scheduling logic, add it here.

def update_printer_status(printer_ip, new_status):
    """
    Update the printer's status in the database using the stored app instance.
    """
    global APP_INSTANCE
    if APP_INSTANCE is None:
        print("[DB] No app instance available.")
        return
    try:
        with APP_INSTANCE.app_context():
            printer = Printer.query.filter_by(ip_address=printer_ip).first()
            if printer and printer.status != new_status:
                printer.status = new_status
                db.session.commit()
                print(f"[DB] Updated printer {printer_ip} status to {new_status}")
    except Exception as e:
        print(f"[DB] Error updating printer status for {printer_ip}: {e}")

def ws_on_message_factory(printer_ip, allowed_methods=None):
    def on_message(ws, message):
        try:
            data = json.loads(message)
        except Exception as e:
            print(f"[WS][{printer_ip}] Error parsing message: {e}")
            return

        if allowed_methods is not None:
            method = data.get("method")
            if method is not None and method not in allowed_methods:
                print(f"[WS][{printer_ip}] Filtering out method: {method}")
                return

        # Check for printer status info.
        if "result" in data and "status" in data["result"]:
            status_obj = data["result"]["status"]
            if "print_stats" in status_obj and status_obj["print_stats"].get("state"):
                new_state = status_obj["print_stats"]["state"]
                print(f"[WS][{printer_ip}] Detected print state: {new_state}")
                threading.Thread(
                    target=update_printer_status,
                    args=(printer_ip, new_state),
                    daemon=True
                ).start()

        # Emit update via Socket.IO to clients in the printer's room.
        try:
            socketio.emit("printer_update", data, room=printer_ip)
        except Exception as e:
            print(f"[WS][{printer_ip}] Error emitting Socket.IO event: {e}")

        # Optionally pass the raw message to SSE subscribers.
        client = active_ws_clients.get(printer_ip)
        if client:
            for sub_q in client.get("subscribers", []):
                sub_q.put(message)
    return on_message

def ws_on_error_factory(printer_ip):
    def on_error(ws, error):
        print(f"[WS][{printer_ip}] Error: {error}")
        client = active_ws_clients.get(printer_ip)
        if client:
            err_msg = json.dumps({"error": str(error)})
            for sub_q in client.get("subscribers", []):
                sub_q.put(err_msg)
    return on_error

def ws_on_close_factory(printer_ip):
    def on_close(ws, close_status_code, close_msg):
        print(f"[WS][{printer_ip}] Connection closed: code={close_status_code}, msg={close_msg}")
        client = active_ws_clients.get(printer_ip)
        if client:
            info_msg = json.dumps({"info": "connection closed"})
            for sub_q in client.get("subscribers", []):
                sub_q.put(info_msg)
    return on_close

def ws_on_open(ws, printer_ip):
    print(f"[WS][{printer_ip}] Connection opened. Sending initial polling query for printer objects.")
    payload = PAYLOAD_TEMPLATE.copy()
    payload["id"] = 1
    ws.send(json.dumps(payload))
    print(f"[WS][{printer_ip}] Initial query sent: {json.dumps(payload)}")
    threading.Thread(target=periodic_polling, args=(ws, printer_ip, 1), daemon=True).start()

def periodic_polling(ws, printer_ip, poll_interval=1):
    """
    Send a polling JSON-RPC request over the websocket every poll_interval seconds.
    """
    counter = 2  # Starting id for subsequent requests.
    while True:
        try:
            time.sleep(poll_interval)
            payload = PAYLOAD_TEMPLATE.copy()
            payload["id"] = counter
            counter += 1
            print(f"[WS][{printer_ip}] Sending polling payload: {json.dumps(payload)}")
            ws.send(json.dumps(payload))
        except Exception as e:
            print(f"[WS][{printer_ip}] Polling error: {e}")
            break

def run_websocket_client(printer):
    printer_ip = printer.ip_address
    ws_url = f"ws://{printer.ip_address}:{printer.port}/websocket"
    print(f"[WS][{printer_ip}] Attempting to connect to {ws_url}")
    ws_app = websocket.WebSocketApp(
        ws_url,
        on_message=ws_on_message_factory(printer_ip, allowed_methods=["printer.objects.query"]),
        on_error=ws_on_error_factory(printer_ip),
        on_close=ws_on_close_factory(printer_ip),
        on_open=lambda ws: ws_on_open(ws, printer_ip),
    )
    if printer_ip not in active_ws_clients:
        active_ws_clients[printer_ip] = {"subscribers": []}
    active_ws_clients[printer_ip]["ws_app"] = ws_app
    ws_app.run_forever()

def get_ws_subscription(printer):
    """
    Returns a subscription queue for a given printer.
    If a websocket client for this printer is already active and already has a subscription queue,
    then return the existing queue; otherwise, create a new websocket connection and subscription.
    """
    printer_ip = printer.ip_address
    if printer_ip not in active_ws_clients:
        print(f"[WS][{printer_ip}] No active connection found. Creating new websocket client.")
        active_ws_clients[printer_ip] = {"subscribers": []}
        ws_thread = threading.Thread(target=run_websocket_client, args=(printer,))
        ws_thread.daemon = True
        ws_thread.start()
        active_ws_clients[printer_ip]["thread"] = ws_thread
    else:
        print(f"[WS][{printer_ip}] Active connection already exists. Reusing connection.")
    if active_ws_clients[printer_ip]["subscribers"]:
        print(f"[WS][{printer_ip}] Reusing existing subscription. Total subscribers: {len(active_ws_clients[printer_ip]['subscribers'])}")
        return active_ws_clients[printer_ip]["subscribers"][0]
    else:
        sub_q = queue.Queue()
        active_ws_clients[printer_ip]["subscribers"].append(sub_q)
        print(f"[WS][{printer_ip}] New subscription added. Total subscribers: {len(active_ws_clients[printer_ip]['subscribers'])}")
        return sub_q

def remove_ws_subscription(printer, sub_q):
    """
    Removes a subscription queue from the printer's active subscribers.
    """
    printer_ip = printer.ip_address
    if printer_ip in active_ws_clients:
        if sub_q in active_ws_clients[printer_ip]["subscribers"]:
            active_ws_clients[printer_ip]["subscribers"].remove(sub_q)
            print(f"[WS][{printer_ip}] Subscription removed. Total subscribers: {len(active_ws_clients[printer_ip]['subscribers'])}")

def check_printer_connection(printer):
    """
    Checks if there is an existing active websocket connection for the printer.
    Returns True if the connection exists and is alive; otherwise, returns False.
    """
    printer_ip = printer.ip_address
    if printer_ip in active_ws_clients:
        ws_info = active_ws_clients[printer_ip]
        thread = ws_info.get("thread")
        if thread and thread.is_alive():
            print(f"[WS][{printer_ip}] Active websocket connection found.")
            return True
    print(f"[WS][{printer_ip}] No active websocket connection found.")
    return False

def disconnect_printer(printer):
    """
    Closes the active websocket connection for a given printer (if exists)
    and removes its entry from active_ws_clients.
    """
    printer_ip = printer.ip_address
    if printer_ip in active_ws_clients:
        ws_info = active_ws_clients[printer_ip]
        ws_app = ws_info.get("ws_app")
        if ws_app:
            print(f"[WS][{printer_ip}] Disconnecting websocket.")
            ws_app.close()
        else:
            print(f"[WS][{printer_ip}] No ws_app instance found for disconnect.")
        active_ws_clients.pop(printer_ip, None)
    else:
        print(f"[WS][{printer_ip}] No active connection to disconnect.")

__all__ = [
    "get_ws_subscription",
    "remove_ws_subscription",
    "check_printer_connection",
    "disconnect_printer",
]
