import os,re,time,shutil
import json
import shutil
import zipfile
import tempfile
import copy
import pandas as pd
import xlwt
import requests
import numpy as np
from io import BytesIO
from operator import itemgetter, attrgetter
from docxtpl import DocxTemplate, InlineImage, Listing

from flask_restful import (reqparse, Resource, request)
from flask import (jsonify, current_app, make_response, send_file)
from werkzeug.datastructures import FileStorage
from sqlalchemy import and_, or_

from app.models import db
from app.models.review_report import ReviewLib
from app.models.user import User
from app.models.chemo_report import ChemoDatabase, ChemoReport, ReportTemplet
from app.models.sample_v import PatientInfoV, FamilyInfoV, ApplyInfo, SampleInfoV
from app.models.record_config import CancerTypes
from app.models.run_info import RunInfo, SeqInfo

from app.libs.ext import file_sam, file_okr, file_pdf, zip_dir
from app.libs.lims import LimsApi

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

def data_to_excel(file,data):
    workbook = xlwt.Workbook(encoding = 'utf-8')
    style = xlwt.XFStyle() # 初始化样式
    font = xlwt.Font() # 为样式创建字体
    font.name = 'Times New Roman'
    #font.bold = True # 黑体
    #font.underline = True # 下划线
    #font.italic = True # 斜体字
    style.font = font # 设定样式
    for name in data.keys():
        worksheet = workbook.add_sheet(name)
        nrow=0
        for row in data[name]:
            ncol=0
            for i in row:
                worksheet.write(nrow, ncol, str(i), style) # 参数对应 行, 列, 值
                ncol+=1
            nrow+=1
    workbook.save(file)

