import os, shutil
import json
import datetime

from flask import (jsonify, current_app)
from flask_login import current_user, login_required
from flask_restful import (reqparse, Resource, fields, request)
from sqlalchemy import and_, or_

from app.models import db
from app.models.user import User
from app.models.run_info import RunInfo, SeqInfo
from app.models.sample_v import (SampleInfoV, ApplyInfo, TreatInfoV, PathologyInfo, Operation, PatientInfoV,
                                 FamilyInfoV)
from app.models.report import Report
from app.models.review_report import ReviewLib

from app.libs.get_data import read_json
from app.libs.ext import str2time, set_float, time_set, set_time_now, calculate_time
from app.libs.report import save_reesult, get_qc_raw, dict2df, save_reesult_lims
from app.libs.upload import find_apply
from app.libs.lims import LimsApi


class GetAllSample(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('val', required=True, type=str,
                                 help='迈景编号/申请单号/患者姓名')

    def get(self):
        all_sample = {}
        dir_app = current_app.config['PRE_REPORT']
        dir_sample = os.path.join(dir_app, 'sample', 'sample.json')
        sams = read_json(dir_sample, 'sample_info')
        all_sample['all_sample'] = sams
        # print(type(sams))
        return jsonify(all_sample)


class GetRunInfo(Resource):

    def get(self):
        """
        方法名称：获取上机信息
        方法描述：调用此API接口获取上机信息
        ---
        tags:
            - PGM报告相关API接口
        parameters:
            - name: search
              in: query
              type: string
              default: ''
              description: 搜索条件

            - name: page
              in: query
              type: integer
              default: 1
              description: 当前页码数

            - name: page_per
              in: query
              type: integer
              default: 10
              description: 每页条数

        responses:
            401:
                description: 用户身份验证失败!
                schema:
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {code: 401, message: "身份验证失败!", data: null}
            200:
                description: 获取上机信息成功!
                schema:
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {
                            code: 200,
                            message: "获取身份信息成功!",
                            data: {total: 123, run: [{id: 98, name: "S202008018-CCF", start_T: "2020-08-17 12:00:00",
                            end_T: "2020-08-17 16:30:00", platform: "S5"}]}
                        }
        """
        parser = reqparse.RequestParser()
        parser.add_argument('search', type=str, help='搜索条件')
        parser.add_argument('page', type=int, help='页码')
        parser.add_argument('page_per', type=int, help='每页数量')
        args = parser.parse_args()

        # 获取参数
        page = args.get('page')
        per_page = args.get('page_per')
        search = args.get('search')

        run_info = {}
        runs = RunInfo.query.filter(RunInfo.name.like('%{}%'.format(search))).order_by(RunInfo.start_T.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        list_run = []
        for run in runs.items:
            list_run.append(run.to_dict())
        run_info['run'] = list_run
        run_info['total'] = runs.total
        return {
            "code": 200,
            "message": "上机信息获取成功!",
            "data": run_info
        }, 200

    def post(self):  # 生成报告
        parser = reqparse.RequestParser()
        parser.add_argument('id', help='样本id')
        args = parser.parse_args()

        # 获取参数
        mg_id = args.get('id')
        token = request.cookies.get('token')
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405
        name = user.username
        run = RunInfo.query.filter(RunInfo.id == mg_id).first()
        msgs = []
        for seq in run.seq_info:
            if seq.status == '分析完成':
                apply = ApplyInfo.query.filter(ApplyInfo.req_mg == seq.sample_mg).first()
                for sam in apply.sample_infos:
                    if seq.sample_name in sam.sample_id:
                        sam.seq.append(seq)
                        msg = save_reesult(seq, name, sam)

                        msgs.append(msg)
            elif seq.status == '结果已保存':
                msgs.append('样本{}结果已经保存'.format(seq.sample_name))
            else:
                msgs.append('样本{}未分析完成'.format(seq.sample_name))

        return {'msg': ','.join(msgs)}

    def delete(self):
        """
            方法名称：删除批次信息API接口
            方法描述：调用此API接口删除批次信息
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: id
                  in: query
                  required: true
                  type: string
                  description: 批次id号!
            responses:
                200:
                    description: 删除成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "删除成功!",data: null}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', help='样本id')
        args = parser.parse_args()
        id = args.get('id')
        run = RunInfo.query.filter(RunInfo.id == id).first()
        run_id = run.name

        for seq in run.seq_info:
            sam = seq.sample_info_v
            if sam:
                report = sam.report
                sam.seq.remove(seq)
            run.seq_info.remove(seq)
            db.session.delete(seq)

        db.session.delete(run)
        db.session.commit()
        # return {'msg': '{}.删除完成'.format(run_id)}
        return {"code": 200, "message": "删除成功!", "data": None}, 200

    def put(self):
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        data = request.get_data()
        sams = (json.loads(data)['sams'])
        for sam in sams:
            seq_id = sam.get('id')
            # print(sam)
            SeqInfo.query.filter(SeqInfo.id == seq_id).update(sam)
        db.session.commit()
        return {'msg': '保存成功'}


class GetSeqInfo(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('name', type=str, help='run name')
        self.parser.add_argument('sams', help='报告编号', action='append')

    def get(self):
        """
            方法名称：获取单个批次API接口
            方法描述：调用此API接口获取单个批次信息
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: name
                  in: query
                  required: true
                  type: string
                  description: 批次名称!
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
                            run: {end_T: "Wed, 14 Oct 2020 16:30:00 GMT", id: 252, name: "S202010005-ZJM", platform: "S5",start_T: "Wed, 14 Oct 2020 12:00:00 GMT"},
                            seq: [{barcode: "XP-38", cancer: "", cell_percent: "0.1", gender: "男", id: 2864, item: "52",note: "流转52RNA，575验证",
                            report_item: "",sam_type: "TR",sample_mg: "MG2013970105",sample_name: "MG2008130",status: "分析完成"}],
                            seq_title:[
                                {align: "center", type: "selection", width: "50"}
                                ]
                            }
                        }
        """

        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        args = self.parser.parse_args()
        run_info = {}
        run_name = args.get('name')
        run = RunInfo.query.filter(RunInfo.name == run_name).first()
        run_info['run'] = run.to_dict()
        list_seq = []
        for seq in run.seq_info:
            list_seq.append(seq.to_dict())
        run_info['seq'] = list_seq
        run_info['seq_title'] = [
            {'type': 'selection', 'width': '50', 'align': 'center'},
            {'title': '操作', 'slot': 'action', 'width': '200'},
            {'title': '状态', 'key': 'status', 'width': '150'},
            {'title': '迈景编号', 'key': 'sample_name', 'width': '150'},
            {'title': '申请单号', 'key': 'sample_mg', 'width': '150'},
            {'title': '检测内容', 'key': 'item', 'width': '150'},
            {'title': '性别', 'key': 'gender', 'width': '150'},
            {'title': '样本类型', 'key': 'sam_type', 'width': '150'},
            {'title': '肿瘤细胞占比', 'key': 'cell_percent', 'width': '150'},
            {'title': 'Barcode编号', 'key': 'barcode', 'width': '150'},
            {'title': '肿瘤类型(报告用)', 'key': 'cancer', 'width': '150'},
            {'title': '报告模板', 'key': 'report_item', 'width': '150'},
            {'title': '备注', 'key': 'note', 'width': '150'}
        ]
        return jsonify(run_info)

    #  样本信未保存至数据库 todo：将所有样本信息保存到数据库

    def post(self):
        """
            方法名称：保存结果信息API接口
            方法描述：调用此API接口保存结果
            ---
            tags:
                - PGM报告相关API接口
            responses:
                200:
                    description: 样本结果保存成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "样本结果保存成功!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        # 获取当前用户任务
        all_task = ReviewLib.query.filter(
            and_(
                ReviewLib.reporter == user.username,
                or_(
                    ReviewLib.status == '出具中',
                    ReviewLib.status == '审核未通过'
                )
            )
        ).all()
        # 保存当前报告出具者并且分析完成的结果
        sams_lims = []
        sams = []
        err = []
        msgs = []
        for task in all_task:
            if str(task.resource) == "lims":
                run = RunInfo.query.filter(RunInfo.name == str(task.run)).first()
                if run:
                    run_info_id = run.id
                else:
                    err.append("样本编号: {}, 检测策略: {} 未检测到批次号信息!".format(task.mgid, task.detect_way))
                    continue
                seq = SeqInfo.query.filter(
                    and_(  # run名称 + 样本名称 + 检测策略
                        SeqInfo.run_info_id == run_info_id,
                        SeqInfo.sample_name == task.mgid,
                        SeqInfo.item == task.detect_way,
                    )
                ).filter(SeqInfo.status == "分析完成").first()
                if seq:
                    sams_lims.append(seq.to_dict())
            else:  # 旧的数据
                seq = SeqInfo.query.filter(
                    and_(
                        SeqInfo.sample_name == task.mgid,
                        SeqInfo.sample_mg == task.req_mg
                    )
                ).filter(SeqInfo.status == "分析完成").first()
                if seq:
                    sams.append(seq.to_dict())
        # 区分保存旧数据和lims数据
        err = []
        msg = []
        self.save_result_lims(user.username, sams_lims, err, msg)
        self.save_result_local(user.username, sams, err, msg)
        if len(err) > 0:
            return {"code": 400, "message": ",".join(err), "data": None}, 400
        else:
            return {"code": 200, "message": ",".join(msg), "data": None}, 200

    def save_result_local(self, name, sams, err, msgs):
        """ 保存结果: 兼容旧数据 """
        dir_app = current_app.config['PRE_REPORT']
        dir_sample = os.path.join(dir_app, 'sample', 'sample.json')
        # samples = read_json(dir_sample, 'sample_info')[0]['sams']
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')
        if not os.path.exists(dir_report):
            os.mkdir(dir_report)

        for sam in sams:
            seq_id = sam.get('id')
            seq = SeqInfo.query.filter(SeqInfo.id == seq_id).first()
            if seq.status == '分析完成':
                applys = ApplyInfo.query.filter(ApplyInfo.req_mg == seq.sample_mg).all()  # 获取申请单信息
                if applys:
                    for apply in applys:
                        # print(f'申请单信息id:{apply.id}')
                        for sam in apply.sample_infos:
                            if seq.cancer:
                                if seq.sample_name in sam.sample_id:
                                    sam.seq.append(seq)
                                    # print(seq.cell_percent)
                                    pathology = PathologyInfo(cell_content=seq.cell_percent)
                                    db.session.add(pathology)
                                    sam.pathology_info = pathology
                                    msg, flag = save_reesult(seq, name, sam)  # 保存结果
                                    if flag is True:
                                        msgs.append(msg)
                                    else:
                                        err.append(msg)

                                    dic_out = (get_qc_raw(seq))
                                    qc = dic_out.get('qc')

                                    dic_qc = {}
                                    for row in qc:
                                        if 'D' in row['Sample']:
                                            dic_qc['on_target'] = row['On_Target']
                                            dic_qc['coverage'] = row['Coverage']
                                            dic_qc['dna_reads'] = row['Clean_reads']
                                            dic_qc['depth'] = row['Depth(X)']
                                            dic_qc['uniformity'] = row['Uniformity']
                                        if 'R' in row['Sample']:
                                            dic_qc['rna_reads'] = row['RNA_mapped_reads']
                                    pat = apply.patient_info_v.to_dict()
                                    dic_detail = {'迈景编号': apply.mg_id, '申请单号': apply.req_mg, '检测内容': seq.item,
                                                  '申请单检测项目': seq.report_item,
                                                  '治疗史，家族史': f"{pat['treat_info']},{pat['family_info']}",
                                                  '癌症类型': apply.cancer_d, '样本类型': seq.sam_type,
                                                  '肿瘤细胞纯度': seq.cell_percent,
                                                  'DNA mapped reads数': dic_qc.get('dna_reads'),
                                                  'on target': dic_qc.get('on_target'), '测序深度': dic_qc.get('depth'),
                                                  '均一性': dic_qc.get('uniformity'),
                                                  '覆盖完整性': dic_qc.get('coverage'),
                                                  'RNA mapped reads数': dic_qc.get('rna_reads') if dic_qc.get(
                                                      'rna_reads') else '',
                                                  '检测的突变': '', '靶向药物': '', '销售': apply.sales,
                                                  '报告状态': '', '报告制作人': '', '收样日期': time_set(sam.receive_t),
                                                  '报告日期': set_time_now(),
                                                  '质控时间': f"{calculate_time(time_set(sam.receive_t), set_time_now())}天"}
                                    df = dict2df([dic_detail])
                                    mg_id = apply.mg_id
                                    req_mg = apply.req_mg
                                    dir_report_mg = os.path.join(dir_report, mg_id)
                                    if not os.path.exists(dir_report_mg):
                                        os.mkdir(dir_report_mg)
                                    excel_f = os.path.join(dir_report_mg, f"{mg_id}_{req_mg}.xlsx")
                                    df.to_excel(excel_f, sheet_name='详情', index=False)
                                    dir_apply = current_app.config['UPLOADED_FILEREQ_DEST']
                                    apply_f = find_apply(time_set(sam.receive_t), apply.req_mg, dir_apply)
                                    for file in apply_f:
                                        if file:
                                            shutil.copy2(file, os.path.join(dir_report_mg, os.path.split(file)[-1]))
                                else:
                                    err.append(f'样本{seq.sample_name} 迈景编号与样本信息不符')
                            else:
                                err.append(f'样本{seq.sample_name} 肿瘤类型（报告用未填写）')
                else:
                    err.append('样本{} 的样本信息未录入，请到样本信息登记处录入'.format(seq.sample_name))
            elif seq.status == '结果已保存':
                msgs.append('样本{}结果已经保存'.format(seq.sample_name))
            else:
                err.append('样本{}未分析完成'.format(seq.sample_name))
        if len(err) > 0:  # 存在报错或者警告信息
            # return {"code": 400, "message": ','.join(err), "data": None}, 400
            return err, 400
        else:
            # return {"code": 200, "message": ','.join(msgs), "data": None}, 200
            return msgs, 200

    def save_result_lims(self, name, sams, err, msgs):
        """
            方法名称：保存结果信息API接口
            方法描述：调用此API接口保存结果
            ---
            tags:
                - PGM报告相关API接口
            responses:
                200:
                    description: 样本结果保存成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "样本结果保存成功!", data: null}
        """

        dir_app = current_app.config['PRE_REPORT']
        dir_sample = os.path.join(dir_app, 'sample', 'sample.json')
        samples = read_json(dir_sample, 'sample_info')[0]['sams']
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')
        if not os.path.exists(dir_report):
            os.mkdir(dir_report)

        for sam in sams:
            seq_id = sam.get('id')
            seq = SeqInfo.query.filter(SeqInfo.id == seq_id).first()
            if seq.status == '分析完成':
                # 保存结果到 static/res_report/report/mgid 目录, 目前考虑 run + 样本名, 可能需要加barcode或者检测策略来确定样本唯一性
                if not seq.cancer:
                    err.append(f'请确定样本{seq.sample_name} 肿瘤类型')
                    continue
                msg, flag = save_reesult_lims(seq, name, sam)  # 保存结果
                if flag is True:  # 结果保存成功
                    msgs.append(msg)
                else:
                    err.append(msg)

                dic_out = (get_qc_raw(seq))
                qc = dic_out.get('qc')
                dic_qc = {}
                for row in qc:
                    if 'D' in row['Sample']:
                        dic_qc['on_target'] = row['On_Target']
                        dic_qc['coverage'] = row['Coverage']
                        dic_qc['dna_reads'] = row['Clean_reads']
                        dic_qc['depth'] = row['Depth(X)']
                        dic_qc['uniformity'] = row['Uniformity']
                    if 'R' in row['Sample']:
                        dic_qc['rna_reads'] = row['RNA_mapped_reads']

                lims = LimsApi()
                sample_info = lims.save_result_info(seq.sample_name, seq.sample_mg)  # 参数: 样本名、申请单编号
                run = seq.run_info
                review = ReviewLib.query.filter(
                    and_(
                        ReviewLib.run == run.name,
                        ReviewLib.mgid == seq.sample_name,
                        ReviewLib.detect_way == seq.item
                    )
                ).first()
                dic_detail = {'迈景编号': seq.sample_name, '申请单号': seq.sample_mg, '检测内容': seq.item,
                              '申请单检测项目': seq.report_item,
                              '治疗史，家族史': f"{sample_info['treat_info']},{sample_info['family_info']}",
                              '癌症类型': seq.cancer, '样本类型': seq.sam_type,
                              '肿瘤细胞纯度': seq.cell_percent,
                              'DNA mapped reads数': dic_qc.get('dna_reads'),
                              'on target': dic_qc.get('on_target'), '测序深度': dic_qc.get('depth'),
                              '均一性': dic_qc.get('uniformity'),
                              '覆盖完整性': dic_qc.get('coverage'),
                              'RNA mapped reads数': dic_qc.get('rna_reads') if dic_qc.get(
                                  'rna_reads') else '',
                              '检测的突变': '', '靶向药物': '', '销售': sample_info['sales'],
                              '报告状态': '', '报告制作人': '', '收样日期': time_set(str(review.received_date)),
                              '报告日期': set_time_now(),
                              '质控时间': ''
                              # '质控时间': f"{calculate_time(time_set(str(review.received_date)), set_time_now())}天"
                              }
                df = dict2df([dic_detail])
                mg_id = seq.sample_name
                req_mg = seq.sample_mg
                dir_report_mg = os.path.join(dir_report, mg_id)
                if not os.path.exists(dir_report_mg):
                    os.mkdir(dir_report_mg)
                excel_f = os.path.join(dir_report_mg, f"{mg_id}_{req_mg}.xlsx")
                df.to_excel(excel_f, sheet_name='详情', index=False)  # 保存样本信息到 {mg_id}_{req_mg}.xlsx 文件
                # 查找申请单, 并拷贝到结果目录  -- 暂不拷贝
                # dir_apply = current_app.config['UPLOADED_FILEREQ_DEST']
                # apply_f = find_apply(time_set(str(review.received_date)), req_mg, dir_apply)
                # for file in apply_f:
                #     if file:
                #         shutil.copy2(file, os.path.join(dir_report_mg, os.path.split(file)[-1]))  # 拷贝申请单文件

            elif seq.status == '结果已保存':
                msgs.append('样本{}结果已经保存'.format(seq.sample_name))
            else:
                err.append('样本{}未分析完成'.format(seq.sample_name))
        if len(err) > 0:  # 存在报错或者警告信息
            # return {"code": 400, "message": ','.join(err), "data": None}, 400
            return err, 400
        else:
            # return {"code": 200, "message": ','.join(msgs), "data": None}, 200
            return msgs, 200

    def put(self):
        """
            方法名称：重新分析API接口
            方法描述：调用此API接口重新分析
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - sams
                    properties:
                        sams:
                            type: json
                            description: 样本信息
            responses:
                200:
                    description: 样本已重新分析!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200, message: "开始重新分析!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        data = request.get_data()
        sams = (json.loads(data)['sams'])
        for sam in sams:
            seq_id = sam.get('id')
            seq = SeqInfo.query.filter(SeqInfo.id == seq_id).first()
            seq.status = '重新分析' #测试修改该部分，提交请前务必修改回来
        db.session.commit()
        # return {'msg': '开始重新分析'}
        return {"code": 200, "message": "开始重新分析", "data": None}, 200


class SeqQc(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', help='报告id')
        self.parser.add_argument('mgid', help='迈景编号')
        self.parser.add_argument('report_item', help='检测项目')
        self.parser.add_argument('resource', default='', help='数据来源')

    def get(self):
        """
            方法名称：获取样本QC、原始数据、白名单API接口
            方法描述：调用此API接口获取样本QC、原始数据、白名单
            ---
            tags:
                - PGM报告相关API接口
            parameters:
                - name: id
                  in: query
                  required: true
                  type: string
                  description: 报告id
                - name: mgid
                  in: query
                  required: true
                  type: string
                  description: 迈景编号
                - name: report_item
                  in: query
                  required: true
                  type: string
                  description: 检测项目
                - name: resource
                  in: query
                  required: true
                  type: string
                  description: 数据来源
            responses:
                200:
                    description: 获取变异白名单成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: { code: 200, message: "获取变异白名单成功!", data:
                            {
                                filter: [{Hotspot: "YES", ID: "COSV54736340", OKR注释类型: "mutation", 功能影响: "missense_variant", 变异丰度: "0.5%", 变异类型: "SNV", 基因: "NRAS", 基因座: "chr1:115256529-115256529", 外显子: "exon3", 报告类型: "突变", 氨基酸改变: "p.Gln61Arg", 氨基酸改变-简写: "p.Q61R", 深度: "3188.0", 编码改变: "c.182A>G", 转录本: "NM_002524.4" }],
                                qc: [{"#Run": "S202010005-ZJM", Barcode: "IonXpress_063", Clean_bases(Mbp): "96.3", Clean_reads: "811585", Coverage: "100.00%", Depth(X): "2882", ExprControl_Numbers: "-", GC: "49.96%", MQ17: "97.32%", Mapping: "99.95%", On_Target: "96.98%", Panel: "T52", Q20: "92.02%", Q30: "67.94%", RNA_mapped_reads: "-", Read_length: "118.66", Sample: "MG2008172TD", Uniformity: "99.83%", Uniq_Depth: "-", 分析版本: "IR=V5.6;Pipeline=V1.0", 异常提示: "-"}],
                                qc_title: [{key: "#Run", title: "#Run", width: "100"}],
                                raw: [{"#VariantType": "SNV", AF: "0.2", Alt: "G", COSMIC: "COSV63871622", Chr: "chr1", Clinvar: "Likely_pathogenic", Depth: "3932.0", End: "11184574", Exon_ID: "exon47", Function_types: "missense_variant", Gene: "MTOR", Hotspot: "YES", Likely_Type: "Somatic", MAF: ".", Ref: "A", Start: "11184574", Transcript: "NM_004958.3", cHGVS: "c.6643T>C", dbSNP: ".", pHGVS_1: "p.S2215P", pHGVS_3: "p.Ser2215Pro"}],
                                raw_title: [{key: "#VariantType", title: "#VariantType", width: "100"}, {key: "Chr", title: "Chr", width: "100"}],
                                w_list: [{"#Chr": "chr12", AD: "504", AD.F: "235", AD.R: "269", AF: "20.2735%", Alt: "T", ComName: "p.G13D", DP: "2486", End: "25398281", Gene: "KRAS", MQ17_AD: "499", MQ17_AD.F: "234", MQ17_AD.R: "265", MQ17_AF: "20.1779%", MQ17_DP: "2473", MQ17_Strand_Bias: "0.53", Ref: "C", Start: "25398281", Strand_Bias: "0.53", VariantLen: "1", VariantType: "SNV", cHGVS: "c.38G>A"}],
                                w_list_title: [{key: "#Chr", title: "#Chr", width: "100"}, {key: "Start", title: "Start", width: "100"}]
                            }
                        }
        """
        argv = self.parser.parse_args()
        rep_id = argv.get('id')
        mgid = argv.get('mgid')
        report_item = argv.get('report_item')
        resource = argv.get('resource')
        if str(resource) == "lims":
            seq = SeqInfo.query.filter(
                and_(SeqInfo.sample_name == mgid, SeqInfo.report_item == report_item)
            ).first()
        else:
            sam = Report.query.filter(Report.id == rep_id).first().sample_info_v
            seq = SeqInfo.query.filter(SeqInfo.sample_name == sam.sample_id).first()
        dic_out = (get_qc_raw(seq))
        qc = dic_out.get('qc')
        if qc:
            qc_title = [{'title': k, 'key': k, 'width': '100'} for k in qc[0].keys()]
            dic_out['qc_title'] = qc_title
        raw = dic_out.get('raw')
        if raw:
            dic_out['raw_title'] = [{'title': k, 'key': k, 'width': '100'} for k in raw[0].keys()]
        w_list = dic_out.get('w_list')
        if w_list:
            dic_out['w_list_title'] = [{'title': k, 'key': k, 'width': '100'} for k in w_list[0].keys()]
        return {"code": 200, "message": "获取信息成功!", "data": dic_out}, 200

