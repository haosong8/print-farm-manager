# sockets/utils.py

_APP_INSTANCE = None

def set_app_instance(app):
    global _APP_INSTANCE
    _APP_INSTANCE = app
    print("[Utils] App instance has been set.")

def get_app_instance():
    return _APP_INSTANCE