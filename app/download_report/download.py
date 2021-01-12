import os
import re
import time
import zipfile
from os import path
import shutil
import pandas as pd
import requests
import json
from docxtpl import DocxTemplate, InlineImage
from datetime import timedelta, datetime

from sqlalchemy import and_
from app.models import db
from app.models.report import Report
from app.models.sample_v import PatientInfoV, FamilyInfoV, TreatInfoV, ApplyInfo, \
    SendMethodV, SampleInfoV, ReportItem
from app.models.run_info import SeqInfo, RunInfo

from pathlib import Path
from app.libs.report import first_check, get_rep_item, set_gene_list, dict2df, get_raw_file
from app.libs.get_data import read_json, splitN
from app.libs.ext import str2time, archive_file, set_time_now, archive_path, BytesIO

from flask import (render_template, Blueprint, make_response, send_from_directory, current_app, send_file, request, jsonify)
from flask_cors import CORS

home = Blueprint('home', __name__)
CORS(home)


@home.route('/')
def index():
    return 'hello'


@home.route('/api/download1/<id>_<item>_<note>/')
def download(id, item, note):
    print(id)
    dir_pre = current_app.config['PRE_REPORT']
    path_docx = os.path.join(dir_pre, 'template_docx')
    dir_res = current_app.config['RES_REPORT']
    dir_report = os.path.join(dir_res, 'report')

    dir_pgm_remplate = os.path.join(dir_pre, 'template_config', 'template_pgm.json')
    config = read_json(dir_pgm_remplate, 'config')
    gene_card = read_json(dir_pgm_remplate, 'gene_card')
    transcript = read_json(dir_pgm_remplate, 'transcript')
    dict_items = {'card': ['10', '12', '25'], 'no_card': ['52']}

    # 转录本字典
    dic_transcript = {}
    for row in transcript:
        dic_transcript[row['gene']] = row['transcript']

    if not os.path.exists(dir_report):
        os.mkdir(dir_report)

    rep_id = id

    dic_m = {}
    list_m = []
    list_card = []

    report = Report.query.filter(Report.id == rep_id).first()
    if note == '1':
        sam = report.samples[0]
        patient = sam.patient_info
        list_m = []
        dic_m['s'] = sam.to_dict()  # 样本信息
        dic_m['sp'] = sam.patient_info.to_dict()  # 病理信息
        dic_m['p'] = patient.to_dict()  # 病人信息

    else:
        if report.stage == '注释复核':
            sam = report.samples[0]
            patient = sam.patient_info
            mutation = report.mutation
            if mutation:
                snvs = mutation.snv
                cnvs = mutation.cnv
                fusions = mutation.fusion
                list_c = ['二审通过']

                first_check(snvs, list_m, list_c)
                first_check(cnvs, list_m, list_c)
                first_check(fusions, list_m, list_c)
            dic_m['s'] = sam.to_dict()  # 样本信息
            dic_m['sp'] = sam.patient_info.to_dict()  # 病理信息
            dic_m['p'] = patient.to_dict()  # 病人信息

    for cc in config:
        if item == cc['item']:
            rep_item = get_rep_item(cc['item'])
            dic_m['c'] = {'item': rep_item, '检测内容': cc['检测内容'],
                          '检测方法': cc['检测方法']}  # 报告配置文件
            list_mutation = []

            for row in cc['结果详情']:
                gene = row['基因']
                m_type = row['检测的变异类型']
                r_mutation = []

                if rep_item in dict_items['card']:
                    if list_m:
                        for mu in list_m:
                            if mu['gene'] == gene:
                                row_ir = {'result': mu['mu_name'], 'mu_af': mu['mu_af'],
                                          'mu_name_usual': mu['mu_name_usual'], 'grade': mu['grade']}
                                r_mutation.append(row_ir)
                        if r_mutation:
                            pass
                        else:
                            r_mutation = [{'result': '未检出', 'mu_af': '',
                                           'mu_name_usual': '', 'grade': ''}]
                        rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                        list_mutation.append(rep_mutation)
                    else:
                        r_mutation = [{'result': '未检出', 'mu_af': '',
                                       'mu_name_usual': '', 'grade': ''}]
                        rep_mutation = {'gene': gene, 'm_type': m_type, 'result': r_mutation}
                        list_mutation.append(rep_mutation)

                    for card in gene_card:
                        if gene == card['基因']:
                            list_card.append(card)

                    dic_m['gene_card'] = list_card  # gene card

                elif rep_item in dict_items['no_card']:
                    if list_m:
                        for mu in list_m:
                            if mu['gene'] == gene:
                                list_mutation.append(mu)
                    else:
                        list_mutation = []

            script_snv = [gene for gene in
                          splitN([{'gene': ge['基因'], 'transcript': dic_transcript.get(ge['基因'])} for ge in cc['结果详情']],
                                 3)]
            script_fusion = [gene for gene in splitN(
                [{'gene': ge['基因'], 'transcript': dic_transcript.get(ge['基因'])} for ge in cc['结果详情'] if
                 '融合' in ge['检测的变异类型']], 3)]
            script_cnv = [gene for gene in
                          splitN([{'gene': ge['基因'], 'transcript': dic_transcript.get(ge['基因'])} for ge in cc['结果详情'] if
                                  '拷贝数变异' in ge['检测的变异类型']], 3)]
            script_other = [gene for gene in
                            splitN(
                                [{'gene': ge['基因'], 'transcript': dic_transcript.get(ge['基因'])} for ge in cc['结果详情'] if
                                 ('VII' in ge['检测的变异类型'] or
                                  '14号外显子跳跃' in ge['检测的变异类型'])], 3)]
            dic_gene = {'突变': script_snv, '融合': script_fusion, '拷贝数变异': script_cnv, '跳跃': script_other}
            gene_list = []
            for k in ['突变', '拷贝数变异', '融合', '跳跃']:
                if dic_gene[k]:
                    gene_list.append({'item': k, 'list_gene': set_gene_list(dic_gene[k], 3)})

            dic_m['mutation'] = list_mutation  # 突变信息
            dic_m['gene_list'] = gene_list  # 基因列表
            dic_m['list_m'] = list_m

            if list_m:
                total_mutation = len(list_m)
                all_mu = []
                for mu in list_m:
                    all_mu.append('{} {}'.format(mu['mu_name_usual'], mu['mu_type']))
                dic_m['mu_info'] = {'total': total_mutation, 'all': '、'.join(all_mu)}
            else:
                a = [1 for ge in cc['结果详情'] if '融合' in ge['检测的变异类型']]
                note_res = '和RNA融合' if a else ''
                dic_m['note_res'] = '未检测到该样本的DNA变异' + note_res

    temp_docx = os.path.join(path_docx, '12.docx')
    file = os.path.join(dir_report, '{}.docx'.format(item))
    if os.path.exists(file):
        pass
    else:
        docx = DocxTemplate(temp_docx)
        if list_card:
            myimage = InlineImage(docx, os.path.join(path_docx, 'appendix_3.png'))
            dic_m['img'] = myimage
        else:
            dic_m['img'] = ''
        docx.render(dic_m)
        docx.save(file)

    path_rep = os.path.join(os.getcwd(), dir_report)
    return send_from_directory(path_rep, '{}.docx'.format(item), as_attachment=True)
    # return file


