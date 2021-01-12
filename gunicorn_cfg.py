import multiprocessing

bind = '192.168.1.103:5002'
workers = multiprocessing.cpu_count()  + 1

backlog = 2048
worker_class = "gevent"
worker_connections = 1000
daemon = False
debug = True
proc_name = 'gunicorn_flask'
pidfile = './log/gunicorn.pid'
errorlog = './log/gunicorn.log'
