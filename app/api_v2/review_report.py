import os,re,time,shutil, sys
import json
import zipfile
import tempfile
import copy
import pandas as pd
from pathlib import Path
import xlwt
import numpy as np
import requests
from io import BytesIO
from operator import itemgetter, attrgetter
from docxtpl import DocxTemplate, InlineImage, Listing
from datetime import timedelta, datetime

from flask_restful import (reqparse, Resource, request)
from flask import (jsonify, current_app, make_response, send_file)
from flask_mail import Message
from werkzeug.datastructures import FileStorage
from sqlalchemy import and_, or_
from app.libs.lims import LimsApi


from app.models import db
from app.models.user import User
from app.models.review_report import ReviewLib
from app.models.chemo_report import ChemoDatabase, ChemoReport, ReportTemplet
from app.models.sample_v import PatientInfoV, FamilyInfoV, ApplyInfo, SampleInfoV
from app.models.record_config import CancerTypes, SalesInfo, Publisher

from app.libs.ext import file_sam, file_okr, file_pdf, format_time, zip_dir, unzip


def get_info(infos):
    list_all = []
    for info in infos:
        list_all.append(info.to_dict())
    return list_all

def excel_to_dict(file,sheetname = 0):
    df = pd.read_excel(file, keep_default_na=False, sheet_name=sheetname)
    result = []
    for i in df.index:
        dic_row = {}
        df_row = df.loc[i].copy()
        for k in df.columns:
            dic_row[k] = str(df_row[k])
        result.append(dic_row)
    return result


# def change_status(old_stat, step):
#     state_list=['等待出具', '出具中', '内审中', '医学审核中', '终审中', '已终审', '已发布', '审核未通过']
#     new_stat=''
#     if old_stat == '等待出具' and step == 'info':
#         new_stat = '出具中'
#     elif old_stat == '内审中' and step == 'step2':
#         new_stat = '医学审核中'
#     elif old_stat == '医学审核中' and step == 'step3':
#         new_stat = '终审中'
#     elif old_stat == '终审中' and step == 'step4':
#         new_stat = '已终审'
#     elif old_stat == '已终审' and step == 'step5':
#         new_stat = '已发布'
#     else:
#         new_stat = old_stat
#     return(new_stat)

def change_status(old_stat, step):
    state_list=['等待出具', '出具中', '内审中', '医学审核中', '终审中', '已终审', '已发布', '审核未通过']
    new_stat=''
    if old_stat == '等待出具' and step == 'info':
        new_stat = '出具中'
    elif old_stat == '内审中' and step == 'step2':
        new_stat = '医学审核中'
    elif old_stat == '医学审核中' and step == 'step3':
        new_stat = '已医学审核'
    elif old_stat == '已医学审核' and step == 'step4':
        new_stat = '已发布'
    else:
        new_stat = old_stat
    return(new_stat)



def createPdf(wordPath, pdfPath):
    if os.path.exists(pdfPath):
        os.remove(pdfPath)
    pythoncom.CoInitialize()
    word = gencache.EnsureDispatch('Word.Application')
    doc = word.Documents.Open(wordPath, ReadOnly=1)
    doc.ExportAsFixedFormat(pdfPath,constants.wdExportFormatPDF,Item=constants.wdExportDocumentWithMarkup,CreateBookmarks=constants.wdExportCreateHeadingBookmarks)
    word.Quit(constants.wdDoNotSaveChanges)


def send_mail(name, tomail, tital, infos, files):
    mail_list = []
    # mail_cc = [
    #     'dyy@maijinggene.com', 'limengzhen@maijinggene.com', 'sgj@maijinggene.com', 'medicalaffairs@maijinggene.com',
    #     'xiaomai@maijinggene.com', 'zsh@maijinggene.com', 'pathology@maijinggene.com', 'zy@maijinggene.com']

    publishers = Publisher.query.all()  # 正式环境
    mail_cc = [publisher.mail for publisher in publishers]  # 正式环境
    # mail_cc = ['wym@maijinggene.com']  # 测试
    # tomail = 'lwx@maijinggene.com'  # 测试
    mail_list.append(tomail)
    mail_list+=mail_cc
    message = Message(tital, sender=current_app.config['MAIL_USERNAME'], recipients=mail_list)
    message.body = name + '，您好！\n    ' + infos
    for file in files:
        file = os.path.abspath(file)
        with current_app.open_resource(file) as fp:
            file_name=os.path.basename(file)
            message.attach(file_name, 'application/octet-stream', fp.read())
    mail = current_app.extensions.get('mail')
    mail.send(message)

