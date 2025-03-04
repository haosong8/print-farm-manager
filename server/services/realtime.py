import threading
import queue
import websocket
import json
import time

# Global dictionary to hold active websocket clients.
# Keyed by printer IP address; each entry holds a dict with:
#   - 'thread': the thread running the websocket client
#   - 'ws_app': the current websocket application instance
#   - 'subscribers': a list of queue.Queue instances, one per subscriber.
#   - 'initial_received': a flag to indicate if the initial response has been received.
active_ws_clients = {}

def ws_on_message_factory(printer_ip, allowed_methods=None):
    def on_message(ws, message):
        print(f"[WS][{printer_ip}] Received message: {message}")
        try:
            data = json.loads(message)
        except Exception as e:
            print(f"[WS][{printer_ip}] Error parsing message: {e}")
            return

        # Check for the initial response (id == 1) and mark it.
        if data.get("id") == 1:
            client = active_ws_clients.get(printer_ip)
            if client is not None:
                client["initial_received"] = True
                print(f"[WS][{printer_ip}] Initial response received.")
        if allowed_methods is not None:
            method = data.get("method")
            if method is not None and method not in allowed_methods:
                print(f"[WS][{printer_ip}] Filtering out method: {method}")
                return
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
            # Optionally, clear the active connection:
            # active_ws_clients.pop(printer_ip, None)
    return on_close

def ws_on_open(ws, printer_ip):
    print(f"[WS][{printer_ip}] Connection opened. Sending initial JSON-RPC request for printer objects.")
    initial_payload = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None,
            }
        },
        "id": 1,
    }
    ws.send(json.dumps(initial_payload))
    print(f"[WS][{printer_ip}] Initial request sent: {json.dumps(initial_payload)}")
    # Delay polling until the initial response is received.
    threading.Thread(target=wait_and_start_polling, args=(ws, printer_ip, 0.5), daemon=True).start()

def wait_and_start_polling(ws, printer_ip, poll_interval, max_wait=30):
    """
    Wait until the initial response (id==1) is received or until max_wait seconds have passed.
    Then start periodic polling over the websocket.
    """
    start_time = time.time()
    client = active_ws_clients.get(printer_ip)
    while client is not None and not client.get("initial_received", False):
        if time.time() - start_time > max_wait:
            print(f"[WS][{printer_ip}] Timeout waiting for initial response. Starting polling anyway.")
            break
        time.sleep(0.1)
    periodic_polling(ws, printer_ip, poll_interval=poll_interval)

def periodic_polling(ws, printer_ip, poll_interval=1):
    """
    Send a polling JSON-RPC request over the websocket every poll_interval seconds.
    For diagnosis, poll_interval is set to 0.1 seconds.
    """
    counter = 2  # Starting id for subsequent requests.
    payload_template = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None,
            }
        }
    }
    while True:
        try:
            time.sleep(poll_interval)
            payload = payload_template.copy()
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
        active_ws_clients[printer_ip] = {"subscribers": [], "initial_received": False}
    active_ws_clients[printer_ip]["ws_app"] = ws_app
    ws_app.run_forever()

def get_ws_subscription(printer):
    """
    Returns a new subscription queue for a given printer.
    If a websocket client for this printer is already active, adds a new subscriber.
    Otherwise, creates a new websocket connection.
    """
    printer_ip = printer.ip_address
    if printer_ip not in active_ws_clients:
        print(f"[WS][{printer_ip}] No active connection found. Creating new websocket client.")
        active_ws_clients[printer_ip] = {"subscribers": [], "initial_received": False}
        ws_thread = threading.Thread(target=run_websocket_client, args=(printer,))
        ws_thread.daemon = True
        ws_thread.start()
        active_ws_clients[printer_ip]["thread"] = ws_thread
    else:
        print(f"[WS][{printer_ip}] Active connection already exists. Reusing connection.")
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