class ChemoResultsReport(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('cancer', type=str, help='癌种')
        self.parser.add_argument('rep_temple', type=str, help='模板')
        self.parser.add_argument('mgid', type=str, help='迈景id')

    def Get_besteffect(self,eff_list):
        eff_result='-'
        if '可能较好' in eff_list and '可能一般' in eff_list:
            eff_result='可能较好'
        elif '可能相对较高' in eff_list and '可能相对适中' in eff_list:
            eff_result='可能相对较高'
        elif '可能较差' in eff_list and '可能一般' in eff_list:
            eff_result='可能较差'
        elif '可能相对较低' in eff_list and '可能相对适中' in eff_list:
            eff_result='可能相对较低'
        return(eff_result)

    def Get_subeffect(self,eff_dic):
        eff_result='-'
        a=list(eff_dic.keys())
        if len(a) == 1:
           eff_result=a[0]
        elif len(a)>2:
            eff_result='-'
        else:
            eff_result=self.Get_besteffect(a)
        return(eff_result)

    def Get_effect(self,eff_list): #根据排序好的证据，确定最终药物结果
        eff_list=sorted(eff_list,key=itemgetter(0,1))
        eff_result='无法判断'
        if len(eff_list) == 1 : #证据只有一个
            eff_result=eff_list[0][1]
        else:
            level_dic={}
            leve_hight=eff_list[0][0]
            sub_num=0
            hight_num=0
            for i in eff_list:
                if i[0] != leve_hight: #非最高证据的都为次级证据
                    i[0]='5A'
                    sub_num+=1
                else:
                    hight_num+=1
                if i[0] not in level_dic.keys():
                    level_dic[i[0]]={}
                    level_dic[i[0]][i[1]]=1
                else:
                    if i[1] not in level_dic[i[0]].keys():
                        level_dic[i[0]][i[1]]=1
                    else:
                        level_dic[i[0]][i[1]]+=1
            if leve_hight in level_dic.keys():
                hight_eff=self.Get_subeffect(level_dic[leve_hight]) #最高证据结果
                sub_eff = '-'
                if '5A' in level_dic.keys() and sub_num > 1:
                    sub_eff=self.Get_subeffect(level_dic['5A']) #次级证据结果
                if hight_eff == '-':
                    eff_result='无法判断'
                elif hight_num>1:
                    eff_result=hight_eff
                else:
                    if sub_eff == '-' or sub_eff == hight_eff: #次级证据冲突或次级证据和最高证据一致
                        eff_result=hight_eff
                    elif hight_eff == '可能一般' or hight_eff == '可能相对适中': #最高证据和次级证据不冲突，使用次级证据的极端结果
                        eff_result=sub_eff
                    elif sub_eff == '可能相对适中' or sub_eff == '可能一般': #最高证据和次级证据不冲突，使用最高级证据的极端结果
                        eff_result=hight_eff
                    else:
                        eff_result='无法判断'
        return(eff_result)

    def Get_chemo_result(self, sample_dic, cancer):
        chemo_result=[]
        cancer_chemo=[]
        for d in sorted(sample_dic.keys()):
            effect='-'
            toxic='-'
            effect_c='-'
            toxic_c='-'
            chemo_level={}
            for i in sorted(sample_dic[d],key=itemgetter(2,6,1)): #按药物效果类型、证据级别、化疗位点排序
                if i[4] and i[5]:
                    if i[2] not in chemo_level.keys():
                        chemo_level[i[2]]={}
                    if cancer in i[7] or i[7] == '泛肿瘤':
                        if 'check' not in chemo_level[i[2]].keys():
                            chemo_level[i[2]]['check']=[]
                        chemo_level[i[2]]['check'].append([i[6],i[5]])
                    else:
                        if 'nocheck' not in chemo_level[i[2]].keys():
                            chemo_level[i[2]]['nocheck']=[]
                        chemo_level[i[2]]['nocheck'].append([i[6],i[5]])
            if '药效' in chemo_level.keys():
                if 'check' in chemo_level['药效'].keys():
                    effect=self.Get_effect(chemo_level['药效']['check'])
                    effect_c=effect
                elif 'nocheck' in chemo_level['药效'].keys():
                    effect=self.Get_effect(chemo_level['药效']['nocheck'])
            if '毒理' in chemo_level.keys():
                if 'check' in chemo_level['毒理'].keys():
                    toxic=self.Get_effect(chemo_level['毒理']['check'])
                    toxic_c=toxic
                elif 'nocheck' in chemo_level['毒理'].keys():
                    toxic=self.Get_effect(chemo_level['毒理']['nocheck'])
            chemo_result.append([d,effect,toxic])
            if effect_c != '-' or toxic_c != '-':
                cancer_chemo.append([d,effect_c,toxic_c])
        return(chemo_result,cancer_chemo)

    def post(self):
        """
            方法名称：生成报告API接口
            方法描述：调用此API接口生成报告
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: mgid
                  in: query
                  type: string
                  required: true
                  description: 迈景id

                - name: cancer
                  in: query
                  type: string
                  required: true
                  description: 癌种

                - name: rep_temple
                  in: query
                  type: string
                  required: true
                  description: 报告模板

            responses:
                200:
                    description: 报告生成成功!
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
                        example: {code: 200, message: "报告生成成功!", data: null}
        """
        erro = []
        args = self.parser.parse_args()
        mgid = args.get('mgid')
        cancer = args.get('cancer')
        rep_temp = args.get('rep_temple')
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        # 报告出具增加条件限制
        review = ReviewLib.query.filter(
            and_(
                ReviewLib.mgid == mgid,
                or_(ReviewLib.pro_name.like('%化疗%'), ReviewLib.pro_name.like('%SNP%'), ReviewLib.pro_name.like('%575%'))
            )
        ).first()   # Note: 增加项目类型限制?
        if review:
            if review.status == "等待出具":
                return {"code": 400, "message": "{} 任务未分配, 请先分配任务!".format(mgid), "data": None}, 400
            elif review.reporter != user.username:
                return {"code": 400, "message": "{} 任务已分配给用户: {}".format(mgid, review.reporter), "data": None}, 400
        else:
            return {"code": 400, "message": "{} 任务未分配, 请先分配任务!".format(mgid), "data": None}, 400

        dir_pre = current_app.config['PRE_REPORT']
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'chemo_report')
        temp_doc = os.path.join(dir_pre, 'template_docx', rep_temp)

        if not os.path.exists(dir_res):
            os.mkdir(dir_res)
        info = ChemoReport.query.filter(ChemoReport.mgid == mgid).first()
        if info:
            out_date=time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
            rp_date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            sam_dir=os.path.join(dir_res,mgid)
            if os.path.exists(sam_dir):
                shutil.rmtree(sam_dir)
            os.mkdir(sam_dir)
            df = excel_to_dict(os.path.join(dir_res,'Upload',info.res_name),'SNP')
            temp_dict={}
            gt_result={}
            for row in df: #读取上传结果中的信息
                if row.get('检测位点') in gt_result.keys():
                    if row.get('检测基因型') != gt_result[row.get('检测位点')]:
                        erro.append('样本{}结果存在问题，rs{}存在两个不同的结果，请核仔细查！'.format(mgid,row.get('检测位点')))
                else:
                    gt_result[row.get('检测位点')]=row.get('检测基因型')
            #开始读取数据库信息
            data_list=db.session.query(ChemoDatabase).all()
            result_dic={}
            rs_list=[]
            for i in data_list:
                if not i.drug:
                    continue
                if re.search('SNP_ZS2_',temp_doc) and i.zs2 == '0':
                    continue
                if re.search('SNP_575_',temp_doc) and i.panle575 == '0':
                    continue
                if i.drug not in result_dic.keys():
                    result_dic[i.drug]=[]
                incancer='否'
                if cancer in i.cancer or i.cancer == '泛肿瘤':
                    incancer = '是'
                if i.rs in gt_result.keys():
                    result_dic[i.drug].append([i.gene,i.rs,i.clin_type,i.re_gt,gt_result[i.rs],'',i.level,i.cancer,i.good,i.medium,i.bed,i.anno,i.pos,incancer])
                    if i.re_gt == gt_result[i.rs]:
                        rs_list.append(['',i.gene,i.rs,i.re_gt,gt_result[i.rs],i.pos,'否'])
                    else:
                        rs_list.append(['',i.gene,i.rs,i.re_gt,gt_result[i.rs],i.pos,'是'])
                else:
                    result_dic[i.drug].append([i.gene,i.rs,i.clin_type,i.re_gt,'','',i.level,i.cancer,i.good,i.medium,i.bed,i.anno,i.pos,incancer])
                    rs_list.append(['',i.gene,i.rs,i.re_gt,'',i.pos,''])

            rs_list=set(tuple(s) for s in rs_list)
            rs_list=[list(t) for t in rs_list]
            idx=1
            for i in sorted(rs_list,key=itemgetter(1,2)):
                i[0]=idx
                idx+=1
            temp_dict['rs_list']=sorted(rs_list,key=itemgetter(0,1,2))

            for d in result_dic.keys(): #根据化疗数据库确定每个用药方案和证据的结果
                for i in result_dic[d]:
                    if i[1] in gt_result.keys():
                        i[4]=gt_result[i[1]]
                        if i[2] == '药效':
                            if gt_result[i[1]] in i[8]:
                                i[5]='可能较好'
                            elif gt_result[i[1]] in i[9]:
                                i[5]='可能一般'
                            elif gt_result[i[1]] in i[10]:
                                i[5]='可能较差'
                            else:
                                i[5]=''
                        elif i[2] == '毒理':
                            if gt_result[i[1]] in i[8]:
                                i[5]='可能相对较低'
                            elif gt_result[i[1]] in i[9]:
                                i[5]='可能相对适中'
                            elif gt_result[i[1]] in i[10]:
                                i[5]='可能相对较高'
                            else:
                                i[5]=''
            excel_data={'SNP':[],'Chemo':[]}
            for d in sorted(result_dic.keys()):  # 保存SNP对应的化疗结果
                if 'snp_list' not in temp_dict.keys():
                    temp_dict['snp_list']={}
                temp_dict['snp_list'][d]=sorted(result_dic[d],key=itemgetter(2,6,1))
                for i in sorted(result_dic[d],key=itemgetter(2,6,1)):
                    i_list=[d]
                    for t in i[0:8]:
                        i_list.append(t)
                    excel_data['SNP'].append(i_list)

            # 开始根据上传文件名获取样本信息
            temp_dict['ap'] = {}  # 申请单信息
            temp_dict['p'] = {}  # 病人信息
            temp_dict['s'] = {}  # 样本信息
            temp_dict['rp'] = {'date':rp_date, 'mgid':mgid}
            if str(review.resource) == 'lims':  # 从lims获取样本信息
                lims = LimsApi()
                sam_infos = lims.get_sample_info_v(mgid, review.req_mg)  # 参数: 样本编号 订单号
                temp_dict['ap'] = sam_infos['ap']  # 申请单信息
                temp_dict['p'] = sam_infos['p']  # 病人信息
                temp_dict['s'] = sam_infos['s']  # 样本信息
            else:
                sam_info = SampleInfoV.query.filter(SampleInfoV.sample_id == mgid).first()
                if sam_info:
                    ap_info=sam_info.apply_info
                    temp_dict['ap'] = ap_info.to_dict()
                    temp_dict['p'] = ap_info.patient_info_v.to_dict()
                    temp_dict['s'] = sam_info.to_dict()
                else:
                    erro.append('样本{}未在数据库中找到样本信息，请核查文件命名是否有误、样品信息是否上传！'.format(mgid))
            #############################################################################################

            (chemo_result, cancer_chemo) = self.Get_chemo_result(result_dic,cancer) #综合证据给出药物对应的最终疗效
            if len(chemo_result)>0:
                temp_dict['chemo_list']=sorted(chemo_result)
            if len(cancer_chemo) >0:
                temp_dict['cancer_chemo_list']=sorted(cancer_chemo)
            excel_data['Chemo']=chemo_result
            data_to_excel(os.path.join(sam_dir, '{}.result.xls'.format(mgid)),excel_data) #保存结果

            doc_temple = DocxTemplate(temp_doc)
            doc_temple.render(temp_dict)
            out_name = ''  #报告输出名称
            if 'name' in temp_dict['p'].keys() and temp_dict['p']['name']:
                out_name=temp_dict['p']['name']
            if 'req_mg' in temp_dict['ap'].keys() and temp_dict['ap']['req_mg']:
                out_name += '-{}'.format(temp_dict['ap']['req_mg'])
            else:
                out_name+=mgid
            out_name+='-SNP'
            doc_temple.save(os.path.join(sam_dir,'{}.docx'.format(out_name)))
            info.state='报告已生成'
            info.report_cancer=cancer
            info.report_dir=mgid
            info.report_date=rp_date
            info.reporter=user.username
            info.report_temp=rep_temp

        db.session.commit()
        msg='样本{}报告生成成功！'.format(mgid)
        if erro:
            msg+=','.join(erro)
        return {"code": 200, "message": msg, "data": None}, 200