def pdf_api(docx_file, pdf_file):
    header = None
    docx_file_io = open(docx_file,'rb')
    files = {'docx': docx_file_io}
    api_url = 'http://192.168.1.42:5000/api/tools/docxtopdf/'
    response = requests.post(api_url, files=files, headers=header)
    if response.status_code == 200:
        try:
            data = json.loads(response.text)
        except:
            with open(pdf_file, "wb") as io:
                io.write(response.content)
    else:
        print("Error:docx转pdf失败!")


def format_doc_files(kid):
    pdf_name, rp_date, report_url = "", "", ""
    dir_res = current_app.config['RES_REPORT']
    info = ReviewLib.query.filter(ReviewLib.id == kid).first()
    if info:
        if info.status == '医学审核中':
            kid = str(kid)
            dir_res = os.path.join(dir_res, 'Review_Results',kid)
            file = info.report_file
            mgid = info.mgid
            file = os.path.join(dir_res, file)
            z = zipfile.ZipFile(file,'r')
            doc_dir = os.path.join(dir_res, 'report')
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)
            os.makedirs(doc_dir)
            for name in z.namelist():
                if re.search(r'.docx$',name):
                    print(name)
                    z.extract(name,dir_res)
                    temp_doc = os.path.join(dir_res,name)
                    doc_temple = DocxTemplate(temp_doc)
                    rp_date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    temp_dict={}
                    temp_dict['date']=rp_date
                    doc_temple.render(temp_dict)
                    name=os.path.basename(name)
                    doc_temple.save(os.path.join(doc_dir, name))
                    os.remove(temp_doc)
                    pdf_name=re.sub('docx$','pdf',name, 1)
                    doc_file=os.path.abspath(os.path.join(doc_dir, name))
                    pdf_file=os.path.abspath(os.path.join(doc_dir, pdf_name))
                    # createPdf(doc_file, pdf_file)
                    pdf_api(doc_file, pdf_file)  # docx文档转pdf
                    request_url = request.url
                    report_url = re.sub(r'/api/.+$', "/api/static/res_report/Review_Results/{}/report/{}".format(kid, pdf_name), request_url)
            db.session.commit()
    return pdf_name, rp_date, report_url


class ReviewInfoUpload(Resource):
    def post(self):
        """
        方法名称：报告信息文件上传
        方法描述：调用此API接口上传报告信息
        ---
        tags:
            - 报告审核相关API接口
        consumes:
            - multipart/form-data
        parameters:
            - name: file
              in: formData
              required: true
              type: file
              description: 上传样本信息文件, 格式 .xlsx
        responses:
            200:
                description: 文件上传成功!
                schema:
                    required:
                        - code
                        - message
                        - data
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {code: 200, message: "文件上传成功!", data: null}
        """
        filename = file_sam.save(request.files['file'])
        file = file_sam.path(filename)
        list_sam = excel_to_dict(file)
        date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for row in list_sam:
            if not row.get('迈景编号'):
                pass
            new = ReviewLib.query.filter(and_(ReviewLib.mgid == row.get('迈景编号'), ReviewLib.req_mg == row.get('申请单号'), ReviewLib.pro_name == row.get('项目名称'))).first()
            if new:
                continue
            else:
                info=ReviewLib(mgid = row.get('迈景编号'),req_mg = row.get('申请单号'),pa_name = row.get('患者姓名'),pro_name = row.get('项目名称'),
                                    report_num = row.get('份数'),note = row.get('备注'),received_date = row.get('收样日期'),dadeline = row.get('预计报告日'),status = '等待出具')
                db.session.add(info)
        db.session.commit()
        os.remove(file)
        return {"code": 200, "message": "文件上传成功!", "data": None}, 200

