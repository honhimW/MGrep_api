import os, json, re

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

from flask import (jsonify, current_app, send_from_directory, Response, make_response, send_file)
from flask_restful import (reqparse, Resource, request)

from sqlalchemy import and_, or_
from app.models import db
from app.models.user import User
from app.models.report import Report
from app.models.review_report import ReviewLib
from app.models.run_info import SeqInfo, RunInfo
from app.models.mutation import Mutation, Mutations
from app.models.annotate import Annotate, OKR, AnnotateAuto, OkrDrug, ClinicInterpretation
from app.models.sample_v import ApplyInfo
from app.models.record_config import CancerTypes

from app.libs.report import first_check, get_rep_item, set_gene_list, del_db, dict2df, okr_create, grade_mutation, \
    get_grade, get_drug, okr_create_n, md_create, get_okr_vcf, get_result_file, get_clincl
from app.libs.ext import set_time_now, dic_mu_type, dic_zsy_introduce, get_info,zip_dir
from app.libs.okr_ext import fileokr_to_dict, create_reports_using_report_file, is_okr
from app.libs.get_data import read_json, splitN
from app.libs.lims import LimsApi


class ReportStart(Resource):
    '''
    报告开始制作:承包
    '''

    # todo 添加真实用户

    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page', type=int, help='页码')
        self.parser.add_argument('page_per', type=int, help='每页数量')
        self.parser.add_argument('sams', help='报告', action='append')

    def get(self):

        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, 'message': '无访问权限!', "data": None}, 405

        args = self.parser.parse_args()
        page = args.get('page')
        page_per = args.get('page_per')
        reps = Report.query.order_by(Report.id.desc()).paginate(page=page, per_page=page_per, error_out=False)
        list_rep = []
        all_rep = []
        for rep in reps.items:
            # print(rep.id)
            report_user = rep.report_user
            if report_user == user.username:
                rep_dict = rep.to_dict()
                if rep.sample_info_v:
                    rep_dict['mg_id'] = rep.sample_info_v.sample_id
                else:
                    rep_dict['mg_id'] = '无'
                rep_dict['report_item'] = rep.report_item
                list_rep.append(rep_dict)

            rep_dict = rep.to_dict()
            if rep.sample_info_v:
                rep_dict['mg_id'] = rep.sample_info_v.sample_id
            else:
                rep_dict['mg_id'] = '无'
            rep_dict['report_item'] = rep.report_item
            all_rep.append(rep_dict)
        if 'admin' in [role.name for role in user.roles]:
            list_rep = all_rep
        rep_all = []
        for rep in Report.query.all():
            dic_rep = rep.to_dict()
            if rep.sample_info_v:
                dic_rep['mg_id'] = rep.sample_info_v.sample_id
            else:
                dic_rep['mg_id'] = '无'
            dic_rep['report_item'] = rep.report_item
            rep_all.append(dic_rep)
        dict_rep = {'sample': list_rep, 'all_rep': rep_all, 'total': len(Report.query.all())}
        # print(rep_all)
        return jsonify(dict_rep)

    def post(self):
        data = request.get_data()
        sams = (json.loads(data)['sams'])
        err = ''
        report = ''
        mmsg = ''
        user = '伞兵一号'
        for sam in sams:
            sample = sam.get('sample_name')
            print(sample)

        return {'msg': mmsg, 'err': '{}'.format(err)}


