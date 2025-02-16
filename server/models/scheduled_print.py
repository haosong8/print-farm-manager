from . import db

class ScheduledPrint(db.Model):
    __tablename__ = 'scheduled_prints'
    scheduled_id = db.Column(db.Integer, primary_key=True)
    deadline = db.Column(db.DateTime, nullable=False)
    gcode_id = db.Column(db.Integer, db.ForeignKey('gcodes.gcode_id'), nullable=False)
    assigned_printer_id = db.Column(db.Integer, db.ForeignKey('printers.printer_id'))
    scheduled_start_time = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='pending')

    def to_dict(self):
        return {
            "scheduled_id": self.scheduled_id,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "gcode_id": self.gcode_id,
            "assigned_printer_id": self.assigned_printer_id,
            "scheduled_start_time": self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            "status": self.status,
        }
