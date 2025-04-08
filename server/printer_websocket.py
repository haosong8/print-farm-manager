import websocket
import json
import threading

def on_message(ws, message):
    try:
        parsed = json.loads(message)
        print("Received JSON response:", json.dumps(parsed, indent=2))
    except Exception as e:
        print("Received (raw):", message)
        print("Error parsing JSON:", e)

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed with code:", close_status_code, "message:", close_msg)

def on_open(ws):
    print("WebSocket connection opened.")
    # Example JSON-RPC request: server.info
    payload = {
        "jsonrpc": "2.0",
        "method": "printer.objects.list",
        "id": 1454
    }
    ws.send(json.dumps(payload))
    # Use a timer to close the connection after 3 seconds via safe_close.
    threading.Timer(3, lambda: safe_close(ws)).start()

def safe_close(ws):
    try:
        if ws.sock is not None:
            ws.close()
    except Exception as e:
        print("Error during safe_close:", e)

if __name__ == "__main__":
    ws_url = "ws://192.168.4.7:7125/websocket"
    print("Connecting to:", ws_url)
    
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()
