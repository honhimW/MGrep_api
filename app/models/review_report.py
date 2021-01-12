from . import db
from datetime import datetime

class ReviewLib(db.Model):
    __tablename__ = 'review_lib'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    run = db.Column(db.String(255))  # 新增字段, run名称
    mgid = db.Column(db.String(255))
    req_mg = db.Column(db.String(255))
    detect_way = db.Column(db.String(255))  # 新增字段, 检测策略
    pa_name = db.Column(db.String(255))
    pro_name = db.Column(db.String(255))
    pro_num = db.Column(db.String(255))  # 新增字段, 报告模板编号
    report_num = db.Column(db.String(255))
    note = db.Column(db.String(255))
    received_date = db.Column(db.String(255))
    dadeline = db.Column(db.String(255))
    status = db.Column(db.String(255))
    review_inside = db.Column(db.String(255))  # 内审意见
    review_info = db.Column(db.String(255))  # 医学审核意见
    reporter = db.Column(db.String(255))
    rep_reviewer = db.Column(db.String(255))
    med_reviewer = db.Column(db.String(255))
    report_date = db.Column(db.String(255))
    upreport_date = db.Column(db.String(255))
    report_file = db.Column(db.String(255))
    submit_time = db.Column(db.DateTime, default=datetime.now())
    resource = db.Column(db.String(50))  # 数据来源, 新增字段

    def to_dict(self):
        my_dict = {
            'id':self.id,
            'mgid': self.mgid,
            'req_mg': self.req_mg,
            'pa_name': self.pa_name,
            'pro_name': self.pro_name,
            'pro_num': self.pro_num,
            'report_num': self.report_num,
            'note': self.note,
            'received_date': self.received_date,
            'dadeline': self.dadeline,
            'status': self.status,
            'review_inside': self.review_inside,
            'review_info': self.review_info,
            'reporter': self.reporter,
            'rep_reviewer': self.rep_reviewer,
            'med_reviewer': self.med_reviewer,
            'report_date': self.report_date,
            'upreport_date': self.upreport_date,
            'report_file': self.report_file,
            'detect_way': self.detect_way,
            'resource': self.resource
        }
        return my_dict
