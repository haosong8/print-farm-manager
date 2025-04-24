from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
from sqlalchemy.orm import backref
from models import db

# Association table: cascade deletes on both sides
component_gcode_association = Table(
    'component_gcode_association',
    db.Model.metadata,
    Column(
        'product_component_id',
        Integer,
        ForeignKey('product_components.id', ondelete='CASCADE'),
        primary_key=True
    ),
    Column(
        'gcode_id',
        Integer,
        ForeignKey('gcodes.gcode_id', ondelete='CASCADE'),
        primary_key=True
    )
)

class Product(db.Model):
    __tablename__ = 'products'
    
    product_id = Column(Integer, primary_key=True)
    product_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=False)
    
    components = db.relationship(
        'ProductComponent',
        back_populates='product',
        cascade='all, delete-orphan'
    )
    
    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "components": [c.to_dict() for c in self.components]
        }

class ProductComponent(db.Model):
    __tablename__ = 'product_components'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(
        Integer,
        ForeignKey('products.product_id', ondelete='CASCADE'),
        nullable=False
    )
    component_name = Column(String(255), nullable=False)
    required_material = Column(String(100), nullable=False)
    file_path = Column(String(255), nullable=True)
    
    product = db.relationship('Product', back_populates='components')
    
    candidate_gcodes = db.relationship(
        'Gcode',
        secondary=component_gcode_association,
        backref=backref(
            'product_components',
            lazy='dynamic',
            passive_deletes=True
        ),
        lazy='dynamic',
        passive_deletes=True
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "component_name": self.component_name,
            "required_material": self.required_material,
            "file_path": self.file_path,
            "candidate_gcodes": [g.to_dict() for g in self.candidate_gcodes]
        }