class ReviewInfoGet(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page', type=int, help='页码')
        self.parser.add_argument('page_per', type=int, help='每页数量')
        self.parser.add_argument('ids', help='迈景id')


    def get(self):
        args = self.parser.parse_args()
        page = args.get('page')
        per_page = args.get('page_per')

        token = request.headers.get('token')
        user = User.verify_auth_token(token).to_dict()
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405
        infos = ReviewLib.query.order_by(ReviewLib.dadeline.desc()).all()
        sample_info={}
        sample_info['sample']=get_info(infos)
        return jsonify(sample_info)


class ReviewSearch(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page', type=int, help='页码')
        self.parser.add_argument('page_per', type=int, help='每页数量')
        self.parser.add_argument('key', help='关键词')
        self.parser.add_argument('peop', help='内容负责人')
        self.parser.add_argument('start', default="", help='预计报告日期 - 起始')
        self.parser.add_argument('end', default="", help='预计报告日期 - 结束')
        self.parser.add_argument('sort_by_id', default="", help='通过mg_id排序')
        self.parser.add_argument('status', default='全部', help='状态')

    def get(self):
        """
            方法名称：获取信息API接口
            方法描述：调用此API接口获取信息
            ---
            tags:
                - 报告审核相关API接口
            parameters:
                - name: peop
                  in: query
                  required: true
                  type: string
                  description: 内审人 默认为 'all'

                - name: sort_by_id
                  in: query
                  required: true
                  type: string
                  description: 通过mg_id排序, 默认为 "desc"

                - name: status
                  in: query
                  required: true
                  type: string
                  description: 报告状态, 默认为 "全部"

                - name: key
                  in: query
                  type: string
                  description: 搜索内容

                - name: start
                  in: query
                  type: string
                  description: 预计报告日期 - 开始 '2020.09.01'

                - name: end
                  in: query
                  type: string
                  description: 预计报告日期 - 结束 '2020.09.05'

                - name: page
                  in: query
                  type: integer
                  description: 当前页码 - 默认为1

                - name: page_size
                  in: query
                  type: integer
                  description: 每页的数据条数 - 默认为10

            responses:
                200:
                    description: 获取用户信息成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200,message: "获取身份信息成功!",data: {
                                total: 797,
                                data: [{id: 797, mgid: "MG2006149", req_mg: "MG2093460585", pa_name: "罗惠群",
                                pro_name: "卵巢癌BRCA1/2基因检测（NGS）（胚系突变检测）",received_date: "2020-08-25 10:00",
                                rep_reviewer: "报告",report_date: null,report_file: null,report_num: "1",reporter: null,req_mg: "MG2066130202",
                                review_inside: "内审意见", review_info: "医学审核意见", status: "等待出具", upreport_date: null}]
                            }
                        }
        """
        args = self.parser.parse_args()
        page = args.get('page')
        per_page = args.get('page_per')
        key_info = args.get('key')
        peop = args.get('peop')
        start = args.get('start')  # 开始时间
        end = args.get('end')  # 结束时间
        status = args.get('status')  # 状态
        sort_by_id = args.get('sort_by_id')  # 通过mg_id排序

        token = request.headers.get('token')
        user = User.verify_auth_token(token).to_dict()
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        filter_info={}
        username=user['username']
        #username='报告组员1'

        if peop == 'reporter':  # 报告出具
            if key_info:
                filter_info={and_(ReviewLib.reporter == username, or_(ReviewLib.mgid.like('%{}%'.format(key_info)), ReviewLib.req_mg.like('%{}%'.format(key_info)),
                         ReviewLib.pa_name.like('%{}%'.format(key_info)), ReviewLib.pro_name.like('%{}%'.format(key_info)),
                         ReviewLib.status.like('%{}%'.format(key_info)), ReviewLib.reporter.like('%{}%'.format(key_info)),
                         ReviewLib.rep_reviewer.like('%{}%'.format(key_info)), ReviewLib.med_reviewer.like('%{}%'.format(key_info))))}
            else:
                filter_info={ReviewLib.reporter == username}
        elif peop == 'rep_reviewer':  # 报告内审
            if key_info:
                filter_info={and_(ReviewLib.rep_reviewer == username, or_(ReviewLib.mgid.like('%{}%'.format(key_info)), ReviewLib.req_mg.like('%{}%'.format(key_info)),
                                     ReviewLib.pa_name.like('%{}%'.format(key_info)), ReviewLib.pro_name.like('%{}%'.format(key_info)),
                                     ReviewLib.status.like('%{}%'.format(key_info)), ReviewLib.reporter.like('%{}%'.format(key_info)),
                                     ReviewLib.rep_reviewer.like('%{}%'.format(key_info)), ReviewLib.med_reviewer.like('%{}%'.format(key_info))))}
            else:
                filter_info={ReviewLib.rep_reviewer == username}
        elif peop == 'med_reviewer':  # 医学审核
            if key_info:
                filter_info={and_(ReviewLib.med_reviewer == username, or_(ReviewLib.mgid.like('%{}%'.format(key_info)), ReviewLib.req_mg.like('%{}%'.format(key_info)),
                                     ReviewLib.pa_name.like('%{}%'.format(key_info)), ReviewLib.pro_name.like('%{}%'.format(key_info)),
                                     ReviewLib.status.like('%{}%'.format(key_info)), ReviewLib.reporter.like('%{}%'.format(key_info)),
                                     ReviewLib.rep_reviewer.like('%{}%'.format(key_info)), ReviewLib.med_reviewer.like('%{}%'.format(key_info))))}
            else:
                filter_info={ReviewLib.med_reviewer == username}
        else:
            filter_info={or_(ReviewLib.mgid.like('%{}%'.format(key_info)), ReviewLib.req_mg.like('%{}%'.format(key_info)),
                                     ReviewLib.pa_name.like('%{}%'.format(key_info)), ReviewLib.pro_name.like('%{}%'.format(key_info)),
                                     ReviewLib.status.like('%{}%'.format(key_info)), ReviewLib.reporter.like('%{}%'.format(key_info)),
                                     ReviewLib.rep_reviewer.like('%{}%'.format(key_info)), ReviewLib.med_reviewer.like('%{}%'.format(key_info)))}

        # infos = ReviewLib.query.filter(*filter_info).order_by(ReviewLib.dadeline.desc()).all()
        if start:
            start = format_time(start)
            if end:
                end = format_time(end)
            else:
                end = format_time("2100-01-01")
            infos = ReviewLib.query.filter(*filter_info).filter(ReviewLib.dadeline.between(start, end + timedelta(days=1)))
        else:
            infos = ReviewLib.query.filter(*filter_info)
        # 筛选状态
        if status != "全部":
            status_list = status.split(',')
            infos = infos.filter(ReviewLib.status.in_(status_list))

        # 排序
        sort_way = {ReviewLib.dadeline.desc()}
        infos = infos.order_by(*sort_way).paginate(page=page, per_page=per_page, error_out=False)
        sample_info={}
        sample_info['data']=get_info(infos.items)
        sample_info['total'] = infos.total
        # return jsonify(sample_info)

        return {"code": 200, "message": "获取信息成功!", "data": sample_info}, 200


class ReviewFormDataUpload(Resource):
    def post(self):
        """
            方法名称：提交分配任务、提交审核结果API接口
            方法描述：调用此API接口提交分配任务、提交审核结果
            ---
            tags:
                - 报告审核相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - formdata
                    properties:
                        formdata:
                            type: string
                            description: 分配任务信息, json字符串
            responses:
                200:
                    description: 分配任务提交成功!
                    schema:
                        required:
                            - code
                            - message
                            - data
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "分配任务成功!", data: null}
        """
        data = request.get_data()
        formdata = (json.loads(data)['formdata'])

        if formdata:
            kid = formdata['kid']
            new = ReviewLib.query.filter(ReviewLib.id == kid).first()
            if new:
                if 'reporter' in formdata:
                    new.reporter=formdata['reporter']
                if 'rep_reviewer' in formdata:
                    new.rep_reviewer=formdata['rep_reviewer']
                if 'med_reviewer' in formdata:  # 医学审核
                    new.med_reviewer=formdata['med_reviewer']
                if 'review_inside' in formdata:  # 内审意见
                    new.review_inside = formdata['review_inside']
                if 'review_info' in formdata:  # 医学审核意见
                    new.review_info=formdata['review_info']
                if 'reviewres' in formdata:  # 审核信息
                    if formdata['reviewres'] == '通过':
                        # 状态: 医学审核中 & 审核通过 => 推送报告到lims系统
                        new_status = change_status(new.status, formdata['steps'])
                    else:
                        new_status = '审核未通过'
                elif 'status' in formdata:  # 任务分配
                    new_status = change_status(formdata['status'], formdata['steps'])
            if kid and new_status != "审核未通过":  # 审核未通过不需要转pdf和推送lims系统
                try:
                    pdf_name, report_date, report_url = format_doc_files(kid)
                except Exception as e:
                    print(e)
                    return {"code": 400, "message": "docx转pdf失败!", "data": None}, 400
                # 推送报告到lims系统
                if new_status == "已医学审核" and all([item != "" for item in [pdf_name, report_date, report_url]]) and str(new.resource) == "lims":
                    data = {
                        "sampleId": new.mgid,
                        "batchCode": new.req_mg,
                        "reportedDate": report_date,
                        "productCode": new.pro_num,  # 产品编码
                        "productName": new.pro_name,  # 产品名称
                        "reporterCode": "",  # 报告出具者编号
                        "reporterName": new.reporter,  # 报告出具者
                        "reportNames": [pdf_name],  # 报告名称
                        "remark": new.note,  # 备注
                        "reportType": "",
                        "paths": [report_url],
                        "internalAuditor": new.rep_reviewer,  # 内审人
                        "medicalAuditor": new.med_reviewer  # 医学审核人
                    }
                    # data = {}
                    # print(data)
                    data = json.dumps([data])
                    print(data)
                    url = current_app.config['PUSH_REPORT']
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0',
                        "Content-Type": "application/json"
                    }
                    try:
                        response = requests.post(url, data=data, headers=headers)
                        if response.status_code == 200:  # 接口正常访问
                            res_data = json.loads(response.text)
                            res_code = res_data["code"]
                            res_msg = res_data["msg"]
                            if int(res_code) == 200:  # 推送成功
                                new.status = new_status  # 成功
                                db.session.commit()
                                return {"code": 200, "message": "提交成功!", "data": None}, 200
                            else:
                                return {"code": 400, "message": "{} 报告推送lims系统失败!".format(str(res_msg)), "data": None}, 400
                        else:
                            return {"code": 400, "message": "报告推送lims系统失败!", "data": None}, 400
                    except Exception as e:
                        print(e)
                        return {"code": 400, "message": "报告推送lims系统失败!", "data": None}, 400
        new.status = new_status  # 成功
        db.session.commit()
        return {"code": 200, "message": "提交成功!", "data": None}, 200


class ReceiveExceptionReport(Resource):
    """ 接收异常报告 """
    def post(self):
        """
            方法名称：接收LIMS异常报告接口API接口
            方法描述：调用此API接口接收LIMS异常报告
            ---
            tags:
                - 报告审核相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - data
                    properties:
                        data:
                            type: string
                            description: 异常报告信息, json字符串
            responses:
                200:
                    description: 分接收成功!
                    schema:
                        required:
                            - code
                            - message
                            - data
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "异常报告接收成功!", data: null}
        """
        try:
            data = request.get_json()
            print(data)
        except Exception as error:
            print(error)
            return {"code": 400, "message": "Error: {} 数据获取异常!".format(error), "data": None}, 400
        flag = True
        error_info = []
        for item in data:
            if not all([True if filed in item.keys() else False for filed in ["sampleId", "batchCode", "productName", "productCode", "remark"]]):
                return {"code": 400, "message": "请检查数据字段!", "data": item}, 400
            mgid = item["sampleId"]
            req_mg = item["batchCode"]
            pro_name = item["productName"]
            pro_num = item["productCode"]
            remark = item["remark"]
            review = ReviewLib.query.filter(
                and_(
                    ReviewLib.mgid == mgid,
                    ReviewLib.req_mg == req_mg,
                    ReviewLib.pro_num == pro_num
                )
            ).first()
            if review:
                review_info = str(review.review_info) if review.review_info else ""
                review.review_info = review_info + ";lims:" + str(remark)
                review.status = "审核未通过"
            else:
                flag = False
                error_info.append("{} {}".format(req_mg, mgid))

        if flag:
            try:
                db.session.commit()
            except Exception as error:
                db.session.rollback()  # 回滚
                return {"code": 400, "message": "推送失败! error: {}".format(error), "data": None}, 400
            else:
                return {"code": 200, "message": "数据推送成功!", "data": None}, 200
        else:
            return {"code": 400, "message": "推送失败! {} 报告系统未查询到信息!".format("&".join(error_info)), "data": None}, 400


class ReviewReportEmail(Resource):
    def post(self):
        """
            方法名称：报告发布API接口
            方法描述：调用此API接口发布报告
            ---
            tags:
                - 报告审核相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - formdata
                    properties:
                        formdata:
                            type: string
                            description: 报告发布表单信息, json字符串
            responses:
                200:
                    description: 报告发布成功!
                    schema:
                        required:
                            - code
                            - message
                            - data
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "报告发布成功!", data: null}
        """
        data = request.get_data()
        all_data = json.loads(json.loads(data)['formdata']['formData'])
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'Review_Results')
        msg=''
        warning = []
        success = []
        if len(all_data) > 0:
            for formdata in all_data:  # 批量发布
                kid = formdata['id']
                new = ReviewLib.query.filter(ReviewLib.id == kid).first()
                if new:
                    kid = str(kid)
                    pdf_files=[]
                    report_dir=os.path.join(dir_res, kid, 'report')
                    for root,dirs,files in os.walk(report_dir):
                        for file in files:
                            if re.search(r'.pdf$', file):
                                pdf_files.append(os.path.join(root,file))
                    infos = '申请单：{}报告已出具,报告见附件！\n项目相关信息如下：\n项目名称：{}\n患者姓名：{}\n'.format(new.req_mg, new.pro_name, new.pa_name)
                    tital = '迈景基因检测报告-{}-{}-{}'.format(new.pa_name, new.req_mg, new.pro_name)
                    if len(pdf_files) > 0:
                        # 从LIMS获取
                        saler = ""
                        saler_mail = ""
                        # 获取销售姓名和邮箱
                        if str(new.resource) == "lims":
                            try:
                                lims = LimsApi(current_app.config["LIMS_CFG"])
                                apply_info = lims.get_apply_info(new.req_mg)
                                saler = apply_info["销售代表"]
                                info = SalesInfo.query.filter(SalesInfo.name == saler).first()
                                if info:
                                    saler = info.name
                                    saler_mail = info.mail
                            except Exception as e:
                                print(e)
                        else:
                            try:
                                code = new.req_mg[4:8]
                                info = SalesInfo.query.filter(SalesInfo.code == code).first()
                                saler = info.name
                                saler_mail = info.mail
                            except Exception as e:
                                warning.append("{} {} 获取销售信息失败!".format(new.mgid, e))
                                continue
                        try:
                            send_mail(saler, saler_mail, tital, infos, pdf_files)
                        except Exception as e:
                            print(e)
                            msg = '样品{}邮件发送失败'.format(new.mgid)
                            warning.append(msg)
                        else:
                            new.status = '已发布'
                            new.report_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            db.session.commit()
                            msg='样品{}发布完成！'.format(new.mgid)
                            success.append(msg)
                    else:
                        msg='样品{}发布失败！未检测到需要发送的PDF报告，请核查确定！'.format(new.mgid)
                        warning.append(msg)
                else:
                    msg = '样品{}发布失败！样品信息未获取成功，请核查确定！'.format(new.mgid)
                    warning.append(msg)
        code = 200 if len(warning) == 0 else 400
        message = "{} {}".format(";".join(success), ";".join(warning))
        return {"code": code, "message": message, "data": None}, code


