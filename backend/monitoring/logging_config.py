"""
日志配置模块
提供统一的日志记录功能
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


def setup_logging(app):
    """配置Flask应用的日志系统"""
    
    # 日志目录
    log_dir = app.config.get('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志级别
    log_level_str = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # 日志格式
    log_format = app.config.get(
        'LOG_FORMAT',
        '%(asctime)s - %(name)s - %(levelname)s - %(request_id)s - %(message)s'
    )
    date_format = app.config.get('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
    
    # 创建日志格式化器
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器 - 按日期轮转
    log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,  # 保留30天日志
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 错误日志单独记录
    error_log_file = os.path.join(log_dir, 'error.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # 访问日志
    access_log_file = os.path.join(log_dir, 'access.log')
    access_handler = RotatingFileHandler(
        access_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    access_format = logging.Formatter(
        '%(asctime)s - %(request_id)s - %(remote_addr)s - %(method)s %(path)s - %(status)s - %(duration).3fs',
        datefmt=date_format
    )
    access_handler.setFormatter(access_format)
    
    # 设置werkzeug日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # 设置SQLAlchemy日志级别
    if not app.config.get('SQLALCHEMY_ECHO', False):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    return {
        'root_logger': root_logger,
        'file_handler': file_handler,
        'error_handler': error_handler,
        'access_handler': access_handler
    }


def get_logger(name):
    """获取命名日志记录器"""
    return logging.getLogger(name)


class RequestIdLogger:
    """请求ID日志过滤器 - 自动添加request_id到日志"""
    
    def __init__(self, request_id='-'):
        self.request_id = request_id
    
    def __format__(self, format_spec):
        return self.request_id


# 自定义日志字段处理器
class RequestIdLogFilter(logging.Filter):
    """日志过滤器 - 添加request_id到每条日志"""
    
    def __init__(self, request_id_func):
        super().__init__()
        self.request_id_func = request_id_func
    
    def filter(self, record):
        record.request_id = self.request_id_func()
        return True
