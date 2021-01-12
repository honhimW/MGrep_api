# coding: utf-8

import re
import time
import datetime
from flask import current_app
from app.libs.query import Model


class LimsApi:
    def __init__(self):
        self.model = Model(current_app.config.get("LIMS_CFG"))

    def save_result_info(self, sample_code, order_code):
        """ PGM保存结果获取信息: 家族史、治疗史  销售 """
        # 药物治疗史
        treats_history_info = self.get_treats_history(order_code)
        # 家族史
        family_history_info = self.get_family_history(order_code)
        # 申请单信息
        apply_info = self.get_apply_info(order_code)
        # 治疗史药物
        treats_history = []
        for item in treats_history_info:
            if item["MEDICINE"]:
                treats_history.append(item["MEDICINE"])
        treats_medicine = "、".join(treats_history)

        # 家族史
        family_history = ""
        for family_history_item in family_history_info:
            relation = "" if family_history_item['RELATION'] is None else family_history_item['RELATION']
            tumor = "" if family_history_item['TUMOUR'] is None else family_history_item['TUMOUR']
            family_history += "{}{}".format(relation, tumor)

        return {'treat_info': treats_medicine, 'family_info': family_history, 'sales': apply_info['销售代表']}

    def get_sample_info_v(self, sample_code, order_code):
        # 药物治疗史
        treats_history_info = self.get_treats_history(order_code)
        # 家族史
        family_history_info = self.get_family_history(order_code)
        # 申请单信息
        apply_info = self.get_apply_info(order_code)
        apply_info = {key: apply_info[key] if apply_info[key] else "" for key in apply_info.keys()}
        # 样本信息
        sample_info = self.get_sample_info(sample_code, order_code)
        sample_info = {key: sample_info[key] if sample_info[key] else "" for key in sample_info.keys()}

        # 治疗史药物
        targeted = []
        chem = []
        radio = []
        treats_history = []
        for item in treats_history_info:
            if item["MEDICINE"]:
                treats_history.append(item["MEDICINE"])
                try:
                    if int(item["EFFECTTYPE"]) == 1:
                        targeted.append(item["MEDICINE"])
                    elif int(item["EFFECTTYPE"]) == 2:
                        chem.append(item["MEDICINE"])
                    elif int(item["EFFECTTYPE"]) == 3:
                        radio.append(item["MEDICINE"])
                except Exception as e:
                    print(e)
        treats_medicine = "、".join(treats_history)
        targeted_info = "+".join(targeted)
        chem_info = "+".join(chem)
        radio_info = "+".join(radio)

        # 家族史
        family_history = ""
        for family_history_item in family_history_info:
            relation = "" if family_history_item['RELATION'] is None else family_history_item['RELATION']
            tumor = "" if family_history_item['TUMOUR'] is None else family_history_item['TUMOUR']
            family_history += "{}{}".format(relation, tumor)

        # 申请单信息
        apply = {
            'req_mg': order_code,  # 订单号
            'mg_id':  sample_code,  # 样本编号
            'seq_type': apply_info['项目类型'],  # 项目类型
            'pi_name': '',
            'sales': apply_info['销售代表'],  # 销售代表
            'outpatient_id':  apply_info['住院号门诊号'],  # 门诊号 / 住院号
            'doctor': apply_info['送检医生'],  # 送检医生
            'hosptial':  apply_info['送检医院'],  # 送检单位
            'room': apply_info['送检科室'],  # 送检科室
            'cancer': apply_info['肿瘤类型'],  # 结果解释用癌症类型
            'cancer_d': apply_info['肿瘤类型'],  # 肿瘤类型
            'pathological_code': sample_info['病理号'],  # 病理号
            'original': apply_info['原发部位'],  # 原发部位
            'metastasis': '',  # 转移部位
            'pathological': apply_info['病理诊断'],  # 病理诊断
            'pathological_date': apply_info['病理诊断日期'],  # 病理诊断日期
            'note':  apply_info['送检备注']  # 备注
        }

        # 样本信息
        sample = {
            'code': sample_code,
            'sample_type':  sample_info['样本类型'],  # 样本类型
            'mth':  sample_info['采样方式'],  # 采样方式
            'mth_position': sample_info['采集部位'],  # 采样部位
            'Tytime': sample_info['采集时间'],  # 采样时间
            'pnumber': sample_info['病理号'],  # 病理号
            'receive_t': LimsApi.deal_time(apply_info['签收时间']),  # 收样日期
            'detect_t': '',  # 检测日期
            'send_t': LimsApi.deal_time(sample_info['采集时间']),  # 送检日期
            'counts': sample_info['样本数量'],  # 样本数量
            'note': apply_info['送检备注'],  # 备注
        }

        # 病人信息
        patient = {
            'name': apply_info['患者姓名'],  # 姓名
            'age': apply_info['患者年龄'],  # 年龄
            'gender': apply_info['患者性别'],  # 性别
            'nation': apply_info['患者民族'],   # 名族
            'origo': apply_info['患者籍贯'],  # 籍贯
            'contact': apply_info['患者联系方式'],  # 联系方式
            'ID_number': apply_info['身份证号'],  # 身份证
            'address': '',  # 地址
            'smoke': apply_info['吸烟史'],   # 吸烟史
            'have_family': family_history_info,  # 家族史情况
            'targeted_info': targeted_info,  # 靶向治疗
            'chem_info': chem_info,  # 化疗
            'radio_info': radio_info  # 放疗
        }

        sam_infos = {
            'mdhistory': treats_medicine,  # 药物治疗史
            'fm': family_history,  # 家族史
            'ap': apply,  # 申请单信息
            'p': patient,  # 病人信息
            's': sample,  # 样本信息
        }
        return sam_infos

    def get_family_history(self, order_code):
        """
        获取患者家族史信息

        # 家族史信息
        # relationship: 血亲关系  diseases: 疾病     返回信息 => "血亲疾病"
        """
        sql = """
SELECT
    T_LSI_BATCH_FAMILY_HISTORY.FAMILYHISTORY AS FAMILYHISTORY, -- 家族史
    T_LSI_BATCH_FAMILY_HISTORY.RELATION AS RELATION, -- 亲属关系
    T_LSI_BATCH_FAMILY_HISTORY.AGE AS AGE, -- 确诊年龄
    T_LSI_BATCH_FAMILY_HISTORY.AGEUNIT AS AGEUNIT, -- 年龄单位
    T_LSI_BATCH_FAMILY_HISTORY.TUMOUR AS TUMOUR -- 确诊肿瘤   
FROM
    T_LSI_BATCH_FAMILY_HISTORY
    LEFT
    JOIN
    t_lsi_batch
    ON
    T_LSI_BATCH_FAMILY_HISTORY.BATCHID = t_lsi_batch.ID
WHERE
T_LSI_BATCH.BATCHCODE = '{}'
""".format(order_code)
        family_history_info = self.model.fetchAll(sql)
        # family_history = ""
        # for family_history_item in family_history_info:
        #     relation = "" if family_history_item['RELATION'] is None else family_history_item['RELATION']
        #     tumor = "" if family_history_item['TUMOUR'] is None else family_history_item['TUMOUR']
        #     family_history += "{}{}".format(relation, tumor)
        return family_history_info

    def get_treats_history(self, order_code):
        """
        获取患者药物治疗史

        # 药物治疗史信息
        # name: 药物名   返回信息 => "药物1、药物2..."
        """
        sql = """
SELECT
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.TARGETEDTHERAPYHISTORY AS TARGETEDTHERAPYHISTORY,-- 治疗史
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.MEDICINE AS MEDICINE,-- 治疗药物
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.TREATMENSTARTTIME AS TREATMENSTARTTIME,-- 治疗开始时间
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.TREATMENENDTIME AS TREATMENENDTIME,-- 治疗结束时间
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.EFFECT AS EFFECT,-- 治疗效果
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY.EFFECTTYPE AS EFFECTTYPE -- 类型(1，靶向治疗史，2，化疗史，3，放疗史)
 
FROM
 T_LSI_BATCH_TARGETED_THERAPY_HISTORY
 LEFT JOIN T_LSI_BATCH ON T_LSI_BATCH_TARGETED_THERAPY_HISTORY.BATCHID = T_LSI_BATCH.ID 
WHERE
 T_LSI_BATCH.BATCHCODE = '{}'
""".format(order_code)
        treats_history_info = self.model.fetchAll(sql)
        # treats_history = []
        # for item in treats_history_info:
        #     if item["MEDICINE"]:
        #         treats_history.append(item["MEDICINE"])
        return treats_history_info

    def get_apply_info(self, order_code):
        """
        获取患者申请单信息
        """
        sql = """
SELECT 
    BATCHCODE AS 订单编号,
    CASE WHEN ORDERTYPE = 'M' THEN '临床' WHEN 'K' THEN '科研' ELSE '未知' END AS 项目类型,
    SALESMAN AS 销售代表,
    ADMISSIONNUMBER AS 住院号门诊号,
    CUSTOMERNAME AS 送检医生,
    HOSPITAL AS 送检医院,
    DEPT AS 送检科室,
    TUMORTYPE as 肿瘤类型,
    PRIMARYFOCUS as 原发部位,
    DIAGNOSIS AS 病理诊断,
    DIAGONSISDATE as 病理诊断日期,
    INSPECTREMARKS AS 送检备注,
    SALESBARCODE AS 销售条码,
    PATIENTNAME AS 患者姓名,
    CASE WHEN PATIENTGENDER = 'male' THEN '男' WHEN 'female' THEN '女' ELSE '未知' END AS 患者性别,
    PATIENTAGE AS 患者年龄,
    NATION AS 患者民族,
    NATIVEPLACE AS 患者籍贯,
    CONTACTNUMBER AS 患者联系方式,
    IDNUMBER AS 身份证号,
    SMOKEHISTORY AS 吸烟史,
    SMOKEDURATION AS 吸烟年限,
    RECEIVINGDATE AS 签收时间
    FROM T_LSI_BATCH
    WHERE BATCHCODE = '{}'
""".format(order_code)
        apply_info = self.model.fetchRow(sql)
        # apply_info = {key: apply_info[key] if apply_info[key] else "" for key in apply_info.keys()}
        if apply_info:
            return apply_info
        else:
            return {
                "订单编号": "",
                "项目类型": "",
                "销售代表": "",
                "住院号门诊号": "",
                "送检医生": "",
                "送检医院": "",
                "送检科室": "",
                "肿瘤类型": "",
                "原发部位": "",
                "病理诊断": "",
                "病理诊断日期": "",
                "送检备注": "",
                "销售条码": "",
                "患者姓名": "",
                "患者性别": "",
                "患者年龄": "",
                "患者民族": "",
                "患者籍贯": "",
                "患者联系方式": "",
                "身份证号": "",
                "吸烟史": "",
                "吸烟年限": "",
                "签收时间": ""
            }

    def get_sample_info(self, sample_code, order_code):
        """
        获取样本信息
        """
        sql = """
SELECT DISTINCT 
 T_LSI_BATCH.BATCHCODE AS 订单编号,
 T_LSI_SAMPLE.SAMPLECODE AS 样本编号,
 T_LSI_SAMPLE_TYPE.SAMPLETYPENAME AS 样本类型,
 T_LSI_SAMPLE.DIAGONSISNO AS 病理号,
 T_CORE_CODE.CODENAME AS 采样方式,
 T_LSI_SAMPLE.COLLECTTIME AS 采集时间,
 T_LSI_SAMPLE.COLLECTLOCATION AS 采集部位,
 T_LSI_SAMPLE.SAMPLENUM AS 样本数量
FROM
 T_LSI_SAMPLE
 LEFT JOIN T_LSI_BATCH ON T_LSI_SAMPLE.BATCHID = T_LSI_BATCH.ID
 LEFT JOIN T_LSI_SAMPLE_CATEGORY ON T_LSI_SAMPLE.SAMPLECATEGORY = T_LSI_SAMPLE_CATEGORY.SAMPLECATEGORYCODE
 LEFT JOIN T_LSI_SAMPLE_TYPE ON T_LSI_SAMPLE.SAMPLETYPE = T_LSI_SAMPLE_TYPE.SAMPLETYPECODE 
 LEFT JOIN T_CORE_CODE ON T_LSI_SAMPLE.SAMPLINGMODE = T_CORE_CODE.CODE AND T_CORE_CODE.CODECATEGORYID = 'samplingMode'
WHERE
 T_LSI_SAMPLE.SAMPLECODE = '{}'
AND T_LSI_BATCH.BATCHCODE = '{}'
""".format(sample_code, order_code)

        # print(sql)
        sample_info = self.model.fetchRow(sql)
        # sample_info = {key: sample_info[key] if sample_info[key] else "" for key in sample_info.keys()}
        if sample_info:
            return sample_info
        else:
            return {
                "订单编号": "",
                "样本编号": "",
                "样本类型": "",
                "病理号": "",
                "采样方式": "",
                "采集时间": "",
                "采集部位": "",
                "样本数量": ""
            }

    def get_patient_information(self):
        """
        获取病人信息

        # 病人信息:
        # name: 姓名 age: 年龄 gender: 性别  nation： 名族  origo: 籍贯 contact: 联系方式
        # ID_number: 身份证  address: 地址  smoke: 吸烟史  have_family: 家族史情况  targeted_info: 靶向治疗
        # chem_info: 化疗信息  radio_info: 放疗信息
        """
        pass

    @staticmethod
    def deal_time(time_str):
        # 日期
        try:
            if isinstance(time_str, datetime.datetime):
                time_str = time_str.strftime('%Y-%m-%d')
            else:
                time.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                date = datetime.datetime.strptime(time_str,'%Y-%m-%d %H:%M:%S')
                time_str = date.strftime('%Y-%m-%d')
        except Exception as error:
            print(error)
        return time_str