class RgmReportInfo(Resource):

    def get(self):
        """
            方法名称：获取制作PGM报告首页数据API接口
            方法描述：调用此API接口获取制作PGM报告首页数据
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: search
                  in: query
                  type: string
                  description: 搜索内容 - 默认为''

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
                    description: 获取信息成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                            example: {code: 200,message: "获取信息成功!",data: {"total": 0, "data": []}}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('search', type=str, default='', help='搜索内容')
        parser.add_argument('page', type=int, default=1, help='页码')
        parser.add_argument('page_size', type=int, default=10, help='每页数量')
        args = parser.parse_args()
        # 获取参数
        search = args.get('search')
        page = args.get('page')
        page_per = args.get('page_size')
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, 'message': '无访问权限!', "data": None}, 405

        # 获取分配给当前用户的任务 -- 等待出具的报告
        if 'admin' in [role.name for role in user.roles]:
            all_task = ReviewLib.query.all()
        else:
            all_task = ReviewLib.query.filter(
                and_(
                    ReviewLib.reporter == user.username,
                    or_(
                        ReviewLib.status == '等待出具',
                        ReviewLib.status == '出具中',
                        ReviewLib.status == '审核未通过'
                    ),
                    or_(
                        ReviewLib.pro_name.like('%10基因%'),
                        ReviewLib.pro_name.like('%12基因%'),
                        ReviewLib.pro_name.like('%13基因%'),
                        ReviewLib.pro_name.like('%25基因%'),
                        ReviewLib.pro_name.like('%52基因%'),
                        ReviewLib.pro_num.in_(('PN0001', 'PN0002', 'PN0003', 'PN0004', 'PN0005', 'PN0006', 'PN0015', 'PN0016'))
                    )
                )
            ).all()
        total = 0
        all_req = []
        if all_task:
            all_rep_mg = [task.req_mg for task in all_task]
            all_rep_mg_dict = {task.req_mg: {"mgid": task.mgid, "reporter": task.reporter,
                                             "review_info": task.review_info, "review_inside": task.review_inside, "resource": task.resource} for task in all_task}
            mgid_dict = {task.mgid: task.req_mg for task in all_task}
            # 获取申请单号
            apply_list = []
            if search != '':
                for key in mgid_dict.keys():
                    if re.search(r'%s' % (search), str(key)):  # 根据样本名模糊查询 -> 申请单号
                        apply_list.append(mgid_dict[key])
                all_report = Report.query.filter(Report.req_mg.in_(all_rep_mg)).filter(Report.req_mg.in_(apply_list)).order_by(
                    Report.id.desc()).paginate(page=page, per_page=page_per, error_out=False)
            else:
                all_report = Report.query.filter(Report.req_mg.in_(all_rep_mg)).order_by(
                    Report.id.desc()).paginate(page=page, per_page=page_per, error_out=False)

            total = all_report.total
            for req in all_report.items:
                req_dict = req.to_dict()
                req_dict['mg_id'] = all_rep_mg_dict[req.req_mg]["mgid"]
                req_dict['reporter'] = all_rep_mg_dict[req.req_mg]["reporter"]
                req_dict['review_inside'] = all_rep_mg_dict[req.req_mg]["review_inside"]  # 内审意见
                req_dict['review_info'] = all_rep_mg_dict[req.req_mg]["review_info"]  # 医学审核意见
                req_dict['report_item'] = req.report_item
                req_dict['resource'] = all_rep_mg_dict[req.req_mg]["resource"]
                all_req.append(req_dict)

        return {"code": 200, "message": "获取信息成功!", "data": {"total": total, "data": all_req}}, 200


class GetMutationList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')

    def get(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {'msg': '无访问权限'}, 401

        args = self.parser.parse_args()
        rep_id = args.get('id')
        dic_m = {}
        print(rep_id)
        report = Report.query.filter(Report.id == rep_id).first()
        if report.stage == '突变初审':
            sam = report.samples[0]
            list_m = []
            mutations = report.mutation
            if mutations:
                mutation = mutations.mutation

                first_check(mutation, list_m)
            dic_m['mutation'] = list_m
            dic_m['mg_id'] = sam.mg_id

        print(dic_m)
        return jsonify(dic_m)

    def post(self):
        data = request.get_data()
        sams = (json.loads(data)['sams'])
        for sam in sams:
            id = sam.get('id')
            Mutation.query.filter(Mutation.id == id).update({
                'status': '初审通过'
            })
            db.session.commit()
        return {'msg': '初审通过！'}

    def delete(self):
        data = request.get_data()
        sams = json.loads(data)['sams']
        for sam in sams:
            type = sam.get('type')
            id = sam.get('id')
            Mutation.query.filter(Mutation.id == id).update({
                'status': '初审未通过'
            })
            db.session.commit()
        return {'msg': '初审未通过！'}


class ReportStage(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')
        self.parser.add_argument('stage', type=str, help='当前步骤')

    def post(self):
        """
            方法名称：提交审核结果API接口
            方法描述：调用此API接口提交审核结果
            ---
            tags:
                - PGM报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                        - stage
                    properties:
                        id:
                            type: integer
                            description: 样本id
                        stage:
                            type: string
                            description: 报告状态  '生成报告'
            responses:
                200:
                    description: 提交成功!
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
                        example: {code: 200, message: "提交成功!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 200, "message": "无访问权限!", "data": None}, 200

        args = self.parser.parse_args()
        stage = args.get('stage')
        rep_id = args.get('id')
        stages = ['突变审核', '突变注释', '生成报告', '制作完成', '开始审核',
                  '初次审核', '再次审核', '审核完成', '开始发报', '发送完成', '报告完成']  # 报告步骤
        if stage in stages:
            report = Report.query.filter(Report.id == rep_id).update({
                'stage': stage
            })
            # print(stage)
            db.session.commit()
        if stage == '重新制作':
            report = Report.query.filter(Report.id == rep_id).first()
            if report:
                samples = report.samples
                mutations = report.mutation
                if mutations:
                    mutation = mutations.mutation
                    del_db(db, mutation)
                del_db(db, samples)
                del_db(db, mutations)
            del_db(db, report)
            db.session.commit()

        return {"code": 200, "message": "提交成功!", "data": None}, 200


class EditMutation(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')
        self.parser.add_argument('resource', type=str, default='', help='报告id')

    def get(self):
        """
            方法名称：突变审核获取变异信息信息API接口
            方法描述：调用此API接口获取样本变异信息
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: id
                  in: query
                  required: true
                  type: integer
                  description: 样本id

                - name: resource
                  in: query
                  type: integer
                  description: 数据来源

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
                        example: {code: 200,message: "获取信息成功!",data: {
                                mg_id: "MG2008172",
                                mu_title: [{align: "center", type: "selection", width: "60"}],
                                mutation: [
                                    {ID_v: "COSV54736340", cHGVS: "c.182A>G",
                                    chr_start_end: "chr1:115256529-115256529",
                                    depth: "3188.0",drugs: [],exon: "exon3",function_types: "missense_variant",gene: "NRAS",
                                    grade: "",hotspot: "YES",id: 5313,maf: "",mu_af: "0.5%",mu_type: "突变",okr_mu: "mutation",pHGVS_1: "p.Q61R",
                                    pHGVS_3: "p.Gln61Arg",status: "审核未通过",transcript: "NM_002524.4",type: "SNV"}
                                ]
                            }
                        }
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        rep_id = args.get('id')
        resource = args.get('resource')
        dic_m = {}
        # print(rep_id)
        report = Report.query.filter(Report.id == rep_id).first()
        if report.stage in ['突变审核', '突变注释', '生成报告', '制作完成']:  # todo 简化
            list_m = []
            mutations = report.mutation
            if mutations:
                mutation = mutations.mutation
                list_c = None  # todo 简化
                first_check(mutation, list_m, list_c)

            dic_m['mu_title'] = [{'type': 'selection', 'minWidth': 60, 'align': 'center'},
                                 {'title': '状态', 'minWidth': 100, 'key': 'status'},
                                 {'title': '变异类型', 'key': 'type', 'minWidth': 100},
                                 {'title': '基因', 'key': 'gene', 'minWidth': 100},
                                 {'title': '转录本', 'key': 'transcript', 'width': 100},
                                 {'title': '外显子', 'key': 'exon', 'minWidth': 100},
                                 {'title': '编码改变', 'key': 'cHGVS', 'minWidth': 100},
                                 {'title': '氨基酸改变', 'key': 'pHGVS_3', 'minWidth': 100},
                                 {'title': '氨基酸改变-简写', 'key': 'pHGVS_1', 'minWidth': 130},
                                 {'title': '基因座', 'key': 'chr_start_end', 'minWidth': 150},
                                 {'title': '功能影响', 'key': 'function_types', 'minWidth': 100},
                                 {'title': 'ID', 'key': 'ID_v', 'minWidth': 100},
                                 {'title': 'Hotspot', 'key': 'hotspot', 'minWidth': 100},
                                 {'title': '变异丰度', 'key': 'mu_af', 'minWidth': 100},
                                 {'title': '深度', 'key': 'depth', 'minWidth': 100},
                                 {'title': 'OKR注释类型', 'key': 'okr_mu', 'minWidth': 120},
                                 {'title': '报告类型', 'key': 'mu_type', 'minWidth': 100},
                                 {'title': '临床意义级别', 'slot': 'grade', 'minWidth': 120},
                                 {'title': '操作', 'slot': 'action', 'minWidth': 100}
                                 ]
            dic_m['mutation'] = list_m
            if str(resource) == 'lims':
                review = ReviewLib.query.filter(
                    and_(
                        ReviewLib.req_mg == report.req_mg,
                        ReviewLib.pro_name == report.report_item
                    )
                ).first()
                dic_m['mg_id'] = review.mgid
            else:
                sam = report.sample_info_v
                dic_m['mg_id'] = sam.sample_id

        return {"code": 200, "message": "获取样本变异信息成功!", "data": dic_m}, 200

    def post(self):
        """
            方法名称：突变审核API接口
            方法描述：调用此API接口突变审核
            ---
            tags:
                - PGM报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - sams
                        - mgid
                        - run_name
                        - report_item
                        - resource
                    properties:
                        sams:
                            type: string
                            description: 样本突变信息, json字符串
                        mgid:
                            type: string
                            description: 迈景编号
                        run_name:
                            type: string
                            description: 批次名
                        report_item:
                            type: string
                            description: 检测项目
                        resource:
                            type: string
                            description: 数据来源
            responses:
                200:
                    description: 审核通过!
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
                        example: {code: 200, message: "审核通过!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 401, "message": "无权限访问!", "data": None}, 401

        data = request.get_data()
        sams = (json.loads(data)['sams'])
        resource = (json.loads(data)['resource'])
        mgid = (json.loads(data)['mgid'])
        run_name = (json.loads(data)['run_name'])
        report_item = (json.loads(data)['report_item'])
        # print(resource, mgid, run_name, report_item)

        clinicInterpretation = ClinicInterpretation.query.all()
        okrs = OKR.query.all()
        list_md = []
        for okr in okrs:
            list_md.append(okr.to_dict())
        df_md = dict2df(list_md)

        drug_effect = {'indicated', 'contraindicated', 'resistance', 'not_recommended'}

        if isinstance(sams, dict):
            sams = [sams]

        for sam in sams:
            id = sam.get('id')
            type = sam.get('type')
            mutation = Mutation.query.filter(Mutation.id == id).first()
            mutation.status = '审核通过'
            mu = Mutation.query.filter(Mutation.id == id).first()

            # cancer = mu.mutation.report.sample_info_v.apply_info.cancer    # 获取癌种方式
            if str(resource) == 'lims':
                seq = SeqInfo.query.filter(
                    and_(
                        SeqInfo.sample_name == mgid,
                        SeqInfo.report_item == report_item
                    )
                ).first()
                cancer = seq.cancer if seq else ""
            else:
                cancer = mu.mutation.report.sample_info_v.apply_info.cancer  # 获取癌种方式

            dic_out = md_create(df_md, sam, cancer)
            grade = ''
            if dic_out:
                grades = [row.get('grade') for row in dic_out.values()]
                for i in ['II', 'I']:
                    if i in grades:
                        grade = i
                        break

            drugs = mutation.drug
            if drugs:
                del_db(db, drugs)
            if dic_out:
                drug = get_drug(dic_out)
                for row in drug:
                    okr_drug = OkrDrug(drug=row.get('drug'), level=row.get('level'), drug_effect=row.get('drug_effect'))
                    mutation.drug.append(okr_drug)
            mutation.grade = grade

            db.session.commit()
        return {"code": 200, "message": "审核通过!", "data": None}, 200

    def delete(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        data = request.get_data()
        sams = (json.loads(data)['sams'])
        id = sams.get('id')
        type = sams.get('type')
        Mutation.query.filter(Mutation.id == id).update({
            'status': '审核未通过',
        })
        db.session.commit()
        return {"code": 200, 'message': '审核未通过！', "data": None}, 200


class AnnotateMutation(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')
        self.parser.add_argument('cancer', type=str, help='癌症类型')

    def get(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        rep_id = args.get('id')
        dic_m = {}

        okrs = OKR.query.all()
        list_okr = []
        for okr in okrs:
            list_okr.append(okr.to_dict())
        df = dict2df(list_okr)
        print(df)
        cancers = set(df['disease'].values)
        dic_m['cancers'] = [{'value': v, 'label': v} for v in cancers]
        drug_effect = {'indicated', 'contraindicated', 'resistance', 'not_recommended'}

        report = Report.query.filter(Report.id == rep_id).first()
        if report.stage in ['突变审核', '突变注释', '生成报告', '制作完成']:
            sam = report.samples[0]
            patient = sam.patient_info
            cancer = sam.cancer
            list_m = []
            mutations = report.mutation
            if mutations:
                list_c = ['审核通过']
                mutation = mutations.mutation
                first_check(mutation, list_m, list_c)
            if cancer:
                for row in list_m:
                    grade = get_grade(row, df, cancer, drug_effect)
                    dic_out = okr_create_n(row, df, cancer, drug_effect)
                    if dic_out:
                        drug = get_drug(dic_out)
                        row['drug'] = drug
                    row['grade'] = grade

            dic_m['mutation'] = list_m
            dic_m['sample_info'] = sam.to_dict()
            dic_m['patient_info'] = patient.to_dict()
        # print(dic_m['cancers'])

        return jsonify(dic_m)

    def post(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        data = request.get_data()
        sams = (json.loads(data)['sams'])
        args = self.parser.parse_args()
        cancer = args.get('cancer')
        for sam in sams:
            id = sam.get('id')
            type = sam.get('type')
            mutation = Mutation.query.filter(Mutation.id == id).first()
            mutation.grade = sam.get('grade')
            drugs = mutation.drug
            if drugs:
                del_db(db, drugs)
            if sam.get('drug'):
                for row in sam.get('drug'):
                    okr_drug = OkrDrug(drug=row.get('drug'), level=row.get('level'), drug_effect=row.get('drug_effect'))
                    mutation.drug.append(okr_drug)
            db.session.commit()

        return {'msg': '注释保存成功'}

    def put(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        cancer = args.get('cancer')
        rep_id = args.get('id')
        report = Report.query.filter(Report.id == rep_id).first()
        sam = report.samples[0]
        sam.cancer = cancer
        disease_cancer = {'非小细胞肺癌': 'Non-Small Cell Lung Cancer'}
        db.session.commit()
        return {'msg': '添加完成'}


class DownloadOkr(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')
        self.parser.add_argument('item', type=str, help='检测项目')
        self.parser.add_argument('resource', type=str, default="", help='检测项目')

    def post(self):
        """
            方法名称：保存okr结果API接口
            方法描述：调用此API接口保存okr结果
            ---
            tags:
                - PGM报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                        - item
                        - resource
                    properties:
                        id:
                            type: string
                            description: 样本id
                        item:
                            type: string
                            description: 检测项目
                        resource:
                            type: string
                            description: 数据来源
            responses:
                200:
                    description: okr保存成功!
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
                        example: {code: 200, message: "okr保存成功!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        rep_id = args.get('id')
        item = args.get('item')
        resource = args.get('resource')
        if resource == "lims":
            code, message = self.download_okr_lims(rep_id, item)
        else:
            code, message = self.download_okr_local(rep_id, item)
        return {"code": code, "message": message, "data": None}, code

    def download_okr_local(self, rep_id, item):
        """ 兼容本地数据库老数据 """
        dir_pre = current_app.config['PRE_REPORT']
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')

        dir_pgm_remplate = os.path.join(dir_pre, 'template_config', 'template_pgm.json')
        config = read_json(dir_pgm_remplate, 'config')

        report = Report.query.filter(Report.id == rep_id).first()
        seq = report.sample_info_v.seq[0]
        sam = report.sample_info_v
        cancer = sam.apply_info.cancer
        mg_id = sam.sample_id
        req_mg = sam.apply_info.req_mg
        mutation = report.mutation
        dir_report_mg = os.path.join(dir_report, mg_id)
        list_mu = []
        for mu in mutation.mutation:
            if mu.status == '审核通过':
                if mu.grade in ['I']:
                    pass
                else:
                    list_mu.append(mu.to_dict())
        # print(list_mu)
        for cc in config:
            list_m = []
            if item == cc['item']:
                for row in cc['结果详情']:
                    gene = row['基因']
                    m_type = row['检测的变异类型']
                    if list_mu:
                        for mu in list_mu:
                            if (mu['gene'] == gene and mu['mu_type'] in m_type):
                                list_m.append(mu)
        # print(list_m)
        okr_auto = ''
        if report.auto_okr == 'No':
            okr_auto = 'auto'
        res_f = get_result_file(seq, '.OKR.vcf')
        # print(res_f)
        vcf_f = os.path.join(os.getcwd(), dir_report_mg, '{}.okr.vcf'.format(mg_id))

        okr_f = os.path.join(os.getcwd(), dir_report_mg, '{}{}.okr.tsv'.format(mg_id, okr_auto))
        if os.path.exists(okr_f):
            os.remove(okr_f)

        get_okr_vcf(res_f, list_m, vcf_f)
        create_reports_using_report_file(vcf_f, cancer, okr_f)

        # return {'msg': '{} okr已经保存'.format(mg_id)}
        # return {"code": 200, "message": "{} okr已经保存".format(mg_id), "data": None}, 200
        return 200, "{} okr已经保存".format(mg_id)

    def download_okr_lims(self, rep_id, item):
        """ lims数据 """
        dir_pre = current_app.config['PRE_REPORT']
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')

        dir_pgm_remplate = os.path.join(dir_pre, 'template_config', 'template_pgm.json')
        config = read_json(dir_pgm_remplate, 'config')

        report = Report.query.filter(Report.id == rep_id).first()
        # seq = report.sample_info_v.seq[0]  # 测序数据信息
        run = RunInfo.query.filter(RunInfo.name == report.run_name).first()
        seq = SeqInfo.query.filter(
            and_(
                SeqInfo.run_info_id == run.id,
                SeqInfo.sample_mg == report.req_mg,
                SeqInfo.report_item == report.report_item
            )
        ).first()
        mg_id = seq.sample_name
        # sam = report.sample_info_v  # 样本信息
        cancer_zh = seq.cancer
        # 转换成okr癌种
        cancer_t = CancerTypes.query.filter(CancerTypes.name == cancer_zh).first()
        if cancer_t:
            cancer = cancer_t.okr_name
        else:
            400, "{} 癌种类型不能识别".format(mg_id)
        # req_mg = sam.apply_info.req_mg
        mutation = report.mutation
        dir_report_mg = os.path.join(dir_report, mg_id)
        list_mu = []
        for mu in mutation.mutation:
            if mu.status == '审核通过':
                if mu.grade in ['I']:
                    pass
                else:
                    list_mu.append(mu.to_dict())
        for cc in config:
            list_m = []
            if item == cc['item']:
                for row in cc['结果详情']:
                    gene = row['基因']
                    m_type = row['检测的变异类型']
                    if list_mu:
                        for mu in list_mu:
                            if (mu['gene'] == gene) and (mu['mu_type'] in m_type):
                                list_m.append(mu)
        okr_auto = ''
        if report.auto_okr == 'No':
            okr_auto = 'auto'
        res_f = get_result_file(seq, '.OKR.vcf')
        vcf_f = os.path.join(os.getcwd(), dir_report_mg, '{}.okr.vcf'.format(mg_id))

        okr_f = os.path.join(os.getcwd(), dir_report_mg, '{}{}.okr.tsv'.format(mg_id, okr_auto))
        if os.path.exists(okr_f):
            os.remove(okr_f)

        get_okr_vcf(res_f, list_m, vcf_f)
        create_reports_using_report_file(vcf_f, cancer, okr_f)
        return 200, "{} okr已经保存".format(mg_id)


class AnnotateCheck(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')

    def get(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        rep_id = args.get('id')
        dic_m = {}
        print(rep_id)
        report = Report.query.filter(Report.id == rep_id).first()
        if report.stage in ['突变审核', '突变注释', '生成报告', '制作完成']:
            sam = report.samples[0]
            patient = sam.patient_info
            list_m = []
            mutations = report.mutation
            if mutations:
                list_c = ['二审通过']
                mutation = mutations.mutation
                first_check(mutation, list_m, list_c)

            dic_m['mutation'] = list_m
            dic_m['sample_info'] = sam.to_dict()
            dic_m['patient_info'] = patient.to_dict()
        # print(dic_m)

        return jsonify(dic_m)


class ExportReport(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='报告id')
        self.parser.add_argument('item', type=str, help='报告模板')
        self.parser.add_argument('note', type=str, help='下载okr')
        self.parser.add_argument('hospital', type=str, help='医院')
        self.parser.add_argument('resource', type=str, default='', help='医院')

    def post(self):
        """
            方法名称：生成报告API接口
            方法描述：调用此API接口生成报告
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: id
                  in: query
                  type: integer
                  description: 样本id

                - name: item
                  in: query
                  type: string
                  description: 检测项目

                - name: note
                  in: query
                  type: string
                  description: 是否使用上传okr 0 或者 1(auto)

                - name: hospital
                  in: query
                  type: string
                  description: 是否使用上传okr

                - name: resource
                  in: query
                  type: string
                  description: 数据来源

            responses:
                200:
                    description: 申请单号 xxx 迈景编号 xxx 报告生成成功! 或者 申请单号 xxx 迈景编号 xxx 突变未审核!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                            example: {code: 200, message: "申请单号 xxx 迈景编号 xxx 报告生成成功!", data: None}
        """

        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        # 获取参数
        args = self.parser.parse_args()
        rep_id = args.get('id')
        item = args.get('item')
        note = args.get('note')
        hospital = args.get('hospital')
        resource = args.get('resource')
        if str(resource) == "lims":
            code, message, data = self.export_report_lims(rep_id, item, note, hospital)
        else:
            code, message, data = self.export_report_local(rep_id, item, note, hospital)
        return {"code": code, "message": message, "data": data}

    def export_report_local(self, rep_id, item, note, hospital):
        """ 兼容本地数据库老数据 """
        dir_pre = current_app.config['PRE_REPORT']
        path_docx = os.path.join(dir_pre, 'template_docx')
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')
        review_dir = os.path.join(dir_res, 'Review_Results')  # 报告审核后的上传目录
        if not os.path.exists(dir_report):
            os.mkdir(dir_report)

        if not os.path.exists(review_dir):
            os.mkdir(review_dir)

        dir_pgm_remplate = os.path.join(dir_pre, 'template_config', 'template_pgm.json')
        config = read_json(dir_pgm_remplate, 'config')
        gene_card = read_json(dir_pgm_remplate, 'gene_card')
        transcript = read_json(dir_pgm_remplate, 'transcript')
        dict_items = {'card': ['10', '12', '13', '25'], 'no_card': ['52']}

        # 转录本字典
        dic_transcript = {}
        for row in transcript:
            dic_transcript[row['gene']] = row['transcript']

        if note == '1':
            okr_auto = 'auto'
        else:
            okr_auto = ''
        dic_mu = {'CNV': '拷贝数变异'}
        dic_m = {}
        report = Report.query.filter(Report.id == rep_id).first()
        sam = report.sample_info_v
        mg_id = sam.sample_id
        req_mg = sam.apply_info.req_mg
        list_m = []
        # okr
        dir_report_mg = os.path.join(dir_report, mg_id)
        if not os.path.exists(dir_report_mg):
            os.mkdir(dir_report_mg)
        okr_f = os.path.join(os.getcwd(), dir_report_mg, '{}{}.okr.tsv'.format(mg_id, okr_auto))
        okr = is_okr(okr_f, '样品中未发现相关生物标记物')
        if okr:
            all = fileokr_to_dict(okr_f)
            mutation = set()
            dic_m = all.get('相关生物标记物')
            list_okr = []
            if dic_m:
                dic_mu = dic_m.get('相关生物标记物')
                if dic_mu:
                    for row in dic_mu:
                        mutation.add(row.get('基因组改变'))

            def get_summary(dic_in, key, mutation):
                list_okr = []
                if dic_in:
                    dic_okr = dic_in.get(key)
                    if dic_okr:
                        if mutation:
                            for mu in mutation:
                                list_mu = []
                                for row in dic_okr:
                                    if mu == row.get('基因组改变'):
                                        list_mu.append(row)
                                list_okr.append({'mutation': mu, 'okr': list_mu})
                return list_okr

            def get_okr(dic_in, key, mutation):
                list_okr = []
                if dic_in:
                    dic_okr = dic_in.get(key)
                    if dic_okr:
                        if mutation:
                            for mu in mutation:
                                list_mu = []
                                for row in dic_okr.get('therapy'):
                                    if mu == row.get('基因组改变'):
                                        list_mu.append(row)
                                if list_mu:
                                    list_okr.append({'mutation': mu, 'okr': list_mu})
                return list_okr

            dic_therapy = all.get('相关疗法详情')
            dic_sign = get_summary(dic_m, '相关生物标记物', mutation)
            dic_summary = get_summary(all.get('基因变异相应靶向治疗方案'), '基因变异相应靶向治疗方案', mutation)
            dic_fda = get_okr(dic_therapy, '目前来自FDA 靶向药物信息', mutation)
            dic_clincal = get_okr(dic_therapy, '目前来自临床试验靶向药物信息', mutation)
            dic_nccn = get_okr(dic_therapy, '目前来自NCCN 靶向药物信息', mutation)
            dic_render = {'okr_clincal': dic_clincal, 'okr_fda': dic_fda, 'okr_sign':
                dic_sign, 'okr_summary': dic_summary, 'okr_nccn': dic_nccn}
            dic_m.update(dic_render)
            dic_m['okr'] = 1
        else:
            dic_m['okr'] = 0

        if report.stage in ['生成报告', '制作完成']:  # todo 简化
            apply = sam.apply_info
            patient = apply.patient_info_v
            mutations = report.mutation
            family = patient.family_infos
            if family:
                fam = ''
                for fa in family:
                    fam_dic = fa.to_dict()
                    fam += '{}{}'.format(fam_dic['relationship'], fam_dic['diseases'])
                dic_m['fm'] = fam
            treats = patient.treat_infos
            mdhistory = []
            if treats:
                for treat in treats:
                    mdhistory.append(treat.name)
                mdhistory = [m for m in mdhistory if m]
            if mdhistory:
                mdhistory = '、'.join(mdhistory)
            else:
                mdhistory = ''
            dic_m['mdhistory'] = mdhistory

            if mutations:
                mutation = mutations.mutation
                list_c = ['审核通过']  # todo 简化
                first_check(mutation, list_m, list_c)

            dic_m['s'] = sam.to_dict()  # 样本信息
            dic_m['ap'] = sam.apply_info.to_dict()
            dic_m['ap']['cancer'] = sam.seq[0].cancer
            # dic_m['sp'] = sam.pathology_info.to_dict()  # 病理信息
            dic_m['p'] = patient.to_dict()  # 病人信息
            # print([k.sample_name for k in sam.seq])
            cell_p = sam.pathology_info.cell_content
            # print(cell_p)
            try:
                cell_p = float(cell_p)
                if cell_p < 1:
                    cell_p = format(cell_p, '.0%')
                else:
                    cell_p = format(cell_p / 100, '.0%')
            except:
                pass
            # print(cell_p)
            dic_m['cell_content'] = cell_p
            dic_m['date'] = set_time_now()
            list_card = []

            for cc in config:
                if item == cc['item']:
                    rep_item = get_rep_item(cc['item'])
                    # print(rep_item)
                    # print(cc['基因检测范围'])

                    dic_m['c'] = {'item': rep_item, '检测内容': cc['检测内容'],
                                  '检测方法': cc['检测方法'], '检测内容前言': cc['检测内容前言'],
                                  '基因检测范围': cc['基因检测范围'].split('\n')}  # 报告配置文件
                    list_mutation = []
                    detail_mu = []
                    list_trans = []
                    for row in cc['结果详情']:
                        gene = row['基因']
                        list_trans.append(row)

                        if rep_item in dict_items.get('card'):
                            for card in gene_card:
                                if gene == card['基因']:
                                    list_card.append(card)

                        dic_m['gene_card'] = list_card  # gene card
                        r_mutation = []
                        m_type = row['检测的变异类型']
                        if list_m:
                            for mu in list_m:
                                if mu['mu_type'] == '融合':
                                    mu['gene'] = mu['gene'].split('-')[-1]
                                if mu['okr_mu'] == 'exon 14 skipping' and 'MET' in mu['gene']:
                                    mu['gene'] = 'MET'
                                if mu['okr_mu'] == 'vIII' and 'EGFR' in mu['gene']:
                                    mu['gene'] = 'EGFR'
                                if mu['gene'] == gene and mu['mu_type'] in m_type:

                                    if mu['mu_type'] == '融合':
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} fusion'.format(mu['gene'])
                                    elif mu['mu_type'] == '拷贝数变异':
                                        mu['mu_name'] = '{}({})x{}'.format(mu['ID_v'],
                                                                           mu['chr_start_end'].split(':')[-1],
                                                                           mu['mu_af'].split('/')[0])
                                        mu['mu_name_usual'] = '{} amplification'.format(mu['gene'])
                                    elif mu['okr_mu'] == 'exon 14 skipping' and 'MET' in mu['gene']:
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} exon 14 skipping'.format(mu['gene'])
                                    elif mu['okr_mu'] == 'vIII' and 'EGFR' in mu['gene']:
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} vIII'.format(mu['gene'])
                                    else:
                                        mu['mu_name'] = '{0}({1}):{2} ({3})'.format(mu['transcript'], mu['gene'],
                                                                                    mu['cHGVS'], mu['pHGVS_3'])
                                        if mu['okr_mu'] == 'mutation':
                                            mu['mu_name_usual'] = '{} {}'.format(mu['gene'],
                                                                                 mu['pHGVS_1'].split('.')[-1])
                                        else:
                                            mu['mu_name_usual'] = '{} {}'.format(mu['gene'], mu['okr_mu'])

                                    drugs = []
                                    # print(dic_m['okr'].items())
                                    # print(111,dic_m.get('okr_summary'))
                                    if dic_m.get('okr_summary'):
                                        list_drug = get_clincl(dic_m['okr_summary'])
                                        for row in list_drug:
                                            if mu['mu_name_usual'] in row['mutation']:
                                                mu['drugs'] = row['okr']
                                                mu['grade'] = 'II'
                                    if mu['exon'] and 'exon' in mu['exon']:
                                        mu['exon_n'] = mu['exon'].strip(
                                            'exon')  # re.match('([A-Za-z]+)(\d+)', mu['exon']).group(2)
                                    if mu['drugs']:
                                        for drug in mu['drugs']:
                                            drugs.append('{}({}:{})'.format(drug.get('drug'),
                                                                            drug.get('drug_effect'), drug.get('level')))
                                    else:
                                        drugs = ['暂无']
                                        mu['grade'] = 'III'

                                    mu['okrs'] = drugs
                                    mu['grade_z'] = f"{mu['grade']}类变异"
                                    mu['type_z'] = dic_mu_type.get(mu['function_types'])
                                    if mu['mu_type'] == '融合':
                                        mu['mu_name_z'] = mu['exon']
                                        mu['type_z'] = '基因融合'

                                    elif mu['mu_type'] == '拷贝数变异':
                                        mu['mu_name_z'] = mu['mu_name']
                                        mu['type_z'] = '基因扩增'
                                    elif mu['mu_type'] == '缺失':
                                        mu['type_z'] = '缺失突变'
                                        mu[
                                            'mu_name_z'] = f"{mu['transcript']}({mu['gene']}):{mu['cHGVS']} ({mu['pHGVS_1']})"

                                    else:
                                        mu[
                                            'mu_name_z'] = f"{mu['transcript']}({mu['gene']}):{mu['cHGVS']} ({mu['pHGVS_1']})"

                                    mu['mu_af_z'] = f"{mu['mu_af']}条序列" if (not '/' in mu['mu_af']) and (
                                        not '%' in mu['mu_af']) else mu['mu_af']
                                    # if mu['okrs'] != '暂无':
                                    #     print(mu['okrs'])

                                    drug_z = [f"{row['level']}期的{row['drug']}" for row in mu['drugs']] if mu[
                                                                                                              'drugs'] != '暂无' else []
                                    mu['zsy_okr'] = f"{mu['gene']}目前在{dic_m['ap']['cancer']}" \
                                                    f"中对应的临床试验靶向治疗药物有:{'、'.join(drug_z)}" if mu['grade'] in ['II',
                                                                                                             'III'] else ''

                                    list_mutation.append(mu)
                                    # print(mu)

                                    # mu['']

                                    row_ir = {'result': mu['mu_name'], 'mu_af': mu['mu_af'],
                                              'mu_name_usual': mu['mu_name_usual'], 'grade': mu['grade']}

                                    r_mutation.append(row_ir)
                            if r_mutation:
                                pass
                            else:
                                r_mutation = [{'result': '未检出', 'mu_af': '',
                                               'mu_name_usual': '', 'grade': ''}]
                            rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                            detail_mu.append(rep_mutation)
                        else:
                            list_mutation = []
                            r_mutation = [{'result': '未检出', 'mu_af': '',
                                           'mu_name_usual': '', 'grade': ''}]
                            rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                            detail_mu.append(rep_mutation)
                    list_mutation_sort = []
                    for grade in ['I', 'II', 'III']:
                        for mu in list_mutation:
                            if mu['grade'] == grade:
                                list_mutation_sort.append(mu)
                    dic_m['mutation'] = list_mutation_sort  # 突变信息
                    dic_m['detail_mu'] = detail_mu  # 突变详情
                    dic_m['transcript'] = list_trans
                    # dic_m['list_m'] = list_m

            # print(dic_m.keys())

            if not os.path.exists(dir_report_mg):
                os.mkdir(dir_report_mg)

            if hospital == 'zsy':
                if list_card:
                    temp_docx = os.path.join(path_docx, 'zsy.docx')
                else:
                    temp_docx = os.path.join(path_docx, 'zsy_52.docx')
                dic_m['zsy'] = dic_zsy_introduce.get(get_rep_item(item))
                file = os.path.join(dir_report_mg,
                                    f"{(set_time_now()).replace('.', '')}-{dic_m['p']['name']}-{req_mg}-{get_rep_item(item)}.docx")
            else:
                if hospital == 'mg':
                    if list_card:
                        temp_docx = os.path.join(path_docx, 'pgm.docx')
                    else:
                        temp_docx = os.path.join(path_docx, 'pgm_52.docx')
                    file = os.path.join(dir_report_mg,
                                        '{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))
                if hospital == 'nk':
                    if list_card:
                        temp_docx = os.path.join(path_docx, 'nk.docx')
                    else:
                        temp_docx = os.path.join(path_docx, 'nk_52.docx')
                    file = os.path.join(dir_report_mg,
                                        '{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))

            # file_pdf = os.path.join(dir_report_mg, '{}_{}.pdf'.format(mg_id, item))
            if os.path.exists(file):
                os.remove(file)

            docx = DocxTemplate(temp_docx)
            docx.render(dic_m)

            docx.save(file)

            # 是否齐鲁医院
            if dic_m['ap']['hosptial'] == '山东大学齐鲁医院':
                temp_docx2 = os.path.join(path_docx, 'ql.docx')
                doc2 = DocxTemplate(temp_docx2)
                doc2.render(dic_m)
                file2 = os.path.join(dir_report_mg,
                                     'ql_{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))
                doc2.save(file2)

            report.stage = '制作完成'
            db.session.commit()

            # 修改报告审核状态状态
            review_report = ReviewLib.query.filter(ReviewLib.req_mg == req_mg).first()
            msg = '申请单号为: {} 迈景编号为：{} 的报告成功生成'.format(req_mg, mg_id)
        else:
            msg = '申请单号为: {} 迈景编号为：{} 的报告变异未审核，请审核'.format(req_mg, mg_id)

        # return {"code": 200, "message": msg, "data": {"stage": report.stage}}, 200
        return 200, msg, {"stage": report.stage}

    def export_report_lims(self, rep_id, item, note, hospital):
        """ 兼容本地数据库老数据 """
        dir_pre = current_app.config['PRE_REPORT']
        path_docx = os.path.join(dir_pre, 'template_docx')
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')
        review_dir = os.path.join(dir_res, 'Review_Results')  # 报告审核后的上传目录
        if not os.path.exists(dir_report):
            os.mkdir(dir_report)

        if not os.path.exists(review_dir):
            os.mkdir(review_dir)

        dir_pgm_remplate = os.path.join(dir_pre, 'template_config', 'template_pgm_lims.json')
        config = read_json(dir_pgm_remplate, 'config')
        gene_card = read_json(dir_pgm_remplate, 'gene_card')
        transcript = read_json(dir_pgm_remplate, 'transcript')
        dict_items = {'card': ['10', '12', '13', '25'], 'no_card': ['52']}

        # 转录本字典
        dic_transcript = {}
        for row in transcript:
            dic_transcript[row['gene']] = row['transcript']

        if note == '1':
            okr_auto = 'auto'
        else:
            okr_auto = ''
        dic_mu = {'CNV': '拷贝数变异'}
        dic_m = {}
        report = Report.query.filter(Report.id == rep_id).first()
        # 获取 mg_id req_mg
        run = RunInfo.query.filter(RunInfo.name == report.run_name).first()
        seq = SeqInfo.query.filter(
            and_(
                SeqInfo.run_info_id == run.id,
                SeqInfo.sample_mg == report.req_mg,
                SeqInfo.report_item == report.report_item
            )
        ).first()
        mg_id = seq.sample_name
        req_mg = seq.sample_mg
        cancer = seq.cancer
        #############################
        list_m = []
        # okr
        dir_report_mg = os.path.join(dir_report, mg_id)
        if not os.path.exists(dir_report_mg):
            os.mkdir(dir_report_mg)
        okr_f = os.path.join(os.getcwd(), dir_report_mg, '{}{}.okr.tsv'.format(mg_id, okr_auto))
        okr = is_okr(okr_f, '样品中未发现相关生物标记物')
        if okr:
            all = fileokr_to_dict(okr_f)
            mutation = set()
            dic_m = all.get('相关生物标记物')
            list_okr = []
            if dic_m:
                dic_mu = dic_m.get('相关生物标记物')
                if dic_mu:
                    for row in dic_mu:
                        mutation.add(row.get('基因组改变'))

            def get_summary(dic_in, key, mutation):
                list_okr = []
                if dic_in:
                    dic_okr = dic_in.get(key)
                    if dic_okr:
                        if mutation:
                            for mu in mutation:
                                list_mu = []
                                for row in dic_okr:
                                    if mu == row.get('基因组改变'):
                                        list_mu.append(row)
                                list_okr.append({'mutation': mu, 'okr': list_mu})
                return list_okr

            def get_okr(dic_in, key, mutation):
                list_okr = []
                if dic_in:
                    dic_okr = dic_in.get(key)
                    if dic_okr:
                        if mutation:
                            for mu in mutation:
                                list_mu = []
                                for row in dic_okr.get('therapy'):
                                    if mu == row.get('基因组改变'):
                                        list_mu.append(row)
                                if list_mu:
                                    list_okr.append({'mutation': mu, 'okr': list_mu})
                return list_okr

            dic_therapy = all.get('相关疗法详情')
            dic_sign = get_summary(dic_m, '相关生物标记物', mutation)
            dic_summary = get_summary(all.get('基因变异相应靶向治疗方案'), '基因变异相应靶向治疗方案', mutation)
            dic_fda = get_okr(dic_therapy, '目前来自FDA 靶向药物信息', mutation)
            dic_clincal = get_okr(dic_therapy, '目前来自临床试验靶向药物信息', mutation)
            dic_nccn = get_okr(dic_therapy, '目前来自NCCN 靶向药物信息', mutation)
            dic_render = {'okr_clincal': dic_clincal, 'okr_fda': dic_fda, 'okr_sign':
                dic_sign, 'okr_summary': dic_summary, 'okr_nccn': dic_nccn}
            dic_m.update(dic_render)
            dic_m['okr'] = 1
        else:
            dic_m['okr'] = 0

        if report.stage in ['生成报告', '制作完成']:  # todo 简化
            # sam = report.sample_info_v
            # apply = sam.apply_info
            # patient = apply.patient_info_v   # 病人信息
            mutations = report.mutation
            # family = patient.family_infos   # 家族史信息
            # if family:
            #     fam = ''
            #     for fa in family:
            #         fam_dic = fa.to_dict()
            #         fam += '{}{}'.format(fam_dic['relationship'], fam_dic['diseases'])
            #     dic_m['fm'] = fam
            # treats = patient.treat_infos   # 病人治疗信息
            # mdhistory = []
            # if treats:
            #     for treat in treats:
            #         mdhistory.append(treat.name)
            #     mdhistory = [m for m in mdhistory if m]
            # if mdhistory:
            #     mdhistory = '、'.join(mdhistory)
            # else:
            #     mdhistory = ''
            # dic_m['mdhistory'] = mdhistory

            if mutations:
                mutation = mutations.mutation
                list_c = ['审核通过']  # todo 简化
                first_check(mutation, list_m, list_c)
            # 从lims获取样本信息
            lims = LimsApi()
            sam_infos = lims.get_sample_info_v(mg_id, req_mg)  # 参数: 样本编号 订单号
            print(sam_infos)
            dic_m['fm'] = ""  # 家族史信息
            dic_m['mdhistory'] = ""  # 药物治疗史信息
            # dic_m['s'] = sam.to_dict()  # 样本信息
            dic_m['s'] = sam_infos['s']

            # dic_m['ap'] = sam.apply_info.to_dict()  # 申请单信息
            dic_m['ap'] = sam_infos['ap']

            dic_m['ap']['cancer'] = cancer  # 癌种
            # dic_m['p'] = patient.to_dict()  # 病人信息
            dic_m['p'] = sam_infos['p']

            cell_p = seq.cell_percent if seq.cell_percent else ''   # 细胞含量
            try:
                cell_p = float(cell_p)
                if cell_p < 1:
                    cell_p = format(cell_p, '.0%')
                else:
                    cell_p = format(cell_p / 100, '.0%')
            except:
                pass
            dic_m['cell_content'] = cell_p
            dic_m['date'] = set_time_now()
            list_card = []

            for cc in config:
                if item == cc['item']:
                    rep_item = get_rep_item(cc['item'])

                    dic_m['c'] = {'item': rep_item, '检测内容': cc['检测内容'],
                                  '检测方法': cc['检测方法'], '检测内容前言': cc['检测内容前言'],
                                  '基因检测范围': cc['基因检测范围'].split('\n')}  # 报告配置文件
                    list_mutation = []
                    detail_mu = []
                    list_trans = []
                    for row in cc['结果详情']:
                        gene = row['基因']
                        list_trans.append(row)

                        if rep_item in dict_items.get('card'):
                            for card in gene_card:
                                if gene == card['基因']:
                                    list_card.append(card)

                        dic_m['gene_card'] = list_card  # gene card
                        r_mutation = []
                        m_type = row['检测的变异类型']
                        if list_m:
                            for mu in list_m:
                                if mu['mu_type'] == '融合':
                                    mu['gene'] = mu['gene'].split('-')[-1]
                                if mu['okr_mu'] == 'exon 14 skipping' and 'MET' in mu['gene']:
                                    mu['gene'] = 'MET'
                                if mu['okr_mu'] == 'vIII' and 'EGFR' in mu['gene']:
                                    mu['gene'] = 'EGFR'
                                if mu['gene'] == gene and mu['mu_type'] in m_type:

                                    if mu['mu_type'] == '融合':
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} fusion'.format(mu['gene'])
                                    elif mu['mu_type'] == '拷贝数变异':
                                        mu['mu_name'] = '{}({})x{}'.format(mu['ID_v'],
                                                                           mu['chr_start_end'].split(':')[-1],
                                                                           mu['mu_af'].split('/')[0])
                                        mu['mu_name_usual'] = '{} amplification'.format(mu['gene'])
                                    elif mu['okr_mu'] == 'exon 14 skipping' and 'MET' in mu['gene']:
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} exon 14 skipping'.format(mu['gene'])
                                    elif mu['okr_mu'] == 'vIII' and 'EGFR' in mu['gene']:
                                        mu['mu_name'] = '{0} {1}'.format(mu['chr_start_end'], mu['exon'])
                                        mu['mu_name_usual'] = '{} vIII'.format(mu['gene'])
                                    else:
                                        mu['mu_name'] = '{0}({1}):{2} ({3})'.format(mu['transcript'], mu['gene'],
                                                                                    mu['cHGVS'], mu['pHGVS_3'])
                                        if mu['okr_mu'] == 'mutation':
                                            mu['mu_name_usual'] = '{} {}'.format(mu['gene'],
                                                                                 mu['pHGVS_1'].split('.')[-1])
                                        else:
                                            mu['mu_name_usual'] = '{} {}'.format(mu['gene'], mu['okr_mu'])

                                    drugs = []
                                    if dic_m.get('okr_summary'):
                                        list_drug = get_clincl(dic_m['okr_summary'])
                                        for row in list_drug:
                                            if mu['mu_name_usual'] in row['mutation']:
                                                mu['drugs'] = row['okr']
                                                mu['grade'] = 'II'
                                    if mu['exon'] and 'exon' in mu['exon']:
                                        mu['exon_n'] = mu['exon'].strip(
                                            'exon')  # re.match('([A-Za-z]+)(\d+)', mu['exon']).group(2)
                                    if mu['drugs']:
                                        for drug in mu['drugs']:
                                            drugs.append('{}({}:{})'.format(drug.get('drug'),
                                                                            drug.get('drug_effect'), drug.get('level')))
                                    else:
                                        drugs = ['暂无']
                                        mu['grade'] = 'III'

                                    mu['okrs'] = drugs
                                    mu['grade_z'] = f"{mu['grade']}类变异"
                                    mu['type_z'] = dic_mu_type.get(mu['function_types'])
                                    if mu['mu_type'] == '融合':
                                        mu['mu_name_z'] = mu['exon']
                                        mu['type_z'] = '基因融合'

                                    elif mu['mu_type'] == '拷贝数变异':
                                        mu['mu_name_z'] = mu['mu_name']
                                        mu['type_z'] = '基因扩增'
                                    elif mu['mu_type'] == '缺失':
                                        mu['type_z'] = '缺失突变'
                                        mu[
                                            'mu_name_z'] = f"{mu['transcript']}({mu['gene']}):{mu['cHGVS']} ({mu['pHGVS_1']})"

                                    else:
                                        mu[
                                            'mu_name_z'] = f"{mu['transcript']}({mu['gene']}):{mu['cHGVS']} ({mu['pHGVS_1']})"

                                    mu['mu_af_z'] = f"{mu['mu_af']}条序列" if (not '/' in mu['mu_af']) and (
                                        not '%' in mu['mu_af']) else mu['mu_af']

                                    drug_z = [f"{row['level']}期的{row['drug']}" for row in mu['drugs']] if mu[
                                                                                                              'drugs'] != '暂无' else []
                                    mu['zsy_okr'] = f"{mu['gene']}目前在{dic_m['ap']['cancer']}" \
                                                    f"中对应的临床试验靶向治疗药物有:{'、'.join(drug_z)}" if mu['grade'] in ['II',
                                                                                                             'III'] else ''
                                    list_mutation.append(mu)
                                    row_ir = {'result': mu['mu_name'], 'mu_af': mu['mu_af'],
                                              'mu_name_usual': mu['mu_name_usual'], 'grade': mu['grade']}
                                    r_mutation.append(row_ir)
                            if r_mutation:
                                pass
                            else:
                                r_mutation = [{'result': '未检出', 'mu_af': '',
                                               'mu_name_usual': '', 'grade': ''}]
                            rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                            detail_mu.append(rep_mutation)
                        else:
                            list_mutation = []
                            r_mutation = [{'result': '未检出', 'mu_af': '',
                                           'mu_name_usual': '', 'grade': ''}]
                            rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                            detail_mu.append(rep_mutation)
                    list_mutation_sort = []
                    for grade in ['I', 'II', 'III']:
                        for mu in list_mutation:
                            if mu['grade'] == grade:
                                list_mutation_sort.append(mu)
                    dic_m['mutation'] = list_mutation_sort  # 突变信息
                    dic_m['detail_mu'] = detail_mu  # 突变详情
                    dic_m['transcript'] = list_trans

            if not os.path.exists(dir_report_mg):
                os.mkdir(dir_report_mg)

            if hospital == 'zsy':
                if list_card:
                    temp_docx = os.path.join(path_docx, 'zsy.docx')
                else:
                    temp_docx = os.path.join(path_docx, 'zsy_52.docx')
                dic_m['zsy'] = dic_zsy_introduce.get(get_rep_item(item))
                file = os.path.join(dir_report_mg,
                                    f"{(set_time_now()).replace('.', '')}-{dic_m['p']['name']}-{req_mg}-{get_rep_item(item)}.docx")
            else:
                if hospital == 'mg':
                    if list_card:
                        temp_docx = os.path.join(path_docx, 'pgm.docx')
                    else:
                        temp_docx = os.path.join(path_docx, 'pgm_52.docx')
                    file = os.path.join(dir_report_mg,
                                        '{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))
                if hospital == 'nk':
                    if list_card:
                        temp_docx = os.path.join(path_docx, 'nk.docx')
                    else:
                        temp_docx = os.path.join(path_docx, 'nk_52.docx')
                    file = os.path.join(dir_report_mg,
                                        '{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))
            if os.path.exists(file):
                os.remove(file)
            docx = DocxTemplate(temp_docx)
            docx.render(dic_m)
            docx.save(file)

            # 是否齐鲁医院
            if dic_m['ap']['hosptial'] == '山东大学齐鲁医院':
                temp_docx2 = os.path.join(path_docx, 'ql.docx')
                doc2 = DocxTemplate(temp_docx2)
                doc2.render(dic_m)
                file2 = os.path.join(dir_report_mg,
                                     'ql_{}-{}-{}.docx'.format(dic_m['p']['name'], req_mg, get_rep_item(item)))
                doc2.save(file2)

            report.stage = '制作完成'
            db.session.commit()
            msg = '申请单号为: {} 迈景编号为：{} 的报告成功生成'.format(req_mg, mg_id)
        else:
            msg = '申请单号为: {} 迈景编号为：{} 的报告变异未审核，请审核'.format(req_mg, mg_id)

        return 200, msg, {"stage": report.stage}


class DocxName(Resource):
    """ 待编辑的文件名 """
    def get(self):
        """
            方法名称：在线编辑office获取样本信息API接口
            方法描述：调用此API接口 - 在线编辑office获取样本信息
            ---
            tags:
                - PGM报告相关API接口
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
                        example: {code: 200,message: "获取身份信息成功!",data: {"id": 5053, 'docx_file': 'xxx.docx', 'mg_id': 'MG111223'}}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=int, help='报告id')
        args = parser.parse_args()

        # 获取参数
        report_id = args.get('id')
        report = Report.query.get(report_id)

        # 审核结果
        review = ReviewLib.query.filter(
            and_(
                ReviewLib.req_mg == report.req_mg,
                ReviewLib.pro_name == report.report_item
            )
        ).first()
        # print(report.req_mg, report.report_item)
        # print(review)
        if review:
            review_id = review.id

            # docx文档
            dir_res = current_app.config['RES_REPORT']
            dir_report = os.path.join(dir_res, 'report')
            dir_report_mg = os.path.join(dir_report, str(review.mgid))
            if os.path.isdir(dir_report_mg):
                for root, dirs, files in os.walk(dir_report_mg, topdown=True):
                    for file_name in files:
                        if re.search(r'.docx$', file_name):
                            return {"code": 200, "message": "信息获取成功!", "data": {"id": review_id, 'docx_file': file_name, 'mg_id': review.mgid}}, 200
                return {"code": 404, "message": "迈景编号: {} 报告未找到!".format(review.mgid)}, 404
            else:
                return {"code": 404, "message": "迈景编号: {} 报告目录未找到!".format(review.mgid)}, 404
        else:
            return {"code": 404, "message": "申请单号: {} 报告信息未找到!".format(report.req_mg)}, 404


class SubmitReview(Resource):
    """ 报告制作完成后提交内审 """
    def post(self):
        """
            方法名称：PGM报告提交审核API接口
            方法描述：调用此API接口提交PGM报告审核
            ---
            tags:
                - PGM报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                        - resource
                    properties:
                        id:
                            type: integer
                            description: 报告id
                        resource:
                            type: string
                            description: 数据来源, 是否来源lims系统
            responses:
                200:
                    description: 提交报告审核成功!
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
                        example: {code: 200, message: "xxx成功!", data: null}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=int, help='报告id')
        parser.add_argument('resource', type=str, default="", help='数据来源')
        args = parser.parse_args()

        # 获取参数
        report_id = args.get('id')
        resource = args.get('resource')
        report = Report.query.get(report_id)
        if report.stage != "制作完成":
            return {"code": 400, "message": "当前状态:{}, 报告未制作完成,不能提交内审!"}, 400
        if resource == "lims" and report.is_send_lims != "已推送":
            return {"code": 400, "message": "生信和质控结果未推送lims系统, 请先推送lims系统!"}, 400
        # 审核结果
        review = ReviewLib.query.filter(
            and_(
                ReviewLib.req_mg == report.req_mg,
                ReviewLib.pro_name == report.report_item
            )
        ).first()
        if review:
            # 报告制作成功: 上传文件到审核目录, 并压缩
            try:
                dir_res = current_app.config['RES_REPORT']
                dir_report = os.path.join(dir_res, 'report')
                review_dir = os.path.join(dir_res, 'Review_Results')  # 报告审核后的上传目录
                mg_id = review.mgid
                dir_report_mg = os.path.join(dir_report, mg_id)
                if not os.path.isdir(dir_report_mg):
                    return {"code": 404, "message": "申请单号为: {} 迈景编号为：{} 报告目录不存在!".format(review.req_mg, mg_id), "data": None}, 404
                review_report_dir = os.path.join(review_dir, str(review.id))
                if not os.path.isdir(review_report_dir):
                    os.makedirs(review_report_dir)
                os.system("cp -r %s %s" % (dir_report_mg, review_report_dir))
                review_report_dir = os.path.join(review_report_dir, str(mg_id))
                zip_dir(review_report_dir)
                review.report_file = str(mg_id) + ".zip"
            except Exception as e:
                print(e)
                msg = '申请单号为: {} 迈景编号为：{} 的报告上传审核失败!'.format(review.req_mg, mg_id)
                return {"code": 400, "message": msg, "data": None}, 400

            # 修改审核状态
            review.status = '内审中'
            db.session.commit()
            return {"code": 200, "message": "申请单号为: {} 迈景编号为：{} 报告已提交内审!".format(review.req_mg, mg_id), "data": None}, 200
        else:
            return {"code": 400, "message": "申请单号为: {} 迈景编号为：{} 报告信息未查询到!", "data": None}, 400