@home.route('/api/download/<id>_<item>_<note>/')
def download1(id, item, note):
    dir_res = current_app.config['RES_REPORT']
    dir_report = os.path.join(dir_res, 'report')
    print(dir_report)
    report = Report.query.filter(Report.id == id).first()
    sam = report.sample_info_v
    mg_id = sam.sample_id
    req_mg = sam.apply_info.req_mg
    dir_report_mg = os.path.join(dir_report, mg_id)
    now = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S")
    file_zip = '{}_{}_{}.zip'.format(req_mg, mg_id, now)

    memoryzip = archive_path(dir_report_mg)

    response = make_response(
        send_file(memoryzip, attachment_filename=file_zip, as_attachment=True, cache_timeout=5))
    return response
    # return send_from_directory(path_rep,  '{}_{}.docx'.format(mg_id,item), as_attachment=True)


@home.route('/api/download/all/<list_rep>/')
def download_all(list_rep):
    dir_res = current_app.config['RES_REPORT']
    dir_report = os.path.join(dir_res, 'report')
    list_f = []
    for row in list_rep.strip(',').split(','):
        ss = row.split('_')
        item = ss[-1]
        report = Report.query.filter(Report.id == ss[0]).first()
        sam = report.sample_info_v
        mg_id = sam.sample_id
        for file in os.listdir(os.path.join(dir_report, mg_id)):
            list_f.append(os.path.join(mg_id, file))
    #print(list_f)
    now = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S")
    file_zip = '报告_{}.zip'.format(now)
    memoryzip = archive_file(dir_report, list_f)
    path_rep = os.path.join(os.getcwd(), dir_report)
    response = make_response(
        send_file(memoryzip, attachment_filename=file_zip, as_attachment=True, cache_timeout=5))
    return response


