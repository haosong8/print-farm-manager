from . import db

class Printer(db.Model):
    __tablename__ = 'printers'
    printer_id = db.Column(db.Integer, primary_key=True)
    printer_name = db.Column(db.String(100), nullable=False)
    printer_model = db.Column(db.String(50))
    ip_address = db.Column(db.String(50), nullable=False, unique=True)  # Unique constraint here
    port = db.Column(db.Integer, default=80)
    available_start_time = db.Column(db.Time)
    available_end_time = db.Column(db.Time)
    
    def to_dict(self):
        return {
            "printer_id": self.printer_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "printer_name": self.printer_name,
            "printer_model": self.printer_model,
            "available_start_time": self.available_start_time.strftime("%H:%M:%S") if self.available_start_time else None,
            "available_end_time": self.available_end_time.strftime("%H:%M:%S") if self.available_end_time else None,
        }
