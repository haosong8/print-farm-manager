from . import printers
from . import gcode

def register_blueprints(app):
    app.register_blueprint(printers.printer_bp)
    app.register_blueprint(gcode.gcode_bp)