@home.route('/api/download_okr/<filename>/')
def download_ork(filename):
    dir_res = current_app.config['RES_REPORT']
    path_res = os.path.join(dir_res, 'okr')
    file = os.path.join(path_res, '{}.xlsx'.format(filename))
    if file:
        path_rep = os.path.join(os.getcwd(), path_res)
        response = make_response(
            send_from_directory(path_rep, '{}.xlsx'.format(filename), as_attachment=True, cache_timeout=10))
        return response


@home.route('/api/download_raw/<id>_<type>/')
def download_bam(id, type):
    """
        方法名称：bam文件bai文件下载API接口
        方法描述：调用此API接口下载bam文件和bai文件
        ---
        tags:
            - PGM报告相关API接口
        parameters:
            - name: id
              in: query
              type: string
              description: 样本id

            - name: type
              in: query
              type: string
              description: 数据类型 bam、bai、lims

        responses:
            200:
                description: 文件下载成功!
    """
    report = Report.query.filter(Report.id == id).first()
    # 获取SeqInfo
    run = RunInfo.query.filter(RunInfo.name == report.run_name).first()
    seq = SeqInfo.query.filter(
        and_(SeqInfo.run_info_id == run.id, SeqInfo.sample_mg == report.req_mg, SeqInfo.report_item == report.report_item)
    ).first()
    # sam = report.sample_info_v
    # seq = sam.seq[-1]
    dic_file = get_raw_file(seq)
    # print(dic_file)
    if type == "lims":
        if str(seq.resource) != "lims":
            return jsonify({"code": 400, "message": "非lims数据不能推送lims系统!", "data": None})
        # if report.is_send_lims == "已推送":
        #     return jsonify({"code": 200, "message": "数据已推送!", "data": None})
        # zip_file = BytesIO()
        # out_date = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
        # file_name = "{}_{}.zip".format(str(seq.sample_name), out_date)
        # with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        #     if "lims_result" in dic_file.keys():
        #         with open(dic_file["lims_result"], 'rb') as fp:
        #             zf.writestr(os.path.basename(dic_file["lims_result"]), fp.read())
        #     if "lims_qc" in dic_file.keys():
        #         with open(dic_file["lims_qc"], 'rb') as fp:
        #             zf.writestr(os.path.basename(dic_file["lims_qc"]), fp.read())
        # zip_file.seek(0)
        # response = send_file(zip_file, attachment_filename=file_name, as_attachment=True, cache_timeout=5)
        report_dir = current_app.config.get("RES_REPORT")
        sample_dir = os.path.join(report_dir, "report", seq.sample_name)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0',
            "Content-Type": "application/json"
        }
        # 拷贝文件
        if os.path.isfile(dic_file["lims_result"]):
            try:
                file_name = os.path.basename(dic_file["lims_result"])
                file_name = re.sub(r'xlsx', 'xls', str(file_name))
                shutil.copy2(dic_file["lims_result"], "{}/{}".format(sample_dir, file_name))
                request_url = request.url
                url_path = re.sub(r'/api/.+$', "/api/static/res_report/report/{}/{}".format(seq.sample_name, file_name), request_url)

                url = current_app.config.get("PUSH_RESULT_LIMS")
                data = []
                libs = str(seq.libs).split("/")
                for lib in libs:
                    item = {
                        "runName": run.name,
                        "sampleCode": lib,
                        "fileNames": [
                            file_name
                        ],
                        "filePaths": [
                            url_path
                        ],
                        "readExcels": [
                            "Y"
                        ]
                    }
                    data.append(item)
                data = json.dumps(data)
                print(data)
                response = requests.post(url, data=data, headers=headers)
                res_data = json.loads(response.text)
                if response.status_code == 200:
                    res_code = res_data["code"]
                    if int(res_code) == 200:  # 推送成功
                        pass
                    else:
                        return jsonify({"code": 400, "message": "{} 推送lims系统失败!".format(res_data["msg"]), "data": None})
                else:
                    return jsonify({"code": 400, "message": "Error: {} 生信结果推送失败!".format(res_data["msg"]), "data": None})

            except Exception as error:
                print(error)
                return jsonify({"code": 400, "message": "Error: {} 生信结果推送失败!".format(error), "data": None})
        else:
            return jsonify({"code": 400, "message": "Error: 生信结果文件不存在!", "data": None})

        # 推送质控文件
        if os.path.isfile(dic_file["lims_qc"]):
            try:
                df_qc = pd.read_excel(dic_file["lims_qc"])
                df_qc.rename(columns={
                    '#Run':'runName', 'sampleCode':'', 'barcode':'Barcode', "IonXpress_044": "errorMessage",
                    "Clean_reads": "cleanReads", "Clean_bases(Mbp)": "cleanBases", "Read_length": "readLength", "insert_size": "insertSize",
                    "Q20": "q20", "Q30": "q30", "GC": "Gc", "Mapping": "mapping", "MQ17": "mq17", "On_Target": "onTarget", "Coverage": "coverage",
                    "Uniformity":"uniformity","Duplication(%)":"duplication", "Depth(X)":"depth", "Uniq_Depth":"uniqDepth",
                    "RNA_mapped_reads":"rnaMapperReads", "ExprControl_Numbers":"exprControlNumbers","配对样本是否匹配":"match", "分析版本":"version"
                }, inplace=True)
                qc = df_qc.to_dict(orient='records')
                url = current_app.config.get("PUSH_QC_LIMS")
                data = json.dumps(qc)
                print(data)
                response = requests.post(url, data=data, headers=headers)
                res_data = json.loads(response.text)
                if response.status_code == 200:
                    res_code = res_data["code"]
                    if int(res_code) == 200:  # 推送成功
                        report.is_send_lims = "已推送"
                        db.session.commit()
                        return jsonify({"code": 200, "message": "推送成功!", "data": None})
                    else:
                        return jsonify({"code": 400, "message": "Error: {} 质控文件推送失败!".format(res_data["msg"]), "data": None})
                else:
                    return jsonify({"code": 400, "message": "接口无法访问,质控文件推送失败!", "data": None})
            except Exception as e:
                print(e)
                return jsonify({"code": 400, "message": "质控文件推送失败!", "data": None})
        else:
            return jsonify({"code": 400, "message": "质控文件不存在!", "data": None})
    else:
        response = make_response(
            send_file(dic_file.get(type), as_attachment=True, cache_timeout=5)
        )
        return response