class ReviewUser(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('role', help='权限')

    def get(self):
        """
            方法名称：获取用户信息API接口
            方法描述：调用此API接口获取用户的相关信息
            ---
            tags:
                - 报告审核相关API接口
            parameters:
                - name: role
                  in: query
                  required: true
                  type: string
                  description: 角色
            responses:
                200:
                    description: 获取用户成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200,message: "获取身份信息成功!",data: ["报告", "邹嘉琪", "胡雪", "胡司妮", "陈梓华", "李宇峰"]}
        """
        args = self.parser.parse_args()
        role = args.get('role')
        users = User.query.all()
        all_user = []
        for user in users:
            flag=0
            for k in user.roles:
                if role == k.name:
                    flag+=1
            if flag > 0:
                all_user.append(user.username)
        return {"code": 200, "message": "获取用户成功!", "data": all_user}, 200


class ReviewResultsUpdate(Resource):
    def post(self):
        """
        方法名称：报告结果文件上传
        方法描述：调用此API接口上传报告结果
        ---
        tags:
            - 报告审核相关API接口
        consumes:
            - multipart/form-data
        parameters:
            - name: kid
              in: formData
              required: true
              type: string
              description: kid

            - name: file
              in: formData
              required: true
              type: file
              description: 上传样本结果文件, 格式 .xlsx
        responses:
            200:
                description: 文件上传成功!
                schema:
                    required:
                        - code
                        - message
                        - data
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {code: 200, message: "文件上传成功!", data: null}
        """
        filename = file_okr.save(request.files['file'])
        kid = request.form['kid']
        file = file_okr.path(filename)
        dir_res = current_app.config['RES_REPORT']
        info=ReviewLib.query.filter(ReviewLib.id == kid).first()
        if info:
            dir_res=os.path.join(dir_res,'Review_Results',kid)
            if os.path.exists(dir_res):
                shutil.rmtree(dir_res)
            os.makedirs(dir_res)
            shutil.move(file,dir_res)
            info.report_file=filename
            info.status='内审中'
            info.upreport_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        db.session.commit()
        return {"code": 200, "message": "文件上传成功!", "data": None}, 200


class ReviewResultsDownload(Resource):
    def post(self):
        """
            方法名称：报告结果下载API接口
            方法描述：调用此API接口下载报告结果
            ---
            tags:
                - 报告审核相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - kid
                    properties:
                        kid:
                            type: string
                            description: kid
            responses:
                200:
                    description: 文件下载成功!
                    schema:
                        required:
                            - code
                            - message
                            - data
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "文件下载成功!", data: null}
        """
        data = request.get_data()
        kid = json.loads(data)['kid']
        info=ReviewLib.query.filter(ReviewLib.id == kid).first()
        if info:
            resuts_file=info.report_file
            kid = str(kid)
            resuts_file=Path(os.path.abspath(os.path.join('app','static', 'res_report', 'Review_Results', kid, resuts_file))).as_posix()
            if not os.path.isfile(resuts_file):
                return {"code": 404, "message": "文件不存在!", "data": None}, 404
            response = send_file(resuts_file, attachment_filename=kid, as_attachment=True, cache_timeout=5)
            return response
        else:
            return {"code": 404, "message": "文件不存在!", "data": None}, 404


class ReviewPdfDownload(Resource):
    def post(self):
        """ 报告管理 下载报告结果 """
        data = request.get_data()
        kids = json.loads(data)['kids']
        fm = json.loads(data)['fm']
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'Review_Results')
        pdf_files=[]
        for kid in kids:
            info=ReviewLib.query.filter(ReviewLib.id == kid).first()
            if info:
                kid = str(kid)
                report_dir=os.path.join(dir_res, kid, 'report')
                for root,dirs,files in os.walk(report_dir):
                    for file in files:
                        if re.search(r'.pdf$', file):
                            pdf_files.append(os.path.join(root,file))
                        elif re.search(r'.docx$', file) and fm == 'all':
                            pdf_files.append(os.path.join(root,file))
                report_file=os.path.join(dir_res, kid, info.report_file)
                if os.path.exists(report_file) and fm == 'all':
                    pdf_files.append(report_file)
        zip_file=BytesIO()
        if len(pdf_files)>0:
            with zipfile.ZipFile(zip_file,'w',zipfile.ZIP_DEFLATED) as zf:
                for file in pdf_files:
                    filename=os.path.basename(file)
                    with open(file,'rb') as fp:
                        zf.writestr(filename,fp.read())
        zip_file.seek(0)
        out_date=time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
        name='Total_Sample-{}.zip'.format(out_date)
        response = send_file(zip_file, attachment_filename=name, as_attachment=True, cache_timeout=5)
        return response