class ChemoUpdateDatabase(Resource):
    def post(self):
        filename = file_sam.save(request.files['file'])
        file = file_sam.path(filename)
        list_sam = excel_to_dict(file)
        date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for row in list_sam:
            if not row.get('相关药物'):
                pass
            new = ChemoDatabase.query.filter(and_(ChemoDatabase.rs == row.get('Location'),ChemoDatabase.clin_type == row.get('疗效/毒副'),ChemoDatabase.drug == row.get('相关药物'),ChemoDatabase.level == row.get('Level of Evidence'))).first()
            if new:
                new.good=row.get('好')
                new.medium=row.get('中')
                new.bed=row.get('差')
                new.date=date
            else:
                chemo=ChemoDatabase(rs = row.get('Location'),gene = row.get('Gene'),level = row.get('Level of Evidence'),clin_type = row.get('疗效/毒副'),
                                    anno = row.get('注释翻译'),pmid = row.get('PMIDs'),re_gt = row.get('参考基因'),good = row.get('好'),medium = row.get('中'),
                                    bed = row.get('差'),note = row.get('备注'),drug = row.get('相关药物'),cancer = row.get('相关肿瘤'),date = date,mg = row.get('是否在迈景41个位点中'),
                                    zs2 = row.get('是否在中山二SNP中'),panle575 = row.get('575展示'),pos = row.get('POS'))
                db.session.add(chemo)
        db.session.commit()
        os.remove(file)
        return {'msg': '文件上传成功'}


