import os
import re
from flask import current_app, request, jsonify
from flask_script import (Manager, Server)
from flask_migrate import (Migrate, MigrateCommand)
from flask_mail import Mail, Message
from flasgger import Swagger

from app import create_app
from app.config import DevConfig
from app.models import (db, user, annotate, mutation, report, run_info, chemo_report, record_config, review_report, sample_v)
from app.models.user import User, Role

app = create_app(DevConfig)
swagger_config = Swagger.DEFAULT_CONFIG
swagger_config['title'] = DevConfig.SWAGGER_TITLE    # 配置大标题
swagger_config['description'] = DevConfig.SWAGGER_DESC
Swagger(app, config=swagger_config)
manager = Manager(app)
migrate = Migrate(app, db)

manager.add_command('server', Server())
manager.add_command('db', MigrateCommand)

mail = Mail(app)


@app.before_request
def is_approved():
    """ 请求是否合法 """
    return None


@manager.shell
def make_shell_content():
    return dict(app=app, db=db)


@manager.shell
def set_up():
    # db.drop_all()
    # db.create_all()

    admin_role = Role(name='admin')
    admin_role.description = 'admin'
    db.session.add(admin_role)

    super_admin = Role(name='super_admin')
    super_admin.description = 'super_admin'
    db.session.add(super_admin)

    default_role = Role(name='default')
    default_role.description = 'default'
    db.session.add(default_role)

    rep_role = Role(name='rep')
    rep_role.description = '报告组成员'
    db.session.add(rep_role)

    rep_admin = Role(name='rep_admin')
    rep_admin.description = '报告组主管'
    db.session.add(rep_admin)

    med_role = Role(name='med')
    med_role.description = '医学部成员'
    db.session.add(med_role)

    med_admin = Role(name='med_admin')
    med_admin.description = '医学部主管'
    db.session.add(med_admin)

    sar_role = Role(name='sar')
    sar_role.description = '收发成员'
    db.session.add(sar_role)

    sar_admin = Role(name='sar_admin')
    sar_admin.description = '收发主管'
    db.session.add(sar_admin)

    # default_role = Role(name='default') #添加权限 联系 ext
    # default_role.description = 'default'
    # db.session.add(default_role)

    admin = User(username='admin')
    admin.mail = 'admin@admin.com'
    admin.set_password("hm714012636")
    admin.roles.append(super_admin)
    admin.roles.append(admin_role)
    admin.roles.append(default_role)

    report = User(username='报告')
    report.mail = 'report@maijinggene.com'
    report.set_password('123456')
    report.roles.append(rep_role)
    db.session.add(report)
    xiaomai = User(username='小迈')
    xiaomai.set_password('123456')
    xiaomai.mail = 'xiaomai@maijinggene.com'
    xiaomai.roles.append(sar_role)
    db.session.add(xiaomai)

    db.session.add(admin)
    db.session.commit()
    # if Role.query.filter(Role.name == 'admin').first():
    #     pass
    # else:
    #     db.session.commit()
    # 文件目录
    dir_static = current_app.config['STATIC_DIR']
    dir_pre_report = current_app.config['PRE_REPORT']
    dir_report = current_app.config['RES_REPORT']
    dir_upload = current_app.config['UPLOADED_FILESAM_DEST']
    dir_pdf = current_app.config['UPLOADED_FILEPDF_DEST']
    dir_apply = current_app.config['UPLOADED_FILEREQ_DEST']
    for dir in [dir_static, dir_pre_report, dir_report, dir_upload, dir_pdf, dir_apply]:
        if not os.path.exists(dir):
            os.mkdir(dir)


if __name__ == '__main__':
    manager.run()
