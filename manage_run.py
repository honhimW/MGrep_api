import os

import re
from flask import current_app, request, jsonify
from flask_script import (Manager, Server)
from flask_migrate import (Migrate, MigrateCommand)
from flask_mail import Mail, Message

from app import create_app
from app.config import ProdConfig
from app.models import (db, annotate, mutation, report, run_info, chemo_report)
from app.models.user import User, Role

app = create_app(ProdConfig)
manager = Manager(app)
migrate = Migrate(app, db)

manager.add_command('server', Server())
manager.add_command('db', MigrateCommand)

mail = Mail(app)


@manager.shell
def make_shell_content():
    return dict(app=app, db=db)


if __name__ == '__main__':
    manager.run()