class ExportData(Resource):
    """ 导出结果 """
    def get(self):
        """
            方法名称：报告管理导出数据API接口
            方法描述：调用此API接口报告管理页面导出数据
            ---
            tags:
                - 报告审核相关API接口
            parameters:
                - name: start
                  in: query
                  type: string
                  description: 开始时间

                - name: end
                  in: query
                  type: string
                  description: 结束时间

            responses:
                200:
                    description: 数据导出成功!
                400:
                    description: 数据失败或错误信息!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 400,message: "错误信息!",data: None}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('start', type=str, default='', help="开始时间")
        parser.add_argument('end', type=str, default='', help="结束时间")
        args = parser.parse_args()
        # 获取参数
        start = args.get('start')
        end = args.get('end')
        dir_res = Path(current_app.config['RES_REPORT']).as_posix()
        dir_res = os.path.join(dir_res, 'Review_Results')
        if not start:
            return {"code": 400, "message": "输入开始时间!", "data": None}, 400
        # download_filename = 'Total_Sample_{}_{}.zip'.format(start, end)
        # 下载文件夹
        download_dir = Path(os.path.join(dir_res, 'Total_Sample_{}_{}'.format(start, end))).as_posix()
        download_filename = 'Total_Sample_{}_{}'.format(start, end)
        start = format_time(start)
        if end:
            end = format_time(end)
        else:
            end = format_time("2100-01-01")
        if os.path.isdir(download_dir):
            shutil.rmtree(download_dir)
        try:
            os.makedirs(download_dir)
        except Exception as e:
            print(e)
            return {"code": 400, "message": "创建下载目录失败!", "data": None}, 400
        title = ['id', 'mgid', 'req_mg', 'pa_name', 'pro_name', 'report_num', 'received_date', 'dadeline', 'status',
                                   'reporter', 'rep_reviewer', 'med_reviewer', 'review_inside', 'review_info', 'report_date']
        df = pd.DataFrame(columns=title)
        infos = ReviewLib.query.filter(ReviewLib.dadeline.between(start, end + timedelta(days=1)))
        for info in infos:
            if info.status != '已发布':
                continue
            kid = str(info.id)
            report_dir = os.path.join(dir_res, kid, 'report')
            if os.path.isdir(report_dir):
                print(report_dir)
                os.system("cp -r %s %s/%s" % (report_dir, download_dir, info.mgid))  # 备份文件
            else:
                try:
                    os.makedirs("{}/{}".format(download_dir, info.mgid))
                except Exception as e:
                    print(e)
            info_row = info.to_dict()
            row = {key: info_row[key] for key in title if key in info_row.keys()}
            df = df.append(row, ignore_index=True)
        # 信息表
        df = df.rename(columns={"id": "编号", "mgid": "迈景编号", "req_mg": "申请单号",
                                "pa_name": "患者名字", "pro_name": "检测项目", "report_num": "份数",
                                'received_date': "收样日期", 'dadeline': "预计报告日期", 'status': "状态",
                                'reporter': '报告出具人', 'rep_reviewer': '内审人', 'med_reviewer': '医学审核人', 'review_inside': '内审意见', 'review_info': '审核意见',
                                'report_date': '报告日期', })
        df.to_excel("{}/{}.xlsx".format(download_dir, download_filename), index=False)
        # 压缩目录
        try:
            zip_file = zip_dir(download_dir)
        except Exception as e:
            print(e)
            return {"code": 400, "message": "文件压缩失败!", "data": None}, 400
        if os.path.isfile(zip_file):
            zip_file = Path(os.path.realpath(zip_file)).as_posix()
            return send_file(zip_file, attachment_filename=download_filename + '.zip', as_attachment=True)


class EditNote(Resource):
    """ 报告出具 - 修改备注信息功能 """
    def put(self):
        """
            方法名称：报告出具修改备注API接口
            方法描述：调用此API接口修改备注信息
            ---
            tags:
                - 报告审核相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                        - note
                    properties:
                        id:
                            type: integer
                            description: 报告数据库id
                        note:
                            type: string
                            description: 备注信息
            responses:
                200:
                    description: 备注信息更新成功!
                    schema:
                        required:
                            - code
                            - message
                            - data
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "备注信息更新成功!", data: null}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=int, required=True, help="数据库id")
        parser.add_argument('note', type=str, default='', help="备注信息")
        args = parser.parse_args()
        # 获取参数
        kid = args.get('id')
        note = args.get('note')
        if len(note) >= 255:
            return {"code": 400, "message": "备注信息长度不能大于255字符!", "data": None}, 400
        report = ReviewLib.query.filter(ReviewLib.id == kid).first()
        if report:
            report.note = note
            db.session.commit()
            return {"code": 200, "message": "备注信息更新成功!", "data": None}, 200
        else:
            return {"code": 400, "message": "未查询到报告信息!", "data": None}, 400


