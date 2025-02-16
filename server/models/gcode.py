from . import db

class Gcode(db.Model):
    __tablename__ = 'gcodes'
    gcode_id = db.Column(db.Integer, primary_key=True)
    printer_id = db.Column(db.Integer, db.ForeignKey('printers.printer_id'), nullable=False)
    gcode_name = db.Column(db.String(255), nullable=False)
    estimated_print_time = db.Column(db.Interval)
    historical_print_time = db.Column(db.Interval)

    def to_dict(self):
        return {
            "gcode_id": self.gcode_id,
            "printer_id": self.printer_id,
            "gcode_name": self.gcode_name,
            "estimated_print_time": str(self.estimated_print_time) if self.estimated_print_time else None,
            "historical_print_time": str(self.historical_print_time) if self.historical_print_time else None,
        }
