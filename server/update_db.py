#!/usr/bin/env python

import os
import sys
from config import parse_arguments, load_config, Config
from models import db
from flask import Flask
from flask_migrate import upgrade, Migrate

def create_app_for_migration(config_file):
    """
    Create a minimal Flask app for running database migrations.
    This function loads the configuration the same way as in server.py.
    """
    app = Flask(__name__)
    
    # Load configuration from the specified file.
    config_data = load_config(config_file)
    server_config = Config(
        config_data['HOST'],
        config_data['DB_PORT'],
        config_data['FLASK_PORT'],
        config_data['DB_NAME'],
        config_data['DB_USER'],
        config_data['DB_PASSWORD'],
        config_data['DEBUG']
    )
    
    # Build the SQLALCHEMY_DATABASE_URI from the config data.
    server_config.SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{server_config.DB_USER}:{server_config.DB_PASSWORD}@"
        f"{server_config.HOST}:{server_config.DB_PORT}/{server_config.DB_NAME}"
    )
    
    app.config.from_object(server_config)
    db.init_app(app)
    return app

def ensure_migrations_structure():
    """Ensure that a minimal migrations folder exists with env.py, script.py.mako, and alembic.ini."""
    migrations_dir = 'migrations'
    versions_dir = os.path.join(migrations_dir, 'versions')

    if not os.path.exists(migrations_dir):
        print("Migrations directory not found. Creating minimal migrations structure...")
        os.makedirs(versions_dir, exist_ok=True)
        create_env_file(migrations_dir)
        create_script_mako(migrations_dir)
        create_alembic_ini(migrations_dir)
    else:
        if not os.path.exists(os.path.join(migrations_dir, 'env.py')):
            print("migrations/env.py not found. Creating minimal env.py...")
            create_env_file(migrations_dir)
        if not os.path.exists(os.path.join(migrations_dir, 'script.py.mako')):
            print("migrations/script.py.mako not found. Creating minimal script.py.mako...")
            create_script_mako(migrations_dir)
        if not os.path.exists(os.path.join(migrations_dir, 'alembic.ini')):
            print("migrations/alembic.ini not found. Creating minimal alembic.ini...")
            create_alembic_ini(migrations_dir)

def create_env_file(migrations_dir):
    env_py_content = """\
from __future__ import with_statement
import logging
from logging.config import fileConfig
from alembic import context
from flask import current_app

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception as e:
        print("Warning: Unable to configure logging:", e)

target_metadata = current_app.extensions['migrate'].db.metadata

def run_migrations_offline():
    context.configure(
        url=current_app.config.get("SQLALCHEMY_DATABASE_URI"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = current_app.extensions['migrate'].db.engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""
    with open(os.path.join(migrations_dir, 'env.py'), 'w') as f:
        f.write(env_py_content)

def create_script_mako(migrations_dir):
    script_mako_content = """\
<% 
    import re
    def render_item(item):
        return re.sub(r'\\s+', ' ', str(item)).strip()
%>
"""
    with open(os.path.join(migrations_dir, 'script.py.mako'), 'w') as f:
        f.write(script_mako_content)

def create_alembic_ini(migrations_dir):
    alembic_ini_content = """\
[alembic]
script_location = migrations

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
"""
    with open(os.path.join(migrations_dir, 'alembic.ini'), 'w') as f:
        f.write(alembic_ini_content)

def main():
    # Parse command-line arguments (which must include --config pointing to your server.conf)
    args = parse_arguments()
    # Create the Flask app using the provided config file.
    app = create_app_for_migration(args.config)
    
    # Initialize Flask-Migrate with the app and database.
    from flask_migrate import Migrate
    migrate = Migrate(app, db)
    
    with app.app_context():
        print("Using database:", app.config.get("SQLALCHEMY_DATABASE_URI"))
        ensure_migrations_structure()
        print("Applying migrations using Flask-Migrate...")
        try:
            upgrade(directory='migrations')
            print("Database updated successfully.")
        except Exception as e:
            print("Error applying migrations:", e)
            sys.exit(1)

if __name__ == '__main__':
    main()
