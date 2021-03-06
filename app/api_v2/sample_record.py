import json

from flask import (jsonify, current_app)
from flask_restful import (reqparse, Resource, fields, request)
from sqlalchemy import and_, or_

from app.models import db
from app.models.user import User
from app.models.record_config import SalesInfo, HospitalInfo, \
    SampleType, SeqItems, CancerTypes
from app.models.sample_v import PatientInfoV, FamilyInfoV, TreatInfoV, ApplyInfo, \
    SendMethodV, SampleInfoV, ReportItem
from app.libs.ext import get_local_time, get_utc_time, get_sample
from app.libs.report import del_db


class SampleInfoSearch(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('apply_id', type=int, help='申请单id')

    def get(self):
        args = self.parser.parse_args()
        apply_id = args.get('apply_id')
        # print(apply_id)
        apply = ApplyInfo.query.filter(ApplyInfo.id == apply_id).first()
        list_sample = get_sample([apply])
        # print(list_sample)
        return jsonify({'sample': list_sample})


class SampleInfoRecord(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page', type=int, help='页码')
        self.parser.add_argument('page_per', type=int, help='每页数量')
        # self.parser.add_argument('apply_id', type=int, help='申请单id')

    def get(self):
        """
        方法名称：获取样本信息
        方法描述：调用此API接口获取样本信息
        ---
        tags:
            - 样本信息录入相关API接口
        parameters:
            - name: page
              in: query
              type: integer
              required: true
              default: 1
              description: 当前页码数

            - name: page_per
              in: query
              type: integer
              required: true
              default: 10
              description: 每页条数

            - name: token
              in: header
              required: true
              description: 用户token信息

        responses:
            401:
                description: 用户名无访问权限!
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
                    example: {code: 401, message: "用户无访问权限!", data: null}
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
                    example: {
                        code: 200,
                        message: "获取信息成功!",
                        data: {
                            sample: [{age: "", age_v: "岁", cancer: "", cancer_d: "",
                            doctor: "", family_info: [{age: "", diseases: "", relationship: ""}],
                            hosptial: "惠州市第三人民医院", hosptial_code: "", id: 256, metastasis: "",
                            mg_id: "MG2001584",note: "20200412-曾恣-3545177155-HPV"},samplinfos:[],send_methods:{},seq_type: "临床",smoke_info: {is_smoke: "", smoke: ""},
                            treat_info: [{effect: "", item: "", name: "", treat_date: ""}]],
                            all_sample: [{id: 1, mg_id: "MG2001276", req_mg: "MG2036990041"}],
                            total: <total>,
                            test: {'name': 'hah'}
                        }
                    }
        """
        parser = reqparse.RequestParser()
        parser.add_argument('search', type=str, help='搜索条件')
        parser.add_argument('page', type=int, help='页码')
        parser.add_argument('page_per', type=int, help='每页数量')
        args = parser.parse_args()

        # 获取参数
        search = args.get('search')
        page = args.get('page')
        per_page = args.get('page_per')

        applys = ApplyInfo.query.filter(
            or_(
                ApplyInfo.req_mg.like('%{}%'.format(search)),
                ApplyInfo.mg_id.like('%{}%'.format(search))
            )
        ).order_by(ApplyInfo.submit_time.asc()). \
            paginate(page=page, per_page=per_page, error_out=False)
        list_apply = []
        # total = len(ApplyInfo.query.all())
        total = applys.total

        list_apply = get_sample(applys.items)
        list_all = [{'mg_id': apply.mg_id, 'req_mg': apply.req_mg, 'id': apply.id} for apply in ApplyInfo.query.all()]

        # print(list_apply)
        # print(list_all)
        return {
            "code": 200,
            "message": "获取信息成功!",
            "data": {'sample': list_apply, 'all_sample': list_all, 'total': total, 'test': {'name': 'hah'}}
        }, 200

    def post(self):
        """
        方法名称：添加样本信息
        方法描述：调用此API接口添加样本信息
        ---
        tags:
            - 样本信息录入相关API接口
        parameters:
            - name: body
              in: body
              required: true
              schema:
                required:
                    - samples
                properties:
                    samples:
                        type: array
                        description: 填写样本相关信息
                        example: [{
                            age: "", age_v: "岁", cancer: "", cancer_d: "", doctor: "",
                            family_info: [{age: "", diseases: "", relationship: ""}],
                            hosptial: "惠州市第三人民医院", hosptial_code: "", id: 256, metastasis: "",
                            mg_id: "MG2001584", note: "20200412-曾恣-3545177155-HPV", original: "",
                            outpatient_id: "", pathological: "", pathological_code: "", pathological_date: "",
                            patient_info: {ID_number: "", address: "", age: "岁", chem_info: "", contact: "",
                            family_info: "无", gender: "", …},
                            pi_name: "", rep_item: [], req_mg: "MG2049340174", room: "", sales: "赖琼英",
                            samplinfos: [{Tytime: "", code: "84", counts: "1", id: 256, mth: "", mth_position: "",
                            note: "", pnumber: "",…},…],
                            send_methods: {addr: "", id: 6, phone_n: "", the_way: "无需", to: ""},
                            seq_type: "临床", smoke_info: {is_smoke: "", smoke: ""},
                            treat_info: [{effect: "", item: "", name: "", treat_date: ""}]
                        }]
        responses:
            403:
                description: 患者姓名和申请单号未填写!
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
                    example: {code: 403, message: "请填写患者姓名和申请单号!", data: null}
            200:
                description: 样本信息添加成功!
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
                    example: {code: 200, message: "样本信息添加成功!", data: null}
        """
        data = request.get_data()
        sams = (json.loads(data)['samples'])
        for sam in sams:
            mg_id = sam['mg_id']
            req_mg = sam['req_mg']
            name = sam['patient_info']['name']
            if name and req_mg:
                pass
            else:
                return {
                    "code": 403,
                    "message": '请填写患者姓名和申请单号',
                    "data": None
                }, 403
            ID_number = sam['patient_info']['ID_number']
            code = req_mg[4:8]
            sale = SalesInfo.query.filter(SalesInfo.code == code).first()
            smoke = sam['smoke_info']['smoke'] if sam['smoke_info']['smoke'] else sam['smoke_info']['is_smoke']
            pat = PatientInfoV.query.filter(and_(PatientInfoV.ID_number == ID_number,
                                                 PatientInfoV.name == name)).first()
            if pat:
                pass
            else:
                pat = PatientInfoV(name=name, age=sam['patient_info']['age'],
                                   gender=sam['patient_info']['gender'], nation=sam['patient_info']['nation'],
                                   origo=sam['patient_info']['origo'], contact=sam['patient_info']['contact'],
                                   ID_number=ID_number, smoke=smoke, have_family=sam['patient_info']['have_family'],
                                   targeted_info=sam['patient_info']['targeted_info'],
                                   chem_info=sam['patient_info']['chem_info'],
                                   radio_info=sam['patient_info']['radio_info'])
                db.session.add(pat)
            for fam in sam['family_info']:
                if fam['relationship']:
                    family = FamilyInfoV(relationship=fam['relationship'], age=fam['age'],
                                         diseases=fam['diseases'])
                    db.session.add(family)
                    pat.family_infos.append(family)

            for treat in sam['treat_info']:
                if (treat['treat_date']):
                    start_t = treat['treat_date'][0]
                    end_t = treat['treat_date'][1]
                    treat_info = TreatInfoV(item=treat['item'], name=treat['name'], star_time=get_local_time(start_t),
                                            end_time=get_local_time(end_t), effect=treat['effect'])
                    db.session.add(treat_info)
                    pat.treat_infos.append(treat_info)

            apply = ApplyInfo.query.filter(and_(ApplyInfo.req_mg == req_mg, ApplyInfo.mg_id == mg_id)).first()
            if apply:
                pass
            else:
                apply = ApplyInfo(req_mg=req_mg, mg_id=mg_id, pi_name=sam['pi_name'], sales=sam['sales'],
                                  outpatient_id=sam['outpatient_id'], doctor=sam['doctor'], hosptial=sam['hosptial'],
                                  room=sam['room'], cancer_d=sam['cancer_d'], original=sam['original'],
                                  metastasis=sam['metastasis'], pathological=sam['pathological'],
                                  seq_type=sam['seq_type'],
                                  pathological_date=get_local_time(sam['pathological_date']), note=sam['note'])
                db.session.add(apply)
                pat.applys.append(apply)
            send_m = sam['send_methods']
            send = SendMethodV(the_way=send_m['the_way'], to=send_m['to'],
                               phone_n=send_m['phone_n'], addr=send_m['addr'])
            db.session.add(send)
            apply.send_methods.append(send)

            samples = sam['samplinfos']

            for sample in samples:

                sample_id = '{}{}'.format(mg_id, sample['code'])

                sample_info = SampleInfoV.query.filter(SampleInfoV.sample_id == sample_id).first()
                if sample_info:
                    pass
                else:
                    sample_info = SampleInfoV(sample_id=sample_id, pnumber=sample['pnumber'],
                                              sample_type=sample['sample_type'],
                                              Tytime=get_local_time(sample['Tytime']),
                                              mth=sample['mth'], mth_position=sample['mth_position'],
                                              sample_count=sample['counts'], note=sample['note'])
                    db.session.add(sample_info)
                    apply.sample_infos.append(sample_info)
            for item in sam['rep_item']:
                report_item = ReportItem.query.filter(and_(ReportItem.req_mg == req_mg,
                                                           ReportItem.name == item)).first()
                if report_item:
                    pass
                else:
                    report_item = ReportItem(req_mg=req_mg, name=item)
                    db.session.add(report_item)
                    apply.rep_item_infos.append(report_item)
            db.session.commit()

        return {
            "code": 200,
            "message": "样本信息添加成功!",
            "data": None
        }, 200

    def put(self):
        """
        方法名称：更新样本信息
        方法描述：调用此API接口更新样本信息
        ---
        tags:
            - 样本信息录入相关API接口
        parameters:
            - name: body
              in: body
              required: true
              schema:
                required:
                    - samples
                properties:
                    samples:
                        type: array
                        description: 填写样本相关信息
                        example: [{
                            age: "", age_v: "岁", cancer: "", cancer_d: "", doctor: "",
                            family_info: [{age: "", diseases: "", relationship: ""}],
                            hosptial: "惠州市第三人民医院", hosptial_code: "", id: 256, metastasis: "",
                            mg_id: "MG2001584", note: "20200412-曾恣-3545177155-HPV", original: "",
                            outpatient_id: "", pathological: "", pathological_code: "", pathological_date: "",
                            patient_info: {ID_number: "", address: "", age: "岁", chem_info: "", contact: "",
                            family_info: "无", gender: "", …},
                            pi_name: "", rep_item: [], req_mg: "MG2049340174", room: "", sales: "赖琼英",
                            samplinfos: [{Tytime: "", code: "84", counts: "1", id: 256, mth: "", mth_position: "",
                            note: "", pnumber: "",…},…],
                            send_methods: {addr: "", id: 6, phone_n: "", the_way: "无需", to: ""},
                            seq_type: "临床", smoke_info: {is_smoke: "", smoke: ""},
                            treat_info: [{effect: "", item: "", name: "", treat_date: ""}]
                        }]
        responses:
            200:
                description: 样本信息更新成功!
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
                    example: {code: 200, message: "样本信息更新成功!", data: null}
        """
        try:
            data = request.get_data()
            sams = (json.loads(data)['samples'])
            for sam in sams:
                mg_id = sam['mg_id']
                req_mg = sam['req_mg']
                pat_info = sam['patient_info']
                ID_number = pat_info['ID_number']
                code = req_mg[4:8]

                sale = SalesInfo.query.filter(SalesInfo.code == code).first()
                apply = ApplyInfo.query.filter(ApplyInfo.id == sam['id']).first()
                ApplyInfo.query.filter(ApplyInfo.id == sam['id']).update({
                    'req_mg': req_mg, 'mg_id': mg_id, 'pi_name': sam['pi_name'], 'sales': sale.name,
                    'outpatient_id': sam['outpatient_id'], 'doctor': sam['doctor'], 'hosptial': sam['hosptial'],
                    'room': sam['room'], 'cancer_d': sam['cancer_d'], 'original': sam['original'],
                    'metastasis': sam['metastasis'], 'pathological': sam['pathological'],
                    'pathological_date': get_local_time(sam['pathological_date']),
                    'note': sam['note'], 'seq_type': sam['seq_type']
                })

                smoke = sam['smoke_info']['smoke'] if sam['smoke_info']['smoke'] else sam['smoke_info']['is_smoke']
                pat = apply.patient_info_v
                PatientInfoV.query. \
                    filter(PatientInfoV.id == pat.id) \
                    .update({'name': pat_info['name'], 'gender': pat_info['gender'],
                             'nation': pat_info['nation'], 'origo': pat_info['origo'],
                             'age': pat_info['age'], 'ID_number': ID_number,
                             'smoke': smoke, 'have_family': pat_info['have_family'],
                             'targeted_info': pat_info['targeted_info'], 'chem_info': pat_info['chem_info'],
                             'radio_info': pat_info['radio_info']
                             })
                for treat in sam['treat_info']:
                    if treat['treat_date']:
                        start_t = treat['treat_date'][0]
                        end_t = treat['treat_date'][1]
                        if treat.get('id'):
                            TreatInfoV.query.filter(TreatInfoV.id == treat['id']).update({
                                'item': treat['item'], 'name': treat['name'], 'star_time': get_local_time(start_t),
                                'end_time': get_local_time(end_t), 'effect': treat['effect']
                            })
                        else:
                            treat_info = TreatInfoV(item=treat['item'], name=treat['name'],
                                                    star_time=get_local_time(start_t),
                                                    end_time=get_local_time(end_t), effect=treat['effect'])
                            db.session.add(treat_info)
                            pat.treat_infos.append(treat_info)
                for fam in sam['family_info']:
                    if fam['relationship']:
                        if fam.get('id'):
                            FamilyInfoV.query.filter(FamilyInfoV.id == fam['id']).update({
                                'relationship': fam['relationship'], 'age': fam['age'],
                                'diseases': fam['diseases']
                            })
                        else:
                            family = FamilyInfoV(relationship=fam['relationship'], age=fam['age'],
                                                 diseases=fam['diseases'])
                            db.session.add(family)
                            pat.family_infos.append(family)
                for sample in sam['samplinfos']:
                    sample_id = '{}{}'.format(mg_id, sample['code'])
                    if sample.get('id'):
                        SampleInfoV.query.filter(SampleInfoV.id == sample['id']).update({
                            'sample_id': sample_id, 'pnumber': sample['pnumber'],
                            'sample_type': sample['sample_type'],
                            'mth': sample['mth'], 'mth_position': sample['mth_position'],
                            'Tytime': get_local_time(sample['Tytime']),
                            'sample_count': sample['counts'], 'note': sample['note']
                        })
                    else:
                        sample_info = SampleInfoV(sample_id=sample_id, pnumber=sample['pnumber'],
                                                  sample_type=sample['sample_type'],
                                                  Tytime=get_local_time(sample['Tytime']),
                                                  mth=sample['mth'], mth_position=sample['mth_position'],
                                                  sample_count=sample['counts'], note=sample['note'])
                        db.session.add(sample_info)
                        apply.sample_infos.append(sample_info)
                if sam['send_methods'].get('id'):
                    SendMethodV.query.filter(SendMethodV.id == sam['send_methods']['id']).update({
                        'the_way': sam['send_methods']['the_way'], 'to': sam['send_methods']['to'],
                        'phone_n': sam['send_methods']['phone_n'], 'addr': sam['send_methods']['addr'],
                    })
                else:
                    send_m = sam['send_methods']
                    send = SendMethodV(the_way=send_m['the_way'], to=send_m['to'],
                                       phone_n=send_m['phone_n'], addr=send_m['addr'])
                    db.session.add(send)
                    apply.send_methods.append(send)
                for item in apply.rep_item_infos:
                    db.session.delete(item)
                for item in sam['rep_item']:
                    report_item = ReportItem.query. \
                        filter(and_(ReportItem.req_mg == req_mg,
                                    ReportItem.name == item)).first()
                    if report_item:
                        pass
                    else:
                        report_item = ReportItem(req_mg=req_mg, name=item)
                        db.session.add(report_item)
                        apply.rep_item_infos.append(report_item)
            db.session.commit()
        except Exception as e:
            return {'code': 400, 'message': e, 'data': None}, 400
        return {
            "code": 200,
            "message": '样本信息更新成功!',
            "data": None
        }, 200

    def delete(self):
        """
        方法名称：删除或批量删除样本信息
        方法描述：调用此API接口删除或批量删除样本信息
        ---
        tags:
            - 样本信息录入相关API接口
        parameters:
            - name: body
              in: body
              required: true
              schema:
                required:
                    - samples
                properties:
                    samples:
                        type: array
                        description: 填写样本相关信息
                        example: [{
                            age: "", age_v: "岁", cancer: "", cancer_d: "", doctor: "",
                            family_info: [{age: "", diseases: "", relationship: ""}],
                            hosptial: "惠州市第三人民医院", hosptial_code: "", id: 256, metastasis: "",
                            mg_id: "MG2001584", note: "20200412-曾恣-3545177155-HPV", original: "",
                            outpatient_id: "", pathological: "", pathological_code: "", pathological_date: "",
                            patient_info: {ID_number: "", address: "", age: "岁", chem_info: "", contact: "",
                            family_info: "无", gender: "", …},
                            pi_name: "", rep_item: [], req_mg: "MG2049340174", room: "", sales: "赖琼英",
                            samplinfos: [{Tytime: "", code: "84", counts: "1", id: 256, mth: "", mth_position: "",
                            note: "", pnumber: "",…},…],
                            send_methods: {addr: "", id: 6, phone_n: "", the_way: "无需", to: ""},
                            seq_type: "临床", smoke_info: {is_smoke: "", smoke: ""},
                            treat_info: [{effect: "", item: "", name: "", treat_date: ""}]
                        }]
        responses:
            401:
                description: 用户名无访问权限!
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
                    example: {code: 401, message: "用户无访问权限!", data: null}
            200:
                description: 样本信息删除成功!
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
                    example: {code: 200, message: "样本信息删除成功!", data: null}
        """
        token = request.headers.get('token')  # 权限
        user = User.verify_auth_token(token)
        if not user:
            return {
                "code": 401,
                "message": '用户无权限访问!',
                "data": None
            }, 401
        data = request.get_data()
        sams = (json.loads(data)['samples'])
        msgs = []
        for sam in sams:
            report = ''
            apply = ApplyInfo.query.filter(ApplyInfo.id == sam['id']).first()
            for sam in apply.sample_infos:
                if sam:
                    report = sam.report
            if report:
                msg = '申请单号为{}的信息报告需要，无法删除！！'.format(apply.req_mg)
                msgs.append(msg)
            else:
                del_db(db, apply.send_methods)
                del_db(db, apply.rep_item_infos)
                del_db(db, apply.sample_infos)
                pat = apply.patient_info_v
                del_db(db, apply.sample_infos)
                del_db(db, pat.family_infos)
                del_db(db, pat.treat_infos)
                pat.applys.remove(apply)
                db.session.delete(apply)
                db.session.delete(pat)
                db.session.commit()
                msg = '申请单号为{}的信息删除成功'.format(apply.req_mg)
                msgs.append(msg)
        return {
            "code": 200,
            "message": ','.join(msgs),
            "data": None
        }


class SalesHospitalType(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('item')

    def get(self):
        reslt = {}

        def get_info(sales):
            list_sale = []
            for sale in sales:
                list_sale.append(sale.to_dict())
            return list_sale

        reslt['sales'] = get_info(SalesInfo.query.all())
        reslt['hospital'] = get_info(HospitalInfo.query.all())
        reslt['type'] = get_info(SampleType.query.all())
        reslt['cancers'] = get_info(CancerTypes.query.all())
        reslt['seq_items'] = get_info(SeqItems.query.all())
        reslt['samples'] = get_info(ApplyInfo.query.all())
        # return jsonify({'sales': list_sale, 'hospital': list_hospital, 'type': list_type})
        return jsonify(reslt)
