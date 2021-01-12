from flask_restful import (reqparse, Resource)
from flask import (jsonify, current_app)
from flask_login import (login_user, logout_user, current_user)
from flask_principal import Identity, identity_changed

from app.models.user import User


class LoginView(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('userName', required=True,
                                 help='请输入用户名')
        self.parser.add_argument('password', required=True,
                                 help='请输入密码')
        # self.parser.add_argument('token',type=str, required=True,
        #                          help='token')
        super(LoginView, self).__init__()

    def get(self):
        return jsonify({'data': '你好啊Vue,来自FLASK的问候!'})

    def post(self):
        """
        方法名称：登录系统API接口
        方法描述：调用此API接口登录系统
        ---
        tags:
            - 用户相关API接口
        consumes:
            - application/json
        parameters:
            - name: body
              in: body
              required: true
              schema:
                required:
                    - userName
                    - password
                properties:
                    userName:
                        type: string
                        description: 填写用户帐号
                    password:
                        type: string
                        description: 填写用户密码
        responses:
            401:
                description: 用户名或密码错误!
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
                    example: {code: 401, message: "用户名或密码错误!", data: null}
            200:
                description: 用户登录成功!
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
                    example: {code: 200, message: "系统登录成功!", data: {token: <token>}}
        """
        args = self.parser.parse_args()
        username = args.get('userName')
        password = args.get('password')
        user = User.query.filter_by(
            username=username
        ).first()
        # return 'hello'
        if user and user.check_password(password):
            login_user(user)
            identity_changed.send(
                current_app._get_current_object(),
                identity=Identity(user.id)
            )
            # 登录成功
            return {
                'code': 200,
                'message': '用户登录成功!',
                'data': {'token': user.generate_auth_token().decode('ascii')}
            }, 200
        else:
            return {
                'code': 401,
                'message': '用户名或密码不正确!',
                'data': None
            }, 401


class LoginOut(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('token', type=str, required=True,
                                 help='token')
        super(LoginOut, self).__init__()

    def get(self):
        return jsonify({'data': '你好啊Vue,来自FLASK的问候!'})

    def post(self):
        """
        方法名称：注销登录系统API接口
        方法描述：调用此API接口注销
        ---
        tags:
            - 用户相关API接口
        consumes:
            - application/json
        parameters:
            - name: body
              in: body
              required: true
              schema:
                required:
                    - token
                properties:
                    token:
                        type: string
                        description: 填写token验证信息
        responses:
            200:
                description: 注销登录成功!
                schema:
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {code: 200, message: "注销登录成功!", data: null}
        """
        # args = self.parser.parse_args()
        # token = args.get('token')
        return {
            'code': 200,
            'message': '注销登录成功!',
            'data': None
        }, 200


class GetInfo(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('token', type=str, required=True,
                                 help='token')
        super(GetInfo, self).__init__()

    def get(self):
        """
        方法名称：获取用户相关信息API接口
        方法描述：调用此API接口获取用户的相关信息
        ---
        tags:
            - 用户相关API接口
        parameters:
            - name: token
              in: query
              required: true
              type: string
              description: token验证

        responses:
            401:
                description: 用户身份验证失败!
                schema:
                    properties:
                        code:
                            type: integer
                        message:
                            type: string
                        data:
                            type: object
                    example: {code: 401, message: "身份验证失败!", data: null}
            200:
                description: 获取用户身份信息成功!
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
                            message: "获取身份信息成功!",
                            data: {
                                'name': 'zs',
                                'user_id': 1,
                                'access':[],
                                'token': '<token>',
                                'avator': 'https://avatars0.githubusercontent.com/u/20942571?s=460&v=4'
                            }
                        }
        """
        args = self.parser.parse_args()
        token = args.get('token')
        user = User.verify_auth_token(token)

        if user:
            user_info = {'name': user.username,
                         'user_id': user.id,
                         'access': [role.name for role in user.roles],
                         'token': token,
                         'avator': 'https://avatars0.githubusercontent.com/u/20942571?s=460&v=4'}
            return {
                'code': 200,
                'message': '获取身份信息成功!',
                'data': user_info
            }, 200
        else:
            return {"code": 405, "message": "无访问权限!", "data": None}, 405