class ChemoResultUpload(Resource):
    def post(self):
        """
            方法名称：化疗结果上传API接口
            方法描述：调用此API接口上传化疗结果
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: file
                  in: formData
                  type: file
                  required: true
                  description: 化疗结果, zip格式
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
        file = file_okr.path(filename)
        dirname= os.path.dirname(file)
        z = zipfile.ZipFile(file,'r')
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res,'chemo_report','Upload')
        if not os.path.exists(dir_res):
            os.makedirs(dir_res)
        for name in z.namelist(): #开始解压结果并生成报告
            if re.search(r'.xlsx$|.xls$',name):
                date_log=time.time()
                sample=os.path.basename(name)
                sample=sample.split('.')[0]
                sam_file=os.path.join(dir_res,name)
                if os.path.exists(sam_file):
                    os.remove(sam_file)
                z.extract(name,dir_res)
                new_file='{}.{}'.format(name,date_log)
                os.rename(sam_file,os.path.join(dir_res,new_file))
                info = ChemoReport.query.filter(ChemoReport.mgid == sample).first()
                if info:
                    info.res_name=new_file
                else:
                    chemo=ChemoReport(mgid = sample, res_name = new_file, state='结果已上传', reporter='', report_temp='', report_cancer='', report_dir='', report_date='')
                    db.session.add(chemo)
        db.session.commit()
        z.close()
        os.remove(file)
        return {"code": 200, "message": "化疗结果上传成功!", "data": None}, 200


class ChemoSampleInfo(Resource):
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
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        infos1 = ChemoReport.query.order_by(ChemoReport.submit_time.desc()).paginate(page=page, per_page=per_page, error_out=False)
        infos2 = ChemoReport.query.all()
        sample_info={}
        sample_info['total'] = len(infos2)
        sample_info['sample']=get_info(infos1.items)
        sample_info['temp']=get_info(ReportTemplet.query.filter(ReportTemplet.project == '化疗自动化').all())
        sample_info['cancers']=get_info(CancerTypes.query.all())
        return jsonify(sample_info)

    def delete(self):
        """
            方法名称：删除或批量删除数据API接口
            方法描述：调用此API接口删除或批量删除数据
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - ids
                    properties:
                        ids:
                            type: string
                            description: 样本id信息, json字符串
            responses:
                200:
                    description: 下载成功!
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
                        example: {code: 200, message: "删除成功!", data: null}
        """
        data = request.get_data()
        id_list = (json.loads(data)['ids'])
        msg=[]
        for id in id_list:
            mgid=id['mgid']
            info = ChemoReport.query.filter(ChemoReport.mgid == mgid).first()
            if info:
                dir_res = current_app.config['RES_REPORT']
                dir_res = os.path.join(dir_res,'chemo_report')
                file=os.path.join(dir_res,'Upload',info.res_name)
                if os.path.exists(file):
                    os.remove(file)
                if os.path.exists(os.path.join(dir_res, mgid)):
                    shutil.rmtree(os.path.join(dir_res, mgid))
                db.session.delete(info)
                msg.append('样品{}删除成功.'.format(mgid))
        db.session.commit()
        return {"code": 200, "message": '\n'.join(msg), "data": None}, 200


class ChemoDownload(Resource):
    def post(self):
        """
            方法名称：下载或批量下载报告API接口
            方法描述：调用此API接口下载或批量下载报告
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - ids
                    properties:
                        ids:
                            type: string
                            description: 样本id信息, json字符串
            responses:
                200:
                    description: 下载成功!
        """
        data = request.get_data()
        data = json.loads(data)['ids']
        id_list=[]
        if isinstance(data,list):
            id_list=data
        else:
            id_list.append(data)
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res,'chemo_report')
        need_file=[]
        msg=[]
        name=''
        for id in id_list:
            mgid = id['mgid']
            name = mgid
            info = ChemoReport.query.filter(ChemoReport.mgid == mgid).first()
            if info and info.state == '报告已生成':
                for root,dirs,files in os.walk(os.path.join(dir_res,mgid)):
                    for file in files:
                        need_file.append(os.path.join(mgid,file))

            else:
                msg.append('样品{}未生成相关报告,请先生成报告！'.format(mgid))
        zip_file=BytesIO()
        if id_list:
            out_date=time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
            if len(id_list) > 1:
                name='Total_Sample'
            name+='-{}.zip'.format(out_date)
            with zipfile.ZipFile(zip_file,'w',zipfile.ZIP_DEFLATED) as zf:
                    for file in need_file:
                        with open(os.path.join(dir_res,file),'rb')as fp:
                            zf.writestr(file,fp.read())
        zip_file.seek(0)
        response = send_file(zip_file, attachment_filename=name, as_attachment=True, cache_timeout=5)
        return response


class OnlineEdit(Resource):
    """ 在线编辑 """
    def get(self):
        """
            方法名称：在线编辑office获取样本信息API接口
            方法描述：调用此API接口 - 在线编辑office获取样本信息
            ---
            tags:
                - 化疗报告相关API接口
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
                        example: {code: 200,message: "获取身份信息成功!",data: {
                        "id": 5053,
                         'docx_file': 'xxx.docx',
                         'mg_id': 'MG111223', 'type': 'chemo'
                         }}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=int, help='报告id')
        args = parser.parse_args()

        # 获取参数
        report_id = args.get('id')
        report = ChemoReport.query.get(report_id)
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'chemo_report')
        report_dir = os.path.join(dir_res, str(report.report_dir))  # 报告目录
        if os.path.isdir(report_dir):
            for root, dirs, files in os.walk(report_dir, topdown=True):
                for file_name in files:
                    if re.search(r'.docx$', file_name):
                        return {"code": 200, "message": "信息获取成功!", "data": {"id": report_id, 'docx_file': file_name,
                                                                            'mg_id': str(report.report_dir), "type": "chemo"}}, 200
            return {"code": 404, "message": "迈景编号: {} 报告未找到!".format(str(report.report_dir))}, 404
        else:
            return {"code": 404, "message": "迈景编号: {} 报告目录未找到!".format(str(report.report_dir))}, 404


