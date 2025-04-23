from . import printers
from . import gcode
from . import product
from . import scheduled_print

def register_blueprints(app):
    app.register_blueprint(printers.printer_bp)
    app.register_blueprint(gcode.gcode_bp)
    app.register_blueprint(product.product_bp)
    app.register_blueprint(scheduled_print.scheduled_print_bp)