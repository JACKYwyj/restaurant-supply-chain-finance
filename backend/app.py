"""
餐饮供应链金融平台 - Flask主应用
"""

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
from datetime import datetime
import os

from config import config
from models import db


# API文档配置
SWAGGER_TEMPLATE = {
    "info": {
        "title": "餐饮供应链金融赋能平台API",
        "description": """
## 接口版本
当前版本: **v1.0**

## 认证方式
除 `/api/v1/auth/register` 和 `/api/v1/auth/login` 外，所有接口需要在Header中携带JWT Token:
```
Authorization: Bearer <your_jwt_token>
```

## 速率限制
| 端点类型 | 限制 |
|---------|------|
| 认证接口 (登录/注册) | 10次/分钟 |
| 数据查询接口 | 60次/分钟 |
| 数据写入接口 | 30次/分钟 |
| 通用接口 | 100次/天, 20次/小时 |

## 错误码说明
| 错误码 | 说明 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未授权/Token无效 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
        """,
        "version": "1.0.0",
        "contact": {
            "name": "API Support",
            "email": "support@example.com"
        }
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Token: Bearer <your_token>"
        }
    },
    "responses": {
        "Unauthorized": {
            "description": "未授权或Token无效",
            "examples": {
                "application/json": {
                    "error": "Invalid token",
                    "code": "invalid_token"
                }
            }
        },
        "NotFound": {
            "description": "资源不存在",
            "examples": {
                "application/json": {
                    "error": "Merchant not found"
                }
            }
        },
        "RateLimitExceeded": {
            "description": "请求频率超限",
            "examples": {
                "application/json": {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests"
                }
            }
        }
    }
}


def create_app(config_name=None):
    """应用工厂函数"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))
    
    # 初始化扩展
    db.init_app(app)
    jwt = JWTManager(app)
    
    # CORS配置 - 使用配置文件中的 origins
    cors_origins = app.config.get('CORS_ORIGINS', ['*'])
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # Rate Limiting配置
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[app.config.get('RATELIMIT_DEFAULT', '100 per day, 20 per hour').split(',')],
        storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://'),
        enabled=app.config.get('RATELIMIT_ENABLED', True)
    )
    
    # Swagger文档配置
    swagger = Swagger(app, template=SWAGGER_TEMPLATE)
    
    # 注册蓝图 - 使用v1版本前缀
    from api.auth import auth_bp
    from api.merchant import merchant_bp
    from api.credit import credit_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(merchant_bp, url_prefix='/api/v1/merchant')
    app.register_blueprint(credit_bp, url_prefix='/api/v1/credit')
    
    # 健康检查
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    
    # 根路由
    @app.route('/', methods=['GET'])
    def index():
        return jsonify({
            'name': '餐饮供应链金融赋能平台API',
            'version': '1.0.0',
            'api_version': 'v1',
            'endpoints': {
                'auth': '/api/v1/auth',
                'merchant': '/api/v1/merchant',
                'credit': '/api/v1/credit',
                'health': '/health',
                'api_docs': '/apidocs'
            }
        }), 200
    
    # API文档入口
    @app.route('/apidocs', methods=['GET'])
    def api_docs():
        """API文档入口"""
        return jsonify({
            'message': '访问 /apidocs/index.html 查看Swagger文档',
            'swagger_ui': '/apidocs/index.html',
            'swagger_json': '/apidocs/swagger.json',
            'redoc': '/apidocs/redoc'
        }), 200
    
    # JWT错误处理
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token has expired',
            'code': 'token_expired'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': 'Invalid token',
            'code': 'invalid_token'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': 'Authorization required',
            'code': 'authorization_required'
        }), 401
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app


# 应用实例
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