class SubmitChemoReview(Resource):
    """ 提交内审 """
    def post(self):
        """
            方法名称：化疗报告提交内审API接口
            方法描述：调用此API接口提交化疗报告内核
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                    properties:
                        id:
                            type: integer
                            description: 报告id
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
        args = parser.parse_args()

        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        # 获取参数
        report_id = args.get('id')
        report = ChemoReport.query.get(report_id)
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'chemo_report')
        report_dir = os.path.join(dir_res, str(report.report_dir))  # 报告目录
        if report.is_send_lims != "已推送":
            return {"code": 400, "message": "报告结果未推送lims系统, 请先推送lims系统!", "data": None}, 400

        review = ReviewLib.query.filter(
                 and_(
                     ReviewLib.mgid == report.mgid,
                     or_(ReviewLib.pro_name.like('%化疗%'), ReviewLib.pro_name.like('%SNP%'), ReviewLib.pro_name.like('%575%'))
                 )
        ).first()
        if not review:
            return {"code": 400, "message": "报告审核信息未上传, 请先上传审核信息!", "data": None}, 400
        else:
            if review.status == "等待出具":
                return {"code": 400, "message": "该报告未分配任务, 请指定报告出具人!", "data": None}, 400
            elif review.reporter != user.username:
                return {"code": 400, "message": "该报告已分配给用户: {}!".format(review.reporter), "data": None}, 400

        try:  # 提交内审
            dir_res = current_app.config['RES_REPORT']
            review_dir = os.path.join(dir_res, 'Review_Results')  # 报告审核后的上传目录
            review_report_dir = os.path.join(review_dir, str(review.id))
            if not os.path.isdir(review_report_dir):
                os.makedirs(review_report_dir)
            # 报告提交到审核目录并压缩
            os.system("cp -r %s %s" % (report_dir, review_report_dir))
            review_report_dir = os.path.join(review_report_dir, str(report.report_dir))
            zip_dir(review_report_dir)
            review.report_file = str(report.report_dir) + ".zip"
        except Exception as e:
            print(e)
            return {"code": 400, "message": "提交审核失败!", "data": None}, 400
        # 修改审核状态
        review.status = '内审中'
        db.session.commit()

        report.state = "已提交审核"
        db.session.commit()

        return {"code": 200, "message": "提交审核成功!", "data": None}, 200


class SendLimsResult(Resource):
    """ 推送结果至lims系统 """
    def post(self):
        """
            方法名称：推送分析结果至lims系统API接口
            方法描述：调用此API接口推送分析结果至lims系统
            ---
            tags:
                - 化疗报告相关API接口
            consumes:
                - application/json
            parameters:
                - name: body
                  in: body
                  required: true
                  schema:
                    required:
                        - id
                    properties:
                        id:
                            type: string
                            description: 化疗报告id
            responses:
                200:
                    description: 推送成功!
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
                        example: {code: 200, message: "推送成功!", data: null}
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, help='报告id')
        args = parser.parse_args()

        report_id = args.get('id')
        report = ChemoReport.query.get(report_id)
        if not report:
            return {"code": 400, "message": "Error: id %s, 报告信息未查询到!"%(report_id), "data": None}, 400

        dir_res = current_app.config['RES_REPORT']
        chemo_dir = os.path.join(dir_res, 'chemo_report')
        upload_dir = os.path.join(dir_res, 'chemo_report', 'Upload')
        upload_file = os.path.join(upload_dir, report.res_name)
        if not os.path.isfile(upload_file):
            return {"code": 400, "message": "Error: id %s, 上传结果文件不存在!"%(report_id), "data": None}, 400
        mgid = report.mgid
        sample_dir = os.path.join(chemo_dir, mgid)
        if not os.path.isdir(sample_dir):
            try:
                os.makedirs(sample_dir)
            except Exception as error:
                print(error)
                return {"code": 400, "message": "Error: %s 创建样本目录失败!", "data": None}, 400

        title = [
            "vartype", "chr", "start", "end", "ref", "alt", "gene", "transcript",
            "exon", "chgvs", "phgvs3", "phgvs1", "chr_2", "start_2", "end_2", "gene_2",
            "transcript_2", "exon_2", "function", "MAX_AF", "COSMIC", "ClinVar", "dbSNP",
            "Hotspot", "AF", "AD", "Molecular template number", "Depth", "TMB_result",
            "MSI_site", "MSI_result", "CN", "ISCN", "Break_support1", "Break_support2",
            "Mutation_Type", "manual_check"]
        df_lims = pd.DataFrame(title)
        # 读取文件
        try:
            df = pd.read_excel(upload_file, sheet_name="SNP")
        except Exception as error:
            return {"code": 400, "message": "Error: %s 读取结果文件失败!"%(error)}, 400

        file_title = df.columns.values.tolist()
        for item in ["参考基因组位置(hg19)", "参考基因型(野生型)", "检测基因型", "检测位点", "基因"]:
            if not item in file_title:
                return {"code": 400, "message": "Error: %s 结果文件不存在表头!"%(item), "data": None}, 400

        for index in df.index.values:
            row = df.loc[index, :].to_dict()
            row_lims = {item: '.' for item in title}
            (chrom, position) = row["参考基因组位置(hg19)"].split(":")
            vartype = "SNV"
            if row["检测位点"] == "rs151264360" and str(row["是否检出突变"]) == "是":
                vartype = "DEL"
            elif row["检测位点"] == "rs8175347" and str(row["是否检出突变"]) == "是":
                vartype = "DEL"

            row_lims["chr"] = chrom
            row_lims["start"] = position
            row_lims["end"] = position
            row_lims["ref"] = row["参考基因型(野生型)"]
            row_lims["alt"] = row["检测基因型"]
            row_lims["dbSNP"] = row["检测位点"]
            row_lims["gene"] = row["基因"]
            row_lims["vartype"] = vartype
            df_lims = df_lims.append(row_lims, ignore_index=True)
        # 保存结果
        try:
            df_lims.to_excel("%s/%s.lims.xls"%(sample_dir, mgid))
        except Exception as error:
            return {"code": 400, "message": "Error: %s, %s 保存结果失败!"%(error, mgid), "data": None}, 400

        # 获取信息
        info = SeqInfo.query.filter(
            and_(
                SeqInfo.sample_name == mgid,
                or_(SeqInfo.report_item.like('%化疗%'), SeqInfo.report_item.like('%SNP%'))
            )
        ).first()
        if info:
            if str(info.resource) != "lims":
                return {"code": 400, "message": "非lims数据不能推送lims系统!", "data": None}, 400
            request_url = request.url
            url_path = re.sub(r'/api/.+$', "/api/static/res_report/chemo_report/{}/{}.lims.xls".format(mgid, mgid), request_url)
            url = current_app.config.get("PUSH_RESULT_LIMS")   # 推送分析结果到lims系统接口
            run_info = RunInfo.query.get(info.run_info_id)
            run_name = run_info.name
            data = []
            libs = str(info.libs).split("/")
            for lib in libs:
                item = {
                    "runName": run_name,
                    "sampleCode": lib,
                    "fileNames": [
                        "{}.lims.xls".format(mgid)
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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0',
                "Content-Type": "application/json"
            }
            response = requests.post(url, data=data, headers=headers)
            res_data = json.loads(response.text)
            if response.status_code == 200:
                res_code = res_data["code"]
                if int(res_code) == 200:  # 推送成功
                    report.is_send_lims = "已推送"
                    db.session.commit()
                    return {"code": 200, "message": "推送成功!", "data": None}, 200
                else:
                    return {"code": 400, "message": "{} 推送lims系统失败!".format(res_data["msg"]), "data": None}, 400
            else:
                return {"code": 400, "message": "Error: {} 生信结果推送失败!".format(res_data["msg"]), "data": None}, 400
        else:
            return {"code": 400, "message": "Error: %s 获取run信息失败!"%(mgid), "data": None}, 400


class ChemoInfoSearch(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=str, help='关键词')
        self.parser.add_argument('page', type=int, default=1, help='页码')
        self.parser.add_argument('page_per', type=int, default=10, help='每页数量')
        self.parser.add_argument('ids', help='迈景id')

    def get(self):
        """
            方法名称：获取化疗报告信息API接口
            方法描述：调用此API接口获取化疗报告信息
            ---
            tags:
                - 化疗报告相关API接口
            parameters:
                - name: search
                  in: query
                  type: string
                  description: 搜索内容 - 默认为''

                - name: page
                  in: query
                  type: integer
                  description: 当前页码

                - name: page_size
                  in: query
                  type: integer
                  description: 每页的数据条数

            responses:
                200:
                    description: 获取化疗报告信息成功!
                    schema:
                        properties:
                            code:
                                type: integer
                            message:
                                type: string
                            data:
                                type: object
                        example: {code: 200,message: "获取化疗报告信息成功!",data: {
                                    cancers:[{id: 1, name: "直肠癌", okr_name: "colorectal cancer"}],
                                    sample: [{id: 2, mgid: "MG2002633", report_cancer: "非小细胞肺癌", report_date: "2020-08-24 14:10:34", report_dir: "MG2002633", report_temp: "SNP_v1.docx", reporter: "报告", res_name: "MG2002633.xlsx.1592190984.8617942", state: "报告已生成"}],
                                    temp: [{doc_template: "SNP_v1.docx", id: 1, name: "化疗报告", note: "", project: "化疗自动化", version: "V1.0"}]
                                }
                            }
        """
        args = self.parser.parse_args()
        id = args.get('id')
        page = args.get('page')
        per_page = args.get('page_per')

        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

        infos = ChemoReport.query.filter(ChemoReport.mgid.like('%{}%'.format(id))).all()
        sample_info = {}
        all_sample_list = get_info(infos)
        filter_sample_list = []

        # 只显示当前用户需要出具的报告
        for item in all_sample_list:
            review = ReviewLib.query.filter(
                and_(
                    ReviewLib.mgid == item["mgid"],
                    or_(ReviewLib.pro_name.like('%化疗%'), ReviewLib.pro_name.like('%SNP%'), ReviewLib.pro_name.like('%575%'))
                )
            ).first()
            # and (review.status == "出具中" or review.status == "审核未通过")
            if review and str(review.reporter) == user.username and (review.status == "出具中" or review.status == "审核未通过"):  # 分配给当前用户的报告
                item["reporter"] = review.reporter
                item["rep_reviewer"] = review.rep_reviewer
                item["med_reviewer"] = review.med_reviewer
                filter_sample_list.append(item)
        offset = (int(page) - 1) * int(per_page)
        limit = int(per_page)
        sample_info["total"] = len(filter_sample_list)
        sample_info["sample"] = filter_sample_list[offset:limit]
        sample_info['temp']=get_info(ReportTemplet.query.filter(ReportTemplet.project == '化疗自动化').all())
        sample_info['cancers']=get_info(CancerTypes.query.all())
        # return jsonify(sample_info)
        return {"code": 200, "message": "获取化疗报告信息成功!", "data": sample_info}, 200

