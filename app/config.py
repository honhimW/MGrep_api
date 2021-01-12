import os


class Config(object):
    # cat /dev/urandom | tr -cd 'a-f0-9' | head -c 32 获取随机字符
    SECRET_KEY = '6c61a71132325a99fecc0716b1b6d650'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DIALECT = "mysql"
    DRIVER = 'pymysql'
    USERNAME = os.environ.get('SQL_USERNAME')
    PASSWORD = os.environ.get('SQL_PASSWORD')
    HOST = 'localhost'
    PORT = os.environ.get('SQL_PORT')
    DATABASE = os.environ.get('SQL_DATABASE')
    # DATABASE = "db_auto"

    MY_SQL = 'mysql+pymysql://{}:{}@localhost:{}/{}?charset=utf8'.format(USERNAME, PASSWORD, PORT, DATABASE)
    SQLALCHEMY_DATABASE_URI = MY_SQL
    STATIC_DIR = 'app/static'
    COUNT_DEST = 'app/static/upload'
    PRE_REPORT = 'app/static/pre_report'  # 报告需求文件夹
    RES_REPORT = 'app/static/res_report'  # 报告结果保存文件夹
    UPLOADED_FILEPDF_DEST = 'app/static/res_report/okr'
    UPLOADED_FILESAM_DEST = 'app/static/upload'
    UPLOADED_FILEOKR_DEST = 'app/static/upload'
    UPLOADED_FILEREQ_DEST = 'app/static/apply'

    MONGODB_SETTING = {
        'db': 'local',
        'host': 'localhost',
        'port': 27017
    }

    # celery 配置
    CELERY_BROKER_URL = 'amqp://guest@localhost//'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

    # 邮件服务  腾讯企业邮箱
    MAIL_SERVER = 'smtp.exmail.qq.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USE_TLS = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # lims api接口
    # PUSH_REPORT = "http://183.237.4.230:8090/open/report/accept"   # 推送报告到lims系统
    # PUSH_QC_LIMS = "http://183.237.4.230:8090/open/analysis/quality"   # 推送质控结果到报告系统
    # PUSH_RESULT_LIMS = "http://183.237.4.230:8090/open/analysis/result"  # 推送生信分析结果到报告系统

    # lims配置
    # LIMS_CFG = {
    #     "host": "183.237.4.230",
    #     "port": 3308,
    #     "user": "root",
    #     "passwd": "123456",
    #     "dbname": "mjjy_dev"
    # }

    # lims api接口
    PUSH_REPORT = "http://192.168.1.182:8090/open/report/accept"   # 推送报告到lims系统
    PUSH_QC_LIMS = "http://192.168.1.182:8090/open/analysis/quality"   # 推送质控结果到报告系统
    PUSH_RESULT_LIMS = "http://192.168.1.182:8090/open/analysis/result"  # 推送生信分析结果到报告系统

    # lims配置
    LIMS_CFG = {
        "host": "192.168.1.183",
        "port": 3306,
        "user": "root",
        "passwd": "Mjlims57.",
        "dbname": "mjjy_dev"
    }


class ProdConfig(Config):
    RESULT_DIR = '/data/MGR/IR_Analysis/'
    # RESULT_DIR = '/home/wuyangming/research/Ion_pipeline/testing_environment/auto/V1.0/IR_Analysis/'
    SAMPLEINFO_DIR = '/home/wanghongqian/staticFile/sample/'
    APPLY_ZIP = '/home/wanghongqian/staticFile/application/'


class DevConfig(Config):
    DEBUG = True
    # RESULT_DIR = '/home/hemin/Desktop/信息录入/ir_result'
    RESULT_DIR = 'D:/development/2020-new-task/okr'
    SAMPLEINFO_DIR = '/home/wanghongqian/staticFile/sample/'
    APPLY_ZIP = '/home/hemin/Desktop/信息录入/apply'
    SWAGGER_TITLE = "迈景报告自动化系统API接口文档"
    SWAGGER_DESC = "迈景报告自动化系统API接口文档 - 测试环境使用"




class TestConfig(Config):
    pass
