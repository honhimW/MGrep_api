from flata import Flata
from flata.storages import JSONStorage
import json


def read_json(path_db, table_name):
    '''
    :param path_db: json文件路径
    :return:
    '''
    try:
        db = Flata(path_db, storage=JSONStorage)
        tb = db.table(table_name)
        dic = tb.all()
    except Exception as e:
        print(e)
        with open(path_db, 'r', encoding='utf-8') as io:
            json_str = io.read()
            res = json.loads(json_str)
            dic = res[table_name]
    return dic


def splitN(listS, n):
    '''
    切割列表
    :param listS: 要切割的列表
    :param n: 每份多少个
    :return: 被切分的列表
    '''
    for i in range(0, len(listS), n):
        yield listS[i:i + n]

def dic_to_df(dic):
    pass