@home.route('/api/export/sampleinfo/<start>_<end>/')
def export_sample_info(start, end):
    """
        方法名称：样本信息导出API接口
        方法描述：调用此API接口样本信息导出
        ---
        tags:
            - 样本信息录入相关API接口
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
                description: 文件下载成功!
    """
    dir_res = current_app.config['RES_REPORT']
    path_excel = Path(os.path.join(os.getcwd(), dir_res)).as_posix()
    if start and end:
        start = (str2time(start))
        end = str2time(end)
        applys = ApplyInfo.query.filter(ApplyInfo.submit_time.between(start, end + timedelta(days=1))).all()


    else:
        applys = ApplyInfo.query.all()
    list_sam = []
    for apply in applys:
        dic_app = apply.to_dict()
        dic_app.pop('id')
        # print(apply.mg_id)
        pat = apply.patient_info_v
        dic_pat = pat.to_dict()
        dic_pat.pop('id')

        def formatDict(data):
            for key in data.keys():
                if isinstance(data[key], list):
                    data[key] = '、'.join(data[key])
            return data

        dic_t = {'t_name': [], 't_start': [], 't_end': [], 't_effect': []}
        dic_r = {'r_name': [], 'r_start': [], 'r_end': [], 'r_effect': []}
        dic_c = {'c_name': [], 'c_start': [], 'c_end': [], 'c_effect': []}

        for treat in pat.treat_infos:
            if treat:
                if treat.item == '靶向治疗':
                    dic_t['t_name'].append(treat.name)
                    dic_t['t_start'].append(treat.star_time)
                    dic_t['t_end'].append(treat.end_time)
                    dic_t['t_effect'].append(treat.effect)
                if treat.item == '化疗治疗':
                    dic_c['c_name'].append(treat.name)
                    dic_c['c_start'].append(treat.star_time)
                    dic_c['c_end'].append(treat.end_time)
                    dic_c['c_effect'].append(treat.effect)
                if treat.item == '放疗治疗':
                    dic_r['r_name'].append(treat.name)
                    dic_r['r_start'].append(treat.star_time)
                    dic_r['r_end'].append(treat.end_time)
                    dic_r['r_effect'].append(treat.effect)
        dic_pat.update(formatDict(dic_t))
        dic_pat.update(formatDict(dic_r))
        dic_pat.update(formatDict(dic_c))
        dic_fam = {'family': []}
        for fam in pat.family_infos:
            if fam:
                dic_fam['family'].append('{}{}{}'.format(fam.relationship, fam.age, fam.diseases))
        dic_pat.update(formatDict(dic_fam))

        dic_send = {'the_way': [], 'to': [], 'phone_n': [], 'addr': []}

        for send in apply.send_methods:
            if send:
                dic_send['the_way'].append(send.the_way)
                dic_send['to'].append(send.to)
                dic_send['phone_n'].append(send.phone_n)
                dic_send['addr'].append(send.addr)

        dic_app['rep_items'] = '、'.join([v.name for v in apply.rep_item_infos])
        dic_app.update(formatDict(dic_send))
        dic_pat.update(dic_app)

        for sam in apply.sample_infos:
            if sam:
                dic_sam = sam.to_dict()
                dic_sam.pop('id')
                dic_sam.update(dic_pat)
                list_sam.append(dic_sam)
    if len(list_sam) > 0:
        df = dict2df(list_sam)
    else:
        df = pd.DataFrame(columns=["code","sample_type","mth","mth_position",
                                   "Tytime","pnumber","receive_t","detect_t","counts","send_t","note","name","age",
                                   "gender","nation","origo","contact","ID_number","address","smoke","targeted_info","have_family",
                                   "chem_info","radio_info","family_info","treat_info","t_name","t_start","t_end","t_effect","r_name","r_start",
                                   "r_end","r_effect","c_name","c_start","c_end","c_effect","family","req_mg","seq_type","mg_id","pi_name","sales",
                                   "outpatient_id","doctor","hosptial","room","cancer","cancer_d","pathological_code","hosptial_code","original",
                                   "metastasis","pathological","pathological_date","rep_items","the_way","to","phone_n","addr"])

    start = re.sub(r'\s+|:', '_', str(start))
    end = re.sub(r'\s+|:', '_', str(end))
    xlsx_file = Path(os.path.join(path_excel, '{}_{}样本信息.xlsx'.format(start, end))).as_posix()
    xlsx_filename = os.path.basename(xlsx_file)
    df.to_excel(xlsx_file, index=False)
    return send_from_directory(path_excel, xlsx_filename, as_attachment=True, cache_timeout=10)

