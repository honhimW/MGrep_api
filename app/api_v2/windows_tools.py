import os, re, sys, time

from flask import (jsonify, current_app, make_response, send_file)
from flask_restful import (reqparse, Resource, request)

import werkzeug
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
#from win32com.client import constants, gencache
#import pythoncom

class DocxToPDF(Resource):
    """ docx转pdf """

    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('docx', required=True, type=werkzeug.datastructures.FileStorage, location='files', help="docx文件")
        super(DocxToPDF, self).__init__()

    def post(self):
        # 获取参数
        args = self.parser.parse_args()
        content = args.get('docx')
        docx_file_name = str(secure_filename(content.filename))
        dir_res = current_app.config['RES_REPORT']
        dir_res = os.path.join(dir_res, 'docx_to_pdf')
        if not os.path.exists(dir_res):
            os.makedirs(dir_res)
        tmp_dir = os.path.join(dir_res,time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()))
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        if not re.search(r'.doc(x)?$', docx_file_name):
            return {"code": 1, "msg": "文件类型错误, 只接受后缀为.doc和.docx的word文档"}
        docx_file = os.path.join(tmp_dir, docx_file_name)
        content.save(docx_file)
        pdf_file_name = re.sub(r'.doc(x)?$', '.pdf', docx_file_name)
        pdf_file = os.path.join(tmp_dir, pdf_file_name)
        try:
            self.docx_to_pdf(docx_file, pdf_file)
        except Exception as e:
            print(e)
            return {"code": 1, "msg": "Error: {} , 转换出错!".format(e)}

        response = send_file(os.path.abspath(pdf_file), attachment_filename=pdf_file_name, as_attachment=True, cache_timeout=5)
        return response

    def docx_to_pdf(self, docx_file, pdf_file):
        """ 转换docx文件为pdf文件 """
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        docx_file = os.path.abspath(docx_file)
        pdf_file = os.path.abspath(pdf_file)
        pythoncom.CoInitialize()
        word = gencache.EnsureDispatch('Word.Application')
        docx = word.Documents.Open(docx_file, ReadOnly=1)
        docx.ExportAsFixedFormat(pdf_file, constants.wdExportFormatPDF, Item=constants.wdExportDocumentWithMarkup,
                               CreateBookmarks=constants.wdExportCreateHeadingBookmarks)
        word.Quit(constants.wdDoNotSaveChanges)
