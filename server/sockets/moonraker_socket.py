import threading
import time
import json
import random
import websocket
from flask import current_app
from models import db
from models.printers import Printer
from extensions import socketio
from sockets.utils import get_app_instance  # import the getter

class MoonrakerSocket:
    PAYLOAD_TEMPLATE = {
        "jsonrpc": "2.0",
        "method": "printer.objects.query",
        "params": {
            "objects": {
                "heater_bed": None,
                "extruder": None,
                "toolhead": None,
                "print_stats": None,
                "display_status": None,
            }
        }
    }
    
    def __init__(self, printer, poll_interval=1):
        """
        Initialize the MoonrakerSocket for a given printer.
        """
        self.printer = printer
        self.printer_ip = printer.ip_address
        self.poll_interval = poll_interval
        self.ws = None
        self.thread = None
        self.connected = False

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception as e:
            print(f"[WS][{self.printer_ip}] Error parsing message: {e}")
            return

        # Filter messages if needed; only process messages with method "printer.objects.query".
        method = data.get("method")
        if method and method != "printer.objects.query":
            print(f"[WS][{self.printer_ip}] Filtering out method: {method}")
            return

        # Check if the response contains printer status info.
        if "result" in data and "status" in data["result"]:
            status_obj = data["result"]["status"]
            if "print_stats" in status_obj and status_obj["print_stats"].get("state"):
                new_state = status_obj["print_stats"]["state"]
                print(f"[WS][{self.printer_ip}] Detected print state: {new_state}")
                # Update printer status in DB using the global app instance.
                threading.Thread(
                    target=self.update_printer_status,
                    args=(new_state,),
                    daemon=True
                ).start()
            if "display_status" in status_obj:
                display_status = status_obj["display_status"]
                print(f"[WS][{self.printer_ip}] Display status: {display_status}")
                    
        # Emit update via Socket.IO to clients in the room for this printer.
        try:
            socketio.emit("printer_update", data, room=self.printer_ip)
        except Exception as e:
            print(f"[WS][{self.printer_ip}] Error emitting Socket.IO event: {e}")

    def on_error(self, ws, error):
        print(f"[WS][{self.printer_ip}] Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"[WS][{self.printer_ip}] Connection closed: code={close_status_code}, msg={close_msg}")
        self.connected = False

    def on_open(self, ws):
        print(f"[WS][{self.printer_ip}] Connection opened. Sending initial polling query.")
        payload = self.PAYLOAD_TEMPLATE.copy()
        payload["id"] = 1
        ws.send(json.dumps(payload))
        threading.Thread(target=self.periodic_polling, daemon=True).start()

    def periodic_polling(self):
        counter = 2  # Starting id for subsequent requests.
        while self.connected:
            try:
                time.sleep(self.poll_interval)
                payload = self.PAYLOAD_TEMPLATE.copy()
                payload["id"] = counter
                counter += 1
                print(f"[WS][{self.printer_ip}] Sending polling payload: {json.dumps(payload)}")
                self.ws.send(json.dumps(payload))
            except Exception as e:
                print(f"[WS][{self.printer_ip}] Polling error: {e}")
                break

    def update_printer_status(self, new_status):
        try:
            app = get_app_instance()
            if not app:
                print(f"[DB] No app instance available for {self.printer_ip}.")
                return
            with app.app_context():
                printer = Printer.query.filter_by(ip_address=self.printer_ip).first()
                if printer and printer.status != new_status:
                    printer.status = new_status
                    db.session.commit()
                    print(f"[DB] Updated printer {self.printer_ip} status to {new_status}")
        except Exception as e:
            print(f"[DB] Error updating printer status for {self.printer_ip}: {e}")

    def connect(self):
        ws_url = f"ws://{self.printer_ip}:{self.printer.port}/websocket"
        print(f"[WS][{self.printer_ip}] Attempting to connect to {ws_url}")
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.connected = True
        self.ws.run_forever()

    def start(self):
        self.thread = threading.Thread(target=self.connect, daemon=True)
        self.thread.start()

    def disconnect(self):
        if self.ws:
            print(f"[WS][{self.printer_ip}] Disconnecting websocket.")
            self.ws.close()
            self.connected = False
        else:
            print(f"[WS][{self.printer_ip}] No active websocket to disconnect.")
