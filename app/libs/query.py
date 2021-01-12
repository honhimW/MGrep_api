
import sys
import pymysql

class Model():
  '''
    mysql model 类, 提供访问mysql的接口
  '''

  # 1. 单例模式, 用于保存对象的内存地址 None
  instance = None

  # 2. 记录初始化的动作是否被执行, 默认值为 False
  init_flag = False

  def __init__(self,cfg):
    # 判断初始化动作是否被执行
    if Model.init_flag is True:
      return
    # 初始化参数
    self.__initConfig(cfg)
    # 连接数据库
    self.__my_connect()
    # 选择默认字符集
    self.__my_charset()
    # 修改初始化动作标记
    Model.init_flag = True

  def __new__(cls, *args, **kwargs):

    # 1. 判断对象是否被创建
    if cls.instance is None:
      cls.instance = super().__new__(cls)
    # 2. 返回对象的内存地址
    return cls.instance


  def __initConfig(self, cfg):
    # 初始化参数
    self.host    = cfg['host'] if 'host' in cfg.keys() else 'localhost'
    self.port    = cfg['port'] if 'port' in cfg.keys() else 3306
    self.user    = cfg['user'] if 'user' in cfg.keys() else 'root'
    self.passwd  = cfg['passwd'] if 'passwd' in cfg.keys() else ''
    self.charset = cfg['charset'] if 'charset' in cfg.keys() else 'utf8'
    self.dbname  = cfg['dbname'] if 'dbname' in cfg.keys() else ''


  ## 连接数据库
  def __my_connect(self):
    try:
      self.link=pymysql.connect(
        host=self.host, user=self.user, port=self.port, passwd=self.passwd, db=self.dbname,
        cursorclass=pymysql.cursors.DictCursor)
    except Exception as e:
      print("数据库连接失败: %s"% e)
      sys.exit(1)

    self.cursor = self.link.cursor()


  ## 执行一条sql语句
  def my_query(self,sql):
    try:
      self.cursor.execute(sql)
      self.link.commit()
    except Exception as e:
      print("sql语句执行失败: %s\n报错信息: %s"%(sql,e))
      return False
    else:
      return True
  

  ## 执行sql语句,返回所有结果
  def fetchAll(self, sql):
    if self.my_query(sql) is True:
      result = self.cursor.fetchall()
      return result
    else:
      return False


  ## 执行sql语句, 返回一条结果
  def fetchRow(self,sql):
    if self.my_query(sql) is True:
      result =  self.cursor.fetchone()
      return result
    else:
      return False


  ## 执行sql语句, 返回单行单列结果
  def fetchColumn(self, sql, field):
    if self.my_query(sql) is True:
      row = self.cursor.fetchone()
      return row[field] if field in row.keys() else False
    else:
      return False
  

  ## 选择默认数据集
  def __my_charset(self):
    sql = "set names %s"%(self.charset)
    self.my_query(sql)

  ## 析构方法, 关闭数据库
  def __del__(self):
    self.link.close()
