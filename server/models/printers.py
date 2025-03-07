from sqlalchemy import Column, Integer, String, Time
from models import db

class Printer(db.Model):
    __tablename__ = 'printers'

    printer_id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True, nullable=False)
    port = Column(Integer, nullable=False)
    printer_name = Column(String, nullable=False)
    printer_model = Column(String, nullable=False)
    available_start_time = Column(Time)
    available_end_time = Column(Time)
    # New status field to store connection and printing status.
    status = Column(String, default="disconnected")  # possible values: "offline", "idle", "printing", "completed"

    def to_dict(self):
        return {
            "printer_id": self.printer_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "printer_name": self.printer_name,
            "printer_model": self.printer_model,
            "available_start_time": self.available_start_time.strftime("%H:%M:%S") if self.available_start_time else None,
            "available_end_time": self.available_end_time.strftime("%H:%M:%S") if self.available_end_time else None,
            "status": self.status,
        }
