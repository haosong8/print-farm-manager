from . import printers

def register_blueprints(app):
    app.register_blueprint(printers.printer_bp)