class OnlineRead(Resource):
    """ 在线审核功能 """
    def get(self):
        """
            方法名称：在线审核获取样本信息API接口
            方法描述：调用此API接口 - 在线审核获取样本信息
            ---
            tags:
                - 报告审核相关API接口
            parameters:
                - name: id
                  in: query
                  type: integer
                  description: 报告id

            responses:
                200:
                    description: 获取信息成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200,message: "获取身份信息成功!",data: {"id": 5053, 'docx_file': 'xxx.docx', 'unzip_dir': 'MG111223'}}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=int, required=True, help="数据库id")
        args = parser.parse_args()
        # 获取参数
        kid = args.get('id')
        # 获取审核信息
        review = ReviewLib.query.get(kid)
        if review:
            review_dir = current_app.config["RES_REPORT"]
            report_dir = os.path.join(review_dir, 'Review_Results', str(kid))
            report_file = os.path.join(report_dir, str(review.report_file))
            if not os.path.isfile(report_file):
                return {"code": 404, "message": "{} 报告文件不存在!".format(str(review.report_file)), "data": None}, 404
            # 解压文件
            try:
                # 解压后的目录名
                # unzip_dirname = re.sub(r'\.zip$', '', str(review.report_file))
                unzip_dir = os.path.join(report_dir, "online")
                if os.path.exists(unzip_dir):
                    shutil.rmtree(unzip_dir)
                os.makedirs(unzip_dir)
                # 解压文件
                zip = zipfile.ZipFile(report_file, 'r')
                for name in zip.namelist():
                    # 修复中文名乱码
                    try:
                        docx_file = os.path.basename(name.encode('cp437').decode('gbk'))
                    except Exception as e:
                        print(e)
                        docx_file = os.path.basename(name.encode('utf-8').decode('utf-8'))
                    if re.search(r'\.docx$', name):
                        hfile = open("{}/{}".format(unzip_dir, docx_file), 'wb')
                        hfile.write(zip.read(name))
                        hfile.close()
                        return {"code": 200, "message": "信息获取成功!", "data": {"id": kid, 'docx_file': docx_file, 'unzip_dir': 'online'}}, 200
                zip.close()
                return {"code": 404, "message": "迈景编号: {} 报告未找到!".format(review.mgid), "data": None}, 404
            except Exception as e:
                print(e)
                return {"code": 400, "message": "解压文件失败!", "data": None}, 400
        else:
            return {"code": 400, "message": "未查找到审核信息", "data": None}, 400


class GetSalerInfo(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('code', help='销售编号')

    def get(self):
        args = self.parser.parse_args()
        code = args.get('code')
        info=SalesInfo.query.filter(SalesInfo.code == code).first()
        saler_info={}
        saler_info['name']=info.name
        saler_info['mail']=info.mail
        return jsonify(saler_info)
