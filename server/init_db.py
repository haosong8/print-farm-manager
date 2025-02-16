#!/usr/bin/env python
import sys
from server import create_app, db
from config import parse_arguments, load_config

args = parse_arguments()
app = create_app(args.config)

with app.app_context():
    print("Registered tables:", db.metadata.tables.keys())
    db.create_all()
    print("Database tables and relationships created successfully.")
sys.exit(0)
