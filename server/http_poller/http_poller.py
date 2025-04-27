import threading
import time
import json
import requests
from models import db
from models.printers import Printer
from sockets.utils import get_app_instance  # Helper to get your Flask app
from extensions import socketio              # Your Socket.IO instance

class HTTPPoller:
    """
    This class polls a printer's HTTP endpoint at a regular interval.
    It uses either GET or POST (with a JSON payload) as configured.
    The received data is passed to a callback, which you can use to emit
    events via Socket.IO or update your database.
    """

    # Base payload template (without chamber temp)
    BASE_PAYLOAD = {
        "objects": {
            "gcode_move": None,
            "toolhead": None,
            "heater_bed": None,
            "extruder": None,
            "print_stats": None,
            "display_status": None,
            "virtual_sdcard": None
        }
    }

    def __init__(self, printer: Printer, poll_interval=1, request_method="GET", callback=None):
        """
        :param printer: A Printer model instance.
        :param poll_interval: Poll interval in seconds.
        :param request_method: "GET" or "POST" (default: GET).
        :param callback: A function with signature callback(printer_ip, data).
                         If provided, it is called on every successful poll.
        """
        self.printer = printer
        self.poll_interval = poll_interval
        self.request_method = request_method.upper()
        self.callback = callback
        self.thread = None
        self.running = False
        # Track consecutive polling errors
        self.error_count = 0

    def build_url(self) -> str:
        """
        Build the URL for querying printer objects using the Moonraker REST API.
        """
        return f"http://{self.printer.ip_address}:{self.printer.port}/printer/objects/query"

    def poll_once(self):
        """
        Execute one polling request and process the result.
        Dynamically injects chamber temp if the printer has a heated chamber.
        """
        url = self.build_url()

        # Make a fresh copy of the base payload
        payload = {"objects": dict(self.BASE_PAYLOAD["objects"])}

        # If this printer has a heated chamber, request its temperature
        if getattr(self.printer, "heated_chamber", False):
            payload["objects"]["temperature_sensor chamber_temp"] = None

        try:
            if self.request_method == "GET":
                # Build query string from the object keys
                query_string = "&".join(payload["objects"].keys())
                full_url = f"{url}?{query_string}"
                response = requests.get(full_url, timeout=2)

            elif self.request_method == "POST":
                headers = {"Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers, timeout=2)

            else:
                print(f"[HTTPPoller][{self.printer.ip_address}] Unsupported request method: {self.request_method}")
                return

            response.raise_for_status()  # Raises on 4xx/5xx
            data = response.json()

            # On successful poll, reset error counter
            if self.error_count >= 10:
                # Optionally, mark printer as online again after recovery
                app = get_app_instance()
                with app.app_context():
                    Printer.query.filter_by(id=self.printer.id).update({"is_online": True})
                    db.session.commit()
                print(f"[HTTPPoller][{self.printer.ip_address}] Printer recovered and set online.")
            self.error_count = 0

            if self.callback:
                self.callback(self.printer.ip_address, data)

        except Exception as e:
            print(f"[HTTPPoller][{self.printer.ip_address}] Polling error: {e}")
            self.error_count += 1

            # After 10 consecutive polling errors, mark printer as offline
            if self.error_count >= 10:
                app = get_app_instance()
                with app.app_context():
                    Printer.query.filter_by(id=self.printer.id).update({"is_online": False})
                    db.session.commit()
                print(f"[HTTPPoller][{self.printer.ip_address}] Set printer offline after {self.error_count} consecutive errors.")
                self.stop()
                
    def poll_loop(self):
        """Continuously poll until stopped."""
        while self.running:
            self.poll_once()
            time.sleep(self.poll_interval)

    def start(self):
        """Start polling in a new daemon thread."""
        self.running = True
        self.thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.thread.start()
        print(f"[HTTPPoller][{self.printer.ip_address}] Started polling every {self.poll_interval} second(s).")

    def stop(self):
        """Stop the poller."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print(f"[HTTPPoller][{self.printer.ip_address}] Polling stopped.")


def update_printer_status_callback(printer_ip, data):
    """
    Called by HTTPPoller on every successful poll.
    Emits the data to all Socket.IO clients in the printer's room.
    """
    try:
        socketio.emit("printer_update", data, room=printer_ip)
    except Exception as e:
        print(f"[HTTPPoller][{printer_ip}] Error emitting update: {e}")


# For standalone testing
if __name__ == "__main__":
    from models.printers import Printer as TestPrinter
    test_printer = TestPrinter.query.filter_by(ip_address="192.168.1.100").first()
    if test_printer:
        poller = HTTPPoller(
            test_printer,
            poll_interval=1,
            request_method="POST",
            callback=update_printer_status_callback
        )
        poller.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            poller.stop()
