import os
import re
import json
import shutil

from flask_restful import (reqparse, Resource, request)
from flask import (current_app)
from werkzeug.datastructures import FileStorage
from sqlalchemy import and_

from app.models import db
from app.models.run_info import RunInfo, SeqInfo
from app.models.annotate import ClinicInterpretation, OKR
from app.models.report import Report
from app.models.mutation import Mutation, Mutations, Chemotherapy
from app.models.record_config import SalesInfo, HospitalInfo, SampleType, \
    SeqItems, CancerTypes, Barcode, FlowItem, CancerTypes
from app.models.sample_v import PatientInfoV, FamilyInfoV, TreatInfoV, ApplyInfo, \
    SendMethodV, SampleInfoV, ReportItem, PathologyInfo, Operation
from app.models.review_report import ReviewLib

from app.libs.ext import file_sam, file_okr, file_pdf, file_request, scp_to_108, ssh_con
from app.libs.upload import save_json_file, excel_to_dict, get_excel_title, get_seq_info, excel2dict, df2dict, time_set, \
    tsv_to_list, file_2_dict, m_excel2list, unzip_file
from app.libs.report import del_db
from app.libs.ir import save_mutation
from app.libs.get_data import read_json


class SampleInfoUpload(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('file', type=FileStorage, required=True, help='样本信息登记表')
        super(SampleInfoUpload, self).__init__()

    def post(self):
        filename = file_sam.save(request.files['file'])
        file = file_sam.path(filename)
        dict_sample = excel_to_dict(file)
        dir_app = current_app.config['PRE_REPORT']
        try:
            os.mkdir(os.path.join(dir_app, 'sample'))
        except IOError:
            pass

        dir_sample = os.path.join(dir_app, 'sample', 'sample.json')
        save_json_file(dir_sample, dict_sample, 'sample_info')
        os.remove(file)
        return {'msg': '样本信息保存成功！！'}


class SampleInfoVUpload(Resource):
    def post(self):
        """
        方法名称：样本信息登记文件上传, 注意: 检测项目字段，如果存在多个检测项目使用中文 "、" 号分隔
        方法描述：调用此API接口上传样本信息, 注意: 文件名不要使用中文, 检测项目字段，如果存在多个检测项目使用中文 "、" 号分隔
        ---
        tags:
            - 样本信息录入相关API接口
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
        for row in list_sam:
            apply = ApplyInfo.query.filter(
                and_(ApplyInfo.req_mg == row.get('申请单号'), ApplyInfo.mg_id == row.get('迈景编号'))).first()
            if apply:  # 更新
                dic_row = {'name': row.get('患者姓名'), 'age': row.get('病人年龄'), 'gender': row.get('病人性别'),
                           'nation': row.get('民族'), 'origo': row.get('籍贯'), 'contact': row.get('病人联系方式'),
                           'ID_number': row.get('病人身份证号码'), 'address': row.get('病人地址'),
                           'have_family': row.get('有无家族遗传疾病'), 'targeted_info': row.get('是否靶向药治疗'),
                           'smoke': row.get('有无吸烟史'), 'chem_info': row.get('是否接受化疗'), 'radio_info': row.get('是否放疗'),
                           'mg_id': row.get('迈景编号'), 'req_mg': row.get('申请单号'), 'sales': row.get('销售代表'),
                           'pi_name': row.get('PI姓名'), 'outpatient_id': row.get('门诊/住院号'), 'doctor': row.get('医生姓名'),
                           'hosptial': row.get('医院名称'), 'room': row.get('科室'), 'cancer_d': row.get('临床诊断'),
                           'seq_type': row.get('项目类型'), 'pathological': row.get('病理诊断'), 'note': row.get('备注'),
                           'to': row.get('报告收件人'), 'phone_n': row.get('联系电话'), 'addr': row.get('联系地址'),
                           'sample_id': row.get('迈景编号'), 'pnumber': row.get('病理号'), 'Tytime': row.get('取样时间'),
                           'receive_t': row.get('收样日期'), 'sample_type': row.get('样本类型（报告用）'), 'mth': row.get('采样方式'),
                           'mth_position': row.get('样本来源'), 'sample_count': row.get('数量')}

                pat = apply.patient_info_v
                PatientInfoV.query.filter(PatientInfoV.id == pat.id).update(
                    {'name': row.get('患者姓名'), 'age': row.get('病人年龄'), 'gender': row.get('病人性别'),
                     'nation': row.get('民族'), 'origo': row.get('籍贯'), 'contact': row.get('病人联系方式'),
                     'ID_number': row.get('病人身份证号码'), 'address': row.get('病人地址'),
                     'have_family': row.get('有无家族遗传疾病'), 'targeted_info': row.get('是否靶向药治疗'),
                     'smoke': row.get('有无吸烟史'), 'chem_info': row.get('是否接受化疗'), 'radio_info': row.get('是否放疗')})

                ApplyInfo.query.filter(ApplyInfo.id == apply.id).update(
                    {'mg_id': row.get('迈景编号'), 'req_mg': row.get('申请单号'), 'sales': row.get('销售代表'),
                     'pi_name': row.get('PI姓名'), 'outpatient_id': row.get('门诊/住院号'), 'doctor': row.get('医生姓名'),
                     'hosptial': row.get('医院名称'), 'room': row.get('科室'), 'cancer_d': row.get('临床诊断'),
                     'hosptial_code': row.get('门诊/住院号'), 'pathological_code': row.get('病理号'),
                     'seq_type': row.get('项目类型'), 'pathological': row.get('病理诊断'), 'note': row.get('备注')})
                sam = apply.sample_infos[0]
                SampleInfoV.query.filter(SampleInfoV.id == sam.id).update(
                    {'sample_id': row.get('迈景编号'), 'pnumber': row.get('病理号'), 'Tytime': row.get('取样时间'), 'detect_t': row.get('检测日期'),
                     'receive_t': row.get('收样日期'), 'sample_type': row.get('样本类型（报告用）'), 'mth': row.get('采样方式'),
                     'mth_position': row.get('样本来源'), 'sample_count': row.get('数量'), 'send_t': row.get('送检日期')})

                # 更新检测项目
                detect_item_old = apply.rep_item_infos
                for detect in detect_item_old:
                    apply.rep_item_infos.remove(detect)
                items = re.split(r'、', row.get('检测项目'))
                for item in items:
                    r_item = ReportItem(req_mg=row.get('申请单号'), name=item)
                    apply.rep_item_infos.append(r_item)
                db.session.commit()

            else:  # 上传
                pat = PatientInfoV(name=row.get('患者姓名'), age=row.get('病人年龄'), gender=row.get('病人性别'),
                                   nation=row.get('民族'), origo=row.get('籍贯'), contact=row.get('病人联系方式'),
                                   ID_number=row.get('病人身份证号码'), address=row.get('病人地址'),
                                   have_family=row.get('有无家族遗传疾病'),
                                   targeted_info=row.get('是否靶向药治疗'), smoke=row.get('有无吸烟史'),
                                   chem_info=row.get('是否接受化疗'), radio_info=row.get('是否放疗'))
                db.session.add(pat)
                apply = ApplyInfo(mg_id=row.get('迈景编号'), req_mg=row.get('申请单号'), sales=row.get('销售代表'),
                                  pi_name=row.get('PI姓名'), pathological_code=row.get('病理号'),
                                  hosptial_code=row.get('门诊/住院号'),
                                  outpatient_id=row.get('门诊/住院号'), doctor=row.get('医生姓名'), hosptial=row.get('医院名称'),
                                  room=row.get('科室'), cancer_d=row.get('临床诊断'), seq_type=row.get('项目类型'),
                                  pathological=row.get('病理诊断'), note=row.get('备注'))
                db.session.add(apply)
                pat.applys.append(apply)
                # sned_mth = SendMethodV(to=row.get('报告收件人'), phone_n=row.get('联系电话'), addr=row.get('联系地址'))
                # db.session.add(sned_mth)
                # apply.send_methods = sned_mth
                sam = SampleInfoV(sample_id=row.get('迈景编号'), pnumber=row.get('病理号'), Tytime=row.get('取样时间'),
                                  receive_t=row.get('收样日期'), send_t=row.get('送检日期'), detect_t=row.get('检测日期')
                                  , sample_type=row.get('样本类型（报告用）'), mth=row.get('采样方式'), mth_position=row.get('样本来源')
                                  , sample_count=row.get('数量'))
                db.session.add(sam)
                apply.sample_infos.append(sam)

                # 更新检测项目
                items = re.split(r'、', row.get('检测项目'))
                for item in items:
                    r_item = ReportItem(req_mg=row.get('申请单号'), name=item)
                    apply.rep_item_infos.append(r_item)

        db.session.commit()
        # path_sample = current_app.config['SAMPLEINFO_DIR']
        # scp_to_108(ssh_con(),f'{os.path.join(os.getcwd(), file)}', path_sample)
        # os.remove(file)
        return {
            'code': 200,
            'message': '文件上传成功',
            'data': None
        }, 200


class RunInfoUpload(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('file', type=FileStorage, required=True,
                                 help='file')
        super(RunInfoUpload, self).__init__()

    def post(self):
        """
        方法名称：上机信息文件上传
        方法描述：调用此API接口上传上机信息, 文件名不要使用中文
        ---
        tags:
            - PGM报告相关API接口
        consumes:
            - multipart/form-data
        parameters:
            - name: file
              in: formData
              required: true
              type: file
              description: 上传上机信息文件, 格式 .xlsx
        responses:
            400:
                description: 文件格式或内容存在问题!
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
                    example: {code: 400, message: "文件格式或内容存在问题!", data: null}
            403:
                description: 文件正常处理, 但存在警告信息!
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
                    example: {code: 400, message: ">>>>样本_MG2001379_信息已存在", data: null}
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
        erro = []
        barcodes = set()
        for bar in Barcode.query.all():
            barcodes.add(bar.name)
        flowitems = set()
        for items in FlowItem.query.all():
            flowitems.add(items.name)
        l_cancer = set()
        for can in CancerTypes.query.all():
            l_cancer.add(can.name)
        dir_app = current_app.config['PRE_REPORT']
        dir_pgm_remplate = os.path.join(dir_app, 'template_config', 'template_pgm.json')
        config = read_json(dir_pgm_remplate, 'config')
        l_item = set()
        for row in config:
            l_item.add(row.get('item'))

        try:
            title = get_excel_title(file)
            # print(title)
            if title in ['S5', 'PGM', 's5', 'pgm']:
                df_seq = get_seq_info(file)
                for name, df in df_seq:
                    if name:
                        # print(df)
                        title_df = [v for v in df.columns]
                        if '肿瘤类型(报告用)' not in title_df and '报告模板' not in title_df:
                            erro.append('上机信息未包含“肿瘤类型(报告用)”或“报告模板”')
                        dict_run = df2dict(df)
                        for dict_val in dict_run.values():
                            cur_erro = []
                            run = RunInfo.query.filter(RunInfo.name == name).first()
                            if run:
                                pass
                            else:
                                run = RunInfo(name=name, platform=title,
                                              start_T=time_set(dict_val.get('上机时间')),
                                              end_T=time_set(dict_val.get('结束时间')))

                                db.session.add(run)
                                if erro:
                                    break
                                else:
                                    db.session.commit()
                            barcode = dict_val.get('Barcode编号').split('/')
                            sam_type = dict_val.get('样本类型').split('/')
                            cancer = dict_val.get('肿瘤类型(报告用)')
                            rep_item = dict_val.get('报告模板')
                            # print(f'样本{dict_val.get("迈景编号")}')

                            if cancer and (cancer not in l_cancer):
                                cur_erro.append(
                                    f'样本{dict_val.get("迈景编号")}癌症类型_{cancer}_不包含在数据库中，请修改后重试！！，所有类型：{"、".join(l_cancer)}。')

                            if rep_item and (rep_item not in l_item):
                                cur_erro.append(
                                    f'样本{dict_val.get("迈景编号")}报告模板_{rep_item}_不包含在数据库中，请修改后重试！！，所有模板：{"、".join(l_item)}。')

                            for bar in barcode:
                                if bar in barcodes:
                                    continue
                                cur_erro.append('样本{}Barcode编号存在问题，请检查后重试！！'.format(dict_val.get('迈景编号')))
                            for i in sam_type:
                                if i in flowitems:
                                    continue
                                cur_erro.append('样本{}样本类型存在问题，请检查后重试！！'.format(dict_val.get('迈景编号')))

                            seq = SeqInfo.query.filter(and_(SeqInfo.sample_name == dict_val.get('迈景编号'),
                                                            SeqInfo.barcode == dict_val.get('Barcode编号'))).first()

                            if seq:
                                # print(f"样本id为{seq.id}")
                                cur_erro.append('样本_{}_信息已存在'.format(dict_val.get('迈景编号')))
                            else:
                                seq = SeqInfo(sample_name=dict_val.get('迈景编号'), sample_mg=dict_val.get('申请单号'),
                                              item=dict_val.get('检测内容'), barcode=dict_val.get('Barcode编号'),
                                              note=dict_val.get('备注'), cancer=dict_val.get('肿瘤类型(报告用)'),
                                              report_item=dict_val.get('报告模板'), sam_type=dict_val.get('样本类型'),
                                              cell_percent=dict_val.get('肿瘤细胞占比'), status='准备分析',
                                              gender=dict_val.get('性别'))
                                if cur_erro:
                                    pass
                                else:
                                    db.session.add(seq)
                                    run.seq_info.append(seq)
                            if cur_erro:
                                erro.extend(cur_erro)
                                continue
                            else:
                                # print(f'样本{dict_val.get("迈景编号")}保存成功')
                                db.session.commit()

            else:
                dict_run = excel2dict(file)
                for dict_val in dict_run.values():
                    run = RunInfo.query.filter(RunInfo.name == dict_val.get('Run name')).first()
                    if run:
                        pass
                    else:
                        run = RunInfo(name=dict_val.get('Run name'), platform=title,
                                      start_T=time_set(dict_val.get('上机时间')),
                                      end_T=time_set(dict_val.get('下机时间')))
                        db.session.add(run)
                        # db.session.commit()
                    seq = SeqInfo.query.filter(SeqInfo.sample_name == dict_val.get('样本编号')).first()
                    if seq:
                        pass
                    else:
                        seq = SeqInfo(sample_name=dict_val.get('样本编号'),
                                      item=dict_val.get('检测项目'), barcode=dict_val.get('index(P7+P5)'),
                                      note=dict_val.get('备注'))
                        db.session.add(seq)
                        run.seq_info.append(seq)
                    # db.session.commit()

        except IOError:
            os.remove(file)
            return {
                "code": 400,
                "message": "文件有问题,请检查后再上传!",
                "data": None
            }, 400

        os.remove(file)
        if erro:
            msg = '>>>>'.join(erro)
            return {
                "code": 403,
                "message": msg,
                "data": None
            }, 403
        # 文件上传成功
        return {
            "code": 200,
            "message": "文件上传成功!",
            "data": None
        }, 200


class LimsOfflineData(Resource):
    """ lims接口: lims下机信息推送到报告系统 """
    def post(self):
        # 接收数据
        data = request.get_json()
        print(data)
        # 处理数据:  唯一键 = run名称 + 样本名 + 检测策略
        sample_info = {}
        required = ["run", "sample_id", "lib_id", "order_id", "pro_name", "pro_number", "detect_way", "nuc_type", "cancer", "barcode"]
        for row in data:
            # 处理样本id  Barcode
            # try:
            #     row['sample_id'] = row['sample_id'][0:10]
            # except Exception as e:
            #     print(e)
            #     return {"code": 400, "message": "请检查样本编号长度", "data": None}, 400
            if not all(True if filed in row.keys() and row[filed] != "" and (not row[filed] is None) else False for filed in required):
                return {"code": 400, "message": "{} {} 以下字段不能为 '' 或者 Null, {}".format(row["run"], row['sample_id'], ",".join(required)), "data": None}, 400
            unique_key = "{}\t{}\t{}".format(row["run"], row['sample_id'], row['detect_way'])
            sample_info.setdefault(unique_key, []).append(row)
        # 数据导入数据库
        for unique_key in sample_info.keys():
            row = self.deal_data(sample_info[unique_key])
            run = RunInfo.query.filter(RunInfo.name == row['run']).first()  # run_info表
            if not run:
                run = RunInfo(name=row['run'], start_T=time_set(row['start_T']), end_T=time_set(row['end_T']), platform=row['platform'])
                db.session.add(run)
                # db.session.commit()

            filter_info = {and_(SeqInfo.run_info_id == run.id, SeqInfo.sample_name == row["sample_id"], SeqInfo.item == row['panel'])}
            seq = SeqInfo.query.filter(*filter_info).first()   # seq_info表
            if seq:  # 更新
                SeqInfo.query.filter(SeqInfo.sample_name == row["sample_id"]).update(
                    {'item': row['panel'], 'barcode': row['barcodes'], 'note': row['note'], 'cancer': row['cancer'],
                     'report_item': row['pro_name'], 'pro_num': row['pro_number'], 'sam_type': row['nucleic'],
                     'cell_percent': row['cell_percent'], 'gender': row['gender'], 'libs': row["libs"], 'resource': 'lims'
                     }
                )
            else:  # 插入
                seq = SeqInfo(sample_name=row["sample_id"], sample_mg=row['order_id'], item=row['panel'],
                              barcode=row['barcodes'], note=row['note'], cancer=row['cancer'], report_item=row['pro_name'],
                              pro_num=row['pro_number'], sam_type=row['nucleic'], cell_percent=row['cell_percent'],
                              status='准备分析', gender=row['gender'], libs=row["libs"], resource="lims")
                db.session.add(seq)
                run.seq_info.append(seq)
            filter_info = {and_(ReviewLib.run == run.name, ReviewLib.mgid == row["sample_id"], ReviewLib.detect_way == row["panel"])}
            review = ReviewLib.query.filter(*filter_info).first()
            if review:  # 更新
                ReviewLib.query.filter(*filter_info).update(
                    {'pa_name': row['pa_name'], 'pro_name': row['pro_name'], 'pro_num': row["pro_number"],
                     'received_date': row['received_date'], 'dadeline': row['dadeline'], 'status': "等待出具", 'resource': 'lims'}
                )
            else:
                review = ReviewLib(run=row["run"], mgid=row['sample_id'], req_mg=row['order_id'], pa_name=row['pa_name'],
                                   pro_name=row['pro_name'], pro_num=row["pro_number"], detect_way=row["panel"], note=row['note'],
                                   received_date=row['received_date'], dadeline=row['dadeline'], status="等待出具", resource="lims")
                db.session.add(review)
            db.session.commit()
        return {"code": 200, "message": "下机信息推送成功!", "data": None}, 200

    def deal_data(self, sample_list):
        lib_list = []   # 文库号列表
        panel = ''   # 检测策略 - panel
        nuc_type = []  # 检测策略 - 核酸类型
        barcode_list = []  # barcode编号
        row = sample_list[0]
        detect_way = ""
        flag = True
        for lib in sample_list:
            lib_list.append(str(lib["lib_id"]))
            nuc_type.append(str(lib["nuc_type"]))
            detect_way = str(lib["detect_way"])  # 检测策略
            # 转换barcode
            bar_code_lib = Barcode.query.filter(Barcode.full_name == str(lib["barcode"])).first()
            if bar_code_lib:
                bar_code = bar_code_lib.name
                barcode_list.append(str(bar_code))
            else:
                barcode_list.append(str(lib["barcode"]))
        row['nucleic'] = "/".join(nuc_type)
        row["libs"] = "/".join(lib_list)
        panel = self.deal_detect_way(detect_way, nuc_type)  # 处理检测策略
        row['panel'] = panel
        row["barcodes"] = "/".join(barcode_list)
        return row

    def deal_detect_way(self, detect_way, sort_nuc):
        detect_way_list = re.split(r'\s+', detect_way)
        try:
            panel = str(detect_way_list[0])
            nuc_type = str(detect_way_list[1])
        except Exception as e:
            print(e)
            return detect_way

        if re.search(r'\+', panel) and re.search(r'\+', nuc_type):  # (22+4 TD+TR)
            # panel = re.sub(r'\+', '/', panel)
            # nuc_type = re.sub(r'\+', '/', nuc_type)
            panel = panel.split('+')
            nuc_tmp = nuc_type.split('+')
            if nuc_tmp[0] in sort_nuc[0]:  # CD  CDL
                panel = "/".join(panel)
            else:
                panel = "{}/{}".format(panel[1], panel[0])
        elif (not re.search(r'\+', panel)) and (re.search(r'\+', nuc_type)):  # (203 CD+CR)   (WES TD+GD)
            panel = "{}/{}".format(panel, panel)
        # else: (52 CD)  (575 TD)  ...
        return panel


class MutationUpload(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        # self.parser.add_argument('file', type=FileStorage, required=True, help='样本信息登记表')
        # self.parser.add_argument('name')
        super(MutationUpload, self).__init__()

    def post(self):
        filename = file_okr.save(request.files['file'])
        file = file_okr.path(filename)
        id = request.form['name']
        report = Report.query.filter(Report.id == id).first()
        mu = report.mutation
        if mu:
            del_db(db, mu.snv)
            del_db(db, mu.cnv)
            del_db(db, mu.fusion)
            db.session.commit()
        mutation = Mutations()
        dic = file_2_dict(file)
        # print(dic)
        if dic:
            for row in dic:
                snv = Mutation(gene=row.get('基因'),
                               mu_type=row.get('检测的突变类型'),
                               mu_name=row.get('变异全称'),
                               mu_af=row.get('丰度'),
                               mu_name_usual=row.get('临床突变常用名称'),
                               reads=row.get('支持序列数'),
                               maf=row.get('maf'),
                               exon=row.get('外显子'),
                               fu_type=row.get('检测基因型'), status='等待审核',
                               locus=row.get('位置'), type=row.get('type'))
                db.session.add(snv)
                mutation.mutation.append(snv)
        db.session.add(mutation)
        report.mutation = mutation
        db.session.commit()
        # print(report.mutation.id)

        os.remove(file)
        return {'msg': '突变信息上传成功！！！'}


class OKRUpload(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        # self.parser.add_argument('file', type=FileStorage, required=True, help='样本信息登记表')
        # self.parser.add_argument('name')
        super(OKRUpload, self).__init__()

    def post(self):
        filename = file_okr.save(request.files['file'])
        file = file_okr.path(filename)
        list_okr = tsv_to_list(file)
        okr_version = filename.split('_')[0]
        clinic = ClinicInterpretation.query.filter(ClinicInterpretation.okr_version == okr_version).first()
        if clinic:
            del_db(db, clinic.okr)
            db.session.commit()
        else:
            clinic = ClinicInterpretation(okr_version=okr_version)
        for okr_dic in list_okr:
            okr = OKR(disease=okr_dic.get('disease'), gene_name=okr_dic.get('gene_name'),
                      protein_alteration=okr_dic.get('protein_alteration'), drug=okr_dic.get('drug'),
                      drug_effect=okr_dic.get('drug_effect'), evidence=okr_dic.get('evidence'),
                      evidence_level=okr_dic.get('evidence_level'), grade=okr_dic.get('grade'))
            db.session.add(okr)
            clinic.okr.append(okr)

        db.session.commit()

        os.remove(file)
        return {'msg': 'okr更新成功!!!'}


class IrUpload(Resource):
    def __init__(self):
        pass

    def post(self):
        """
        方法名称：okr文件上传
        方法描述：调用此API接口上传okr文件
        ---
        tags:
            - PGM报告相关API接口
        consumes:
            - multipart/form-data
        parameters:
            - name: file
              in: formData
              required: true
              type: file
              description: 上传okr文件, 格式 .tsv
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
        dir_res = current_app.config['RES_REPORT']
        dir_report = os.path.join(dir_res, 'report')

        rep_id = request.form['name']
        resource = request.form['resource'] or ""
        report = Report.query.filter(Report.id == rep_id).first()
        if str(resource) == "lims":
            review = ReviewLib.query.filter(
                and_(
                    ReviewLib.req_mg == report.req_mg,
                    ReviewLib.pro_name == report.report_item
                )
            ).first()
            mg_id = str(review.mgid)
        else:
            sam = report.sample_info_v
            mg_id = sam.sample_id
        report.auto_okr = 'No'
        db.session.commit()
        filename = file_pdf.save(request.files['file'], name='{}.okr.tsv'.format(mg_id))
        file = file_pdf.path(filename)

        dir_report_mg = os.path.join(dir_report, mg_id)
        if not os.path.exists(dir_report_mg):
            os.mkdir(dir_report_mg)
        shutil.copy2(os.path.join(os.getcwd(), file), dir_report_mg)
        os.remove(file)
        return {"code": 200, "message": "文件上传成功!", "data": None}, 200


class GeneralUpload(Resource):
    def post(self):
        filename = file_okr.save(request.files['file'])
        file = file_okr.path(filename)

        item = request.form['name']
        if item == 'sales':
            list_sample = m_excel2list(file)
            for name, dict_r in list_sample.items():
                if name == 'sales':
                    for row in dict_r:
                        code = row['销售代码']
                        sale = SalesInfo.query.filter(SalesInfo.code == code).first()
                        if sale:
                            sale.name=row.get('销售姓名')
                            sale.mail=row.get('电子邮箱')
                        else:
                            sale = SalesInfo(code=code, name=row.get('销售姓名'),
                                             status=row.get('状态'), mail=row.get('电子邮箱'),
                                             region=row.get('所属区域'), phone=row.get('电话'),
                                             address=row.get('地址'))
                            db.session.add(sale)
                if name == 'hospital':
                    for row in dict_r:
                        h_name = row['医院']
                        hospital = HospitalInfo.query.filter(HospitalInfo.name == h_name).first()
                        if hospital:
                            pass
                        else:
                            hospital = HospitalInfo(name=h_name)
                            db.session.add(hospital)
                if name == 'type':
                    for row in dict_r:
                        name = row['样本类型']
                        ty = SampleType.query.filter(SampleType.name == name).first()
                        if ty:
                            pass
                        else:
                            ty = SampleType(name=name)
                            db.session.add(ty)
                if name == 'cancer':
                    for row in dict_r:
                        okr_name = row['okr']
                        name = row['癌症类型']
                        cancer = CancerTypes.query.filter(CancerTypes.name == name).first()
                        if cancer:
                            pass
                        else:
                            cancer = CancerTypes(name=name, okr_name=okr_name)
                            db.session.add(cancer)
                if name == 'items':
                    for row in dict_r:
                        name = row['检测项目']
                        items = SeqItems.query.filter(SeqItems.name == name).first()
                        if items:
                            pass
                        else:
                            items = SeqItems(name=name)
                            db.session.add(items)
                if name == 'Barcode':
                    for row in dict_r:
                        name = row['barcode']
                        full_name = row['barcode_a']
                        barcode = Barcode.query.filter(Barcode.name == name).first()
                        if barcode:
                            Barcode.query.filter(Barcode.name == name).update({
                                'full_name': full_name
                            })
                        else:
                            barcode = Barcode(name=name, full_name=full_name)
                            db.session.add(barcode)
                if name == 'Sample':
                    for row in dict_r:
                        name = row['编号']
                        type = row['类型']
                        barcode = FlowItem.query.filter(FlowItem.name == name).first()
                        if barcode:
                            FlowItem.query.filter(FlowItem.name == name).update({
                                'type': type
                            })
                        else:
                            barcode = FlowItem(name=name, type=type)
                            db.session.add(barcode)
            # 利用item 添加新的项目

        db.session.commit()
        os.remove(file)


class ApplyUpload(Resource):
    def post(self):
        """
        方法名称：申请单文件上传
        方法描述：调用此API接口上传申请单文件, 文件名不要使用全中文
        ---
        tags:
            - PGM报告相关API接口
        consumes:
            - multipart/form-data
        parameters:
            - name: file
              in: formData
              required: true
              type: file
              description: 上传申请单文件, 格式 .zip
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
        filename = file_request.save(request.files['file'])
        file = file_request.path(filename)
        dir_apply = current_app.config['UPLOADED_FILEREQ_DEST']
        dic_apply_filename = os.path.join(dir_apply, filename.strip('.zip'))
        if not os.path.exists(dir_apply):
            os.mkdir(dir_apply)
        if not os.path.exists(dic_apply_filename):
            os.mkdir(dic_apply_filename)
        unzip_file(file, dic_apply_filename)

        path_apply = current_app.config['APPLY_ZIP']
        # print(f'压缩包路径为: {os.path.join(os.getcwd(), file)}')
        # scp_to_108(ssh_con(),f'{os.path.join(os.getcwd(), file)}', path_apply)
        # os.remove(file)
        return {
            "code": 200,
            "message": "申请单文件上传成功!",
            "data": None
        }, 200
