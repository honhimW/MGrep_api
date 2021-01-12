from flask_restful import Api
from app.api_v2 import api_v2

my_api = Api(api_v2)

# 用户相关
from app.api_v2.user import LoginView, LoginOut, GetInfo

my_api.add_resource(LoginView, '/user/login')
my_api.add_resource(LoginOut, '/user/logout')
my_api.add_resource(GetInfo, '/user/get_info')

# 文件上传
from app.api_v2.upload import SampleInfoUpload, RunInfoUpload, MutationUpload, \
    OKRUpload, IrUpload, GeneralUpload, SampleInfoVUpload, ApplyUpload, LimsOfflineData

my_api.add_resource(SampleInfoUpload, '/upload/sample_info_upload')  # 样本信息上传
my_api.add_resource(RunInfoUpload, '/upload/run_info_upload')  # 上机信息上传
my_api.add_resource(LimsOfflineData, '/offline_data')   # lims下机数据推送
my_api.add_resource(MutationUpload, '/upload/mutation_upload/')  # 突变结果上传
my_api.add_resource(OKRUpload, '/upload/okr/')  # okr
my_api.add_resource(IrUpload, '/upload/ir_upload/')  # ir压缩包
my_api.add_resource(SampleInfoVUpload, '/upload/sample_record/') # 样本信息登记
my_api.add_resource(GeneralUpload, '/upload/general_upload/')  # 通用上传模块
my_api.add_resource(ApplyUpload, '/upload/apply/')  # 申请单上传

# 获取数据
from app.api_v2.get_data import GetAllSample, GetRunInfo, GetSeqInfo, SeqQc

my_api.add_resource(GetAllSample, '/data/get_sample_info')  # 样本信息获取
my_api.add_resource(GetRunInfo, '/data/get_run_info/')
my_api.add_resource(GetSeqInfo, '/data/get_seq_info/')
my_api.add_resource(SeqQc, '/data/seq_qc/')

# okr
from app.api_v2.okr import OkrAnnotate, OkrResult

my_api.add_resource(OkrAnnotate, '/data/okr/')
my_api.add_resource(OkrResult, '/data/okrfile/')

# admin
from app.api_v2.admin import AdminSample, AdminTemplate, AdminUser, AdminRole,\
    AdminConfig, AdminReport

my_api.add_resource(AdminSample, '/admin/sample/')
my_api.add_resource(AdminTemplate, '/admin/template/')
my_api.add_resource(AdminUser, '/admin/user/')
my_api.add_resource(AdminRole, '/admin/role/')
my_api.add_resource(AdminConfig, '/admin/config/')
my_api.add_resource(AdminReport,'/admin/report/')


# 报告
from app.api_v2.report import ReportStart, GetMutationList, ReportStage, EditMutation, \
    AnnotateMutation, AnnotateCheck, ExportReport, DownloadOkr, RgmReportInfo, DocxName, SubmitReview

my_api.add_resource(RgmReportInfo, '/report/start/')  # 开始
my_api.add_resource(GetMutationList, '/report/mutation_list/')
my_api.add_resource(ReportStage, '/report/report_stage/')  # 改变报告状态
my_api.add_resource(EditMutation, '/report/edit_mutation/')  # 编辑突变
my_api.add_resource(AnnotateMutation, '/report/annotate_mutation/')  # 突变注释
my_api.add_resource(DownloadOkr, '/report/okr/') #okr相关
# my_api.add_resource(AnnotateCheck, '/report/annotate_check/')  # 注释复核
my_api.add_resource(ExportReport, '/report/export_report/')  # 生成报告
my_api.add_resource(DocxName, '/report/report_info')  # 在线编辑office获取报告信息
my_api.add_resource(SubmitReview, '/report/review_report')  # 报告提交审核

# 前端配置

from app.api_v2.config import TemplateItem

my_api.add_resource(TemplateItem, '/config/template_item/')

# 样本录入

from app.api_v2.sample_record import SampleInfoRecord, SalesHospitalType, SampleInfoSearch

my_api.add_resource(SampleInfoRecord, '/sample_record/')
my_api.add_resource(SalesHospitalType, '/sample_record_config/')
my_api.add_resource(SampleInfoSearch, '/sample_record/search/')

# 报告自动化部分
from app.api_v2.chemo_report import SubmitChemoReview, OnlineEdit, ChemoResultsReport, ChemoUpdateDatabase, ChemoResultUpload, \
    ChemoSampleInfo, ChemoDownload, ChemoInfoSearch, SendLimsResult
my_api.add_resource(ChemoResultUpload, '/upload/chemo_result_upload/') # 化疗结果上传和报告生成
my_api.add_resource(ChemoUpdateDatabase, '/upload/chemo_db_upload/') # 化疗结果数据库上传
my_api.add_resource(ChemoSampleInfo, '/chemo_sample/') # 信息列表上传
my_api.add_resource(ChemoResultsReport, '/chemo_report/') #生成化疗报告
my_api.add_resource(ChemoDownload,'/chemo_download/')
my_api.add_resource(ChemoInfoSearch,'/chemo_search/')
my_api.add_resource(SendLimsResult, '/send_lims')  # 推送结果至lims系统
my_api.add_resource(OnlineEdit, '/chemo/online')   # 在线编辑
my_api.add_resource(SubmitChemoReview, '/chemo/review')  # 提交内审



#报告审核部分
from app.api_v2.review_report import ReviewInfoUpload, ReviewInfoGet, ReviewFormDataUpload, ReviewSearch, ReviewUser, EditNote, OnlineRead, \
                                     ReviewResultsUpdate, ReviewResultsDownload, ReviewPdfDownload, ReviewReportEmail, GetSalerInfo, ExportData, ReceiveExceptionReport

my_api.add_resource(ReviewInfoUpload, '/upload/review_info_upload/') # 报告审核信息上传
my_api.add_resource(ReviewInfoGet, '/review_report_infos/') # 信息获取
my_api.add_resource(ReviewFormDataUpload, '/review_report_formdata_upload/') #分配任务
my_api.add_resource(ReviewSearch, '/review_search/') #分配任务
my_api.add_resource(ReviewUser, '/review_user/') #用户信息
my_api.add_resource(ReviewResultsUpdate, '/upload/review_results_upload/') #上传报告结果
my_api.add_resource(ReviewResultsDownload, '/review_results_download/') #下载zip结果
my_api.add_resource(ReviewPdfDownload, '/review_pdf_download/') #下载pdf报告
my_api.add_resource(ReviewReportEmail, '/review_report_email/') #发送报告邮件
my_api.add_resource(GetSalerInfo, '/get_saler_infos/') #获取销售信息
my_api.add_resource(ExportData, '/review/export_data')  # 报告管理页面 导出数据
my_api.add_resource(EditNote, '/review/edit_note')  # 报告出具页面 修改备注
my_api.add_resource(OnlineRead, '/review/online')  # 在线审核
my_api.add_resource(ReceiveExceptionReport, '/review/exception_report')  # 接收LIMS异常报告

# Windowns系统下的工具接口
from app.api_v2.windows_tools import DocxToPDF
my_api.add_resource(DocxToPDF, '/tools/docxtopdf/') # docx文件转pdf