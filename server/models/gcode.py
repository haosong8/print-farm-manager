from sqlalchemy import Column, Integer, String, Time, Float
from models import db

class Gcode(db.Model):
    __tablename__ = 'gcodes'

    gcode_id = db.Column(db.Integer, primary_key=True)
    printer_id = db.Column(db.Integer, db.ForeignKey('printers.printer_id'), nullable=False)
    gcode_name = db.Column(db.String(255), nullable=False)
    estimated_print_time = db.Column(db.Interval)
    historical_print_time = db.Column(db.Interval)
    filament_total = db.Column(db.Float)
    material = db.Column(db.String(100), nullable=False)  # new field

    # Remove the following line because the many-to-many relationship is defined in ProductComponent.
    # product_components = db.relationship('ProductComponent', back_populates='gcode', lazy='dynamic')

    def to_dict(self):
        return {
            "gcode_id": self.gcode_id,
            "printer_id": self.printer_id,
            "gcode_name": self.gcode_name,
            "estimated_print_time": str(self.estimated_print_time) if self.estimated_print_time else None,
            "historical_print_time": str(self.historical_print_time) if self.historical_print_time else None,
            "material": self.material
        }
