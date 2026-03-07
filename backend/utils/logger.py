"""
统一日志配置模块
"""

import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging(app):
    """配置应用日志"""
    
    # 日志级别
    log_level = logging.DEBUG if app.config.get('DEBUG', False) else logging.INFO
    
    # 日志格式
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    
    # 文件处理器 - 应用日志
    log_dir = app.config.get('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    app_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    app_file_handler.setLevel(log_level)
    app_file_handler.setFormatter(detailed_formatter)
    
    # 文件处理器 - 错误日志
    error_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    
    # 文件处理器 - 访问日志
    access_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'access.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    access_file_handler.setLevel(logging.INFO)
    access_file_handler.setFormatter(detailed_formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 添加处理器
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(error_file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('flask').setLevel(logging.INFO)
    
    app.logger.info("Logging configured successfully")
    
    return {
        'console': console_handler,
        'app': app_file_handler,
        'error': error_file_handler,
        'access': access_file_handler
    }


def get_logger(name):
    """获取命名日志记录器"""
    return logging.getLogger(name)
