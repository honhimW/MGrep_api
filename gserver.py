from gevent.pywsgi import WSGIServer
from gevent import monkey
from app import create_app

monkey.patch_all()
app = create_app('app.config.ProdConfig')

server = WSGIServer(('0.0.0.0',5002),app)
server.serve_forever()
