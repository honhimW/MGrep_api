import os

from flask import (jsonify, current_app)
from flask_restful import (reqparse, Resource, fields, request)

from app.models import db
from app.libs.get_data import read_json, splitN


class TemplateItem(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('resource', type=str, help='数据来源')
        args = parser.parse_args()

        # 获取参数
        resource = args.get('resource')
        dir_app = current_app.config['PRE_REPORT']
        if str(resource) == 'lims':  # 数据来源lims
            dir_pgm_remplate = os.path.join(dir_app, 'template_config', 'template_pgm_lims.json')
        else:
            dir_pgm_remplate = os.path.join(dir_app, 'template_config', 'template_pgm.json')
        config = read_json(dir_pgm_remplate, 'config')
        gene_card = read_json(dir_pgm_remplate, 'gene_card')
        transcript = read_json(dir_pgm_remplate, 'transcript')

        template_item = {'item': [{'value': cc['item'], 'label': cc['item']} for cc in config]}
        return jsonify(template_item)

