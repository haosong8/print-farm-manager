from flask import Blueprint, jsonify
from models.printers import Printer
from models import db

printer_bp = Blueprint('printer', __name__, url_prefix='/printers')

@printer_bp.route('/', methods=['GET'])
def get_printers():
    printers = Printer.query.all()
    return jsonify([p.to_dict() for p in printers])
