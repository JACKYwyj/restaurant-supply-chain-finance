"""
餐饮供应链金融平台 - 统一错误处理模块
"""

from flask import jsonify
from werkzeug.http import HTTP_STATUS_CODES
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API统一错误基类"""
    
    def __init__(self, message: str, status_code: int = 400, error_code: str = None, payload: dict = None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"error_{status_code}"
        self.payload = payload or {}
    
    def to_dict(self):
        """转换为字典"""
        rv = dict(self.payload)
        rv['error'] = self.message
        rv['code'] = self.error_code
        rv['status'] = self.status_code
        return rv
    
    def __str__(self):
        return self.message


# === 常见错误类型 ===

class ValidationError(APIError):
    """参数验证错误"""
    def __init__(self, message: str, field: str = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code='validation_error',
            payload={'field': field} if field else {}
        )


class NotFoundError(APIError):
    """资源不存在错误"""
    def __init__(self, resource: str, resource_id=None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id {resource_id} not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code='not_found',
            payload={'resource': resource, 'resource_id': resource_id}
        )


class UnauthorizedError(APIError):
    """未授权错误"""
    def __init__(self, message: str = "Authorization required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code='unauthorized'
        )


class ForbiddenError(APIError):
    """禁止访问错误"""
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message,
            status_code=403,
            error_code='forbidden'
        )


class ConflictError(APIError):
    """资源冲突错误"""
    def __init__(self, message: str, resource: str = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code='conflict',
            payload={'resource': resource} if resource else {}
        )


class RateLimitError(APIError):
    """频率限制错误"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(
            message=message,
            status_code=429,
            error_code='rate_limit_exceeded',
            payload={'retry_after': retry_after} if retry_after else {}
        )


class BusinessError(APIError):
    """业务逻辑错误"""
    def __init__(self, message: str, error_code: str = 'business_error'):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code
        )


# === 错误处理函数 ===

def register_error_handlers(app):
    """注册全局错误处理器"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        """处理自定义API错误"""
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(400)
    def handle_bad_request(error):
        """处理400错误"""
        return jsonify({
            'error': str(error.description) if hasattr(error, 'description') else 'Bad request',
            'code': 'bad_request',
            'status': 400
        }), 400
    
    @app.errorhandler(401)
    def handle_unauthorized(error):
        """处理401错误"""
        return jsonify({
            'error': 'Unauthorized',
            'code': 'unauthorized',
            'status': 401
        }), 401
    
    @app.errorhandler(403)
    def handle_forbidden(error):
        """处理403错误"""
        return jsonify({
            'error': 'Forbidden',
            'code': 'forbidden',
            'status': 403
        }), 403
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """处理404错误"""
        return jsonify({
            'error': 'Not found',
            'code': 'not_found',
            'status': 404
        }), 404
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        """处理429错误"""
        return jsonify({
            'error': 'Rate limit exceeded',
            'code': 'rate_limit_exceeded',
            'status': 429
        }), 429
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """处理500错误"""
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({
            'error': 'Internal server error',
            'code': 'internal_error',
            'status': 500
        }), 500


def handle_exceptions(f):
    """装饰器：捕获函数异常并统一处理"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            return jsonify(e.to_dict()), e.status_code
        except NotFoundError as e:
            return jsonify(e.to_dict()), e.status_code
        except UnauthorizedError as e:
            return jsonify(e.to_dict()), e.status_code
        except ForbiddenError as e:
            return jsonify(e.to_dict()), e.status_code
        except ConflictError as e:
            return jsonify(e.to_dict()), e.status_code
        except RateLimitError as e:
            return jsonify(e.to_dict()), e.status_code
        except BusinessError as e:
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'code': 'internal_error',
                'status': 500
            }), 500
    return decorated_function


def validate_required_fields(data: dict, required_fields: list) -> None:
    """验证必需字段"""
    missing = [field for field in required_fields if field not in data or data[field] is None]
    if missing:
        raise ValidationError(
            message=f"Missing required fields: {', '.join(missing)}",
            field=missing
        )


def validate_field_type(value, expected_type, field_name: str) -> None:
    """验证字段类型"""
    if not isinstance(value, expected_type):
        raise ValidationError(
            message=f"Field '{field_name}' must be of type {expected_type.__name__}",
            field=field_name
        )


def validate_positive(value, field_name: str) -> None:
    """验证正数"""
    if value is not None and value <= 0:
        raise ValidationError(
            message=f"Field '{field_name}' must be positive",
            field=field_name
        )


def validate_range(value, min_val, max_val, field_name: str) -> None:
    """验证范围"""
    if value is not None and (value < min_val or value > max_val):
        raise ValidationError(
            message=f"Field '{field_name}' must be between {min_val} and {max_val}",
            field=field_name
        )
