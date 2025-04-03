from sqlalchemy import Column, Integer, String, Time, Float
from models import db

class Printer(db.Model):
    __tablename__ = 'printers'

    printer_id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True, nullable=False)
    port = Column(Integer, nullable=False)
    webcam_address = Column(String, nullable=False)
    webcam_port = Column(Integer, nullable=False)
    printer_name = Column(String, nullable=False)
    printer_model = Column(String, nullable=False)
    available_start_time = Column(Time)
    available_end_time = Column(Time)
    status = Column(String, default="disconnected")
    prepare_time = Column(Integer)
    supported_materials = Column(String, nullable=False)  # comma-separated list of materials

    # New fields for live stream scaling configuration:
    camera_resolution_width = Column(Integer, nullable=True)   # e.g., 1920
    camera_resolution_height = Column(Integer, nullable=True)  # e.g., 1080
    camera_scaling_factor = Column(Float, nullable=True)         # e.g., 0.75

    # Instead of product_components, each Printer has gcodes:
    gcodes = db.relationship('Gcode', backref='printer', lazy='dynamic')

    def to_dict(self):
        return {
            "printer_id": self.printer_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "webcam_address": self.webcam_address,
            "webcam_port": self.webcam_port,
            "printer_name": self.printer_name,
            "printer_model": self.printer_model,
            "available_start_time": self.available_start_time.strftime("%H:%M:%S") if self.available_start_time else None,
            "available_end_time": self.available_end_time.strftime("%H:%M:%S") if self.available_end_time else None,
            "status": self.status,
            "prepare_time": self.prepare_time,
            "supported_materials": self.supported_materials.split(',') if self.supported_materials else [],
            "camera_resolution_width": self.camera_resolution_width,
            "camera_resolution_height": self.camera_resolution_height,
            "camera_scaling_factor": self.camera_scaling_factor,
        }
