"""
请求ID追踪模块
为每个HTTP请求生成唯一追踪ID
"""

import uuid
import threading
from flask import request, g, has_request_context
from functools import wraps

# 线程本地存储 - 用于在同线程内获取当前请求ID
_thread_local = threading.local()


def generate_request_id():
    """生成唯一的请求ID"""
    return uuid.uuid4().hex[:16]


def get_request_id():
    """获取当前请求的ID"""
    if has_request_context():
        return getattr(g, 'request_id', '-')
    return getattr(_thread_local, 'request_id', '-')


def set_request_id(request_id):
    """设置当前请求的ID"""
    if has_request_context():
        g.request_id = request_id
    else:
        _thread_local.request_id = request_id


class RequestIDMiddleware:
    """请求ID中间件 - 为每个请求分配唯一ID"""
    
    def __init__(self, app=None, header_name='X-Request-ID'):
        self.app = app
        self.header_name = header_name
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        self.header_name = app.config.get('REQUEST_ID_HEADER', 'X-Request-ID')
        
        @app.before_request
        def before_request():
            # 优先使用请求头中的ID（如有）
            request_id = request.headers.get(self.header_name)
            if not request_id:
                request_id = generate_request_id()
            
            set_request_id(request_id)
            g.request_start_time = None
            g.request_start_time = getattr(request, 'start', None)
            
            # 将request_id添加到请求上下文
            g.request_id = request_id
        
        @app.after_request
        def after_request(response):
            # 在响应头中添加request_id
            if has_request_context():
                request_id = get_request_id()
                response.headers[self.header_name] = request_id
            return response
        
        @app.teardown_request
        def teardown_request(exception=None):
            # 清理线程本地存储
            if not has_request_context():
                _thread_local.request_id = None


def with_request_id(func):
    """装饰器 - 确保函数可以访问当前请求ID"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 在日志中自动添加request_id
        return func(*args, **kwargs)
    return wrapper


# 请求ID的工具函数集合
request_id_utils = {
    'generate': generate_request_id,
    'get': get_request_id,
    'set': set_request_id,
    'middleware': RequestIDMiddleware
}
