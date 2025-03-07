import socketio

# Create a Socket.IO client instance.
sio = socketio.Client()

@sio.event
def connect():
    print("Connected to Socket.IO server!")

@sio.event
def connect_error(data):
    print("Connection failed with data:", data)

@sio.event
def disconnect():
    print("Disconnected from Socket.IO server.")

@sio.on("printer_update")
def on_printer_update(data):
    print("Received printer update:", data)

# Connect to the server.
# We include a query parameter "printerIp" so the server can add us to the correct room.
sio.connect("http://localhost:5000?printerIp=192.168.4.53", transports=["websocket"])

# Wait for events.
sio.wait()