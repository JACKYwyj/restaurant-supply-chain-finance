"""
性能监控中间件
监控请求处理时间、内存使用、数据库查询等指标
"""

import time
import psutil
import threading
from flask import request, g, jsonify, has_request_context
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控类"""
    
    def __init__(self, app=None):
        self.app = app
        self.request_count = defaultdict(int)
        self.request_times = defaultdict(list)
        self.error_count = defaultdict(int)
        self.slow_requests = []
        self._lock = threading.Lock()
        self.slow_threshold = 1.0  # 慢请求阈值（秒）
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        self.slow_threshold = app.config.get('SLOW_REQUEST_THRESHOLD', 1.0)
        
        @app.before_request
        def before_request():
            g.request_start_time = time.time()
            g.query_count = 0
        
        @app.after_request
        def after_request(response):
            if has_request_context() and hasattr(g, 'request_start_time'):
                duration = time.time() - g.request_start_time
                endpoint = request.endpoint or 'unknown'
                method = request.method
                
                with self._lock:
                    # 记录请求次数
                    self.request_count[f"{method}:{endpoint}"] += 1
                    
                    # 记录响应时间
                    self.request_times[f"{method}:{endpoint}"].append(duration)
                    
                    # 保留最近1000条记录
                    if len(self.request_times[f"{method}:{endpoint}"]) > 1000:
                        self.request_times[f"{method}:{endpoint}"] = \
                            self.request_times[f"{method}:{endpoint}"][-1000:]
                    
                    # 记录慢请求
                    if duration > self.slow_threshold:
                        self.slow_requests.append({
                            'timestamp': datetime.utcnow().isoformat(),
                            'method': method,
                            'endpoint': endpoint,
                            'path': request.path,
                            'duration': duration,
                            'status': response.status_code,
                            'request_id': getattr(g, 'request_id', '-')
                        })
                        
                        # 只保留最近100条慢请求
                        if len(self.slow_requests) > 100:
                            self.slow_requests = self.slow_requests[-100:]
                        
                        logger.warning(
                            f"Slow request detected: {method} {request.path} took {duration:.3f}s"
                        )
                    
                    # 记录错误
                    if response.status_code >= 400:
                        self.error_count[f"{method}:{endpoint}"] += 1
                
                # 添加性能头信息
                response.headers['X-Response-Time'] = f'{duration:.3f}s'
            
            return response
        
        # 性能指标端点
        @app.route('/metrics', methods=['GET'])
        def metrics():
            """性能指标端点"""
            return jsonify(self.get_stats()), 200
    
    def get_stats(self):
        """获取性能统计"""
        stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'requests': {},
            'errors': {},
            'system': self.get_system_stats(),
            'slow_requests': self.slow_requests[-10:]  # 最近10条慢请求
        }
        
        with self._lock:
            # 计算每个端点的统计数据
            for key, times in self.request_times.items():
                if times:
                    stats['requests'][key] = {
                        'count': self.request_count[key],
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'p50': self._percentile(times, 50),
                        'p95': self._percentile(times, 95),
                        'p99': self._percentile(times, 99)
                    }
            
            stats['errors'] = dict(self.error_count)
        
        return stats
    
    def get_system_stats(self):
        """获取系统资源使用情况"""
        try:
            process = psutil.Process()
            return {
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'memory_percent': process.memory_percent(),
                'threads': process.num_threads(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections())
            }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}
    
    def _percentile(self, data, percentile):
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def reset_stats(self):
        """重置统计数据"""
        with self._lock:
            self.request_count.clear()
            self.request_times.clear()
            self.error_count.clear()
            self.slow_requests.clear()
    
    def get_health_status(self):
        """获取健康状态"""
        stats = self.get_stats()
        
        # 计算健康评分
        health_score = 100
        issues = []
        
        # 检查错误率
        total_requests = sum(stats['requests'].values()) if stats['requests'] else 0
        total_errors = sum(stats['errors'].values())
        if total_requests > 0:
            error_rate = total_errors / total_requests
            if error_rate > 0.05:
                health_score -= 20
                issues.append(f"High error rate: {error_rate:.1%}")
        
        # 检查慢请求
        if len(stats['slow_requests']) > 10:
            health_score -= 10
            issues.append(f"Many slow requests: {len(stats['slow_requests'])}")
        
        # 检查系统资源
        sys_stats = stats.get('system', {})
        if sys_stats.get('memory_percent', 0) > 80:
            health_score -= 20
            issues.append(f"High memory usage: {sys_stats.get('memory_percent', 0):.1f}%")
        
        return {
            'status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'unhealthy',
            'score': health_score,
            'issues': issues,
            'timestamp': stats['timestamp']
        }


# 数据库查询计数装饰器
def track_queries(func):
    """装饰器 - 跟踪函数中的数据库查询"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if has_request_context() and hasattr(g, 'query_count'):
            g.query_count += 1
        return func(*args, **kwargs)
    return wrapper


# 性能监控装饰器
def monitor_performance(threshold=1.0):
    """装饰器 - 监控函数执行时间"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if duration > threshold:
                    logger.warning(
                        f"Slow function: {func.__name__} took {duration:.3f}s"
                    )
        return wrapper
    return decorator
