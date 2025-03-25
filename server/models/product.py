from sqlalchemy import Column, Integer, String, Text, ForeignKey
from models import db
from models.gcode import Gcode
from models.printers import Printer

class Product(db.Model):
    __tablename__ = 'products'
    
    product_id = Column(Integer, primary_key=True)
    product_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationship to the association object representing the bill of materials.
    components = db.relationship('ProductComponent', back_populates='product', cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "description": self.description,
            "components": [component.to_dict() for component in self.components]
        }

class ProductComponent(db.Model):
    __tablename__ = 'product_components'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id'), nullable=False)
    gcode_id = Column(Integer, ForeignKey('gcodes.gcode_id'), nullable=False)
    # Although the Gcode model stores the file name/path, we store it here to capture the exact file path
    # used when this component was added, in case it differs or for historical reference.
    file_path = Column(String(255), nullable=False)
    # Store the printer responsible for this gcode file.
    printer_id = Column(Integer, ForeignKey('printers.printer_id'), nullable=False)
    
    # Relationships for convenient access.
    product = db.relationship('Product', back_populates='components')
    # Changed to use back_populates to reference the bidirectional relationship defined in Gcode.
    gcode = db.relationship('Gcode', back_populates='product_components')
    
    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "gcode_id": self.gcode_id,
            "file_path": self.file_path,
            "printer_id": self.printer_id
        }
