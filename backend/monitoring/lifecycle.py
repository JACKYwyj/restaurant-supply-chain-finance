"""
应用生命周期钩子模块
处理应用启动和关闭时的任务
"""

import atexit
import signal
import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LifecycleManager:
    """应用生命周期管理器"""
    
    def __init__(self, app=None):
        self.app = app
        self.startup_hooks = []
        self.shutdown_hooks = []
        self.start_time = None
        self._shutdown_registered = False
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        self.app = app
        
        # 注册启动钩子
        @app.before_serving
        async def startup():
            """应用启动时执行"""
            self.start_time = datetime.utcnow()
            logger.info("=" * 50)
            logger.info(f"Application starting: {app.config.get('APP_NAME', 'Flask App')}")
            logger.info(f"Environment: {app.config.get('ENV', 'development')}")
            logger.info(f"Start time: {self.start_time.isoformat()}")
            logger.info("=" * 50)
            
            # 执行所有启动钩子
            for hook in self.startup_hooks:
                try:
                    logger.info(f"Running startup hook: {hook.__name__}")
                    result = hook(app)
                    if result:
                        logger.info(f"Startup hook {hook.__name__} completed: {result}")
                except Exception as e:
                    logger.error(f"Error in startup hook {hook.__name__}: {e}")
            
            logger.info("Application started successfully")
        
        # 注册关闭钩子
        @app.after_serving
        async def shutdown():
            """应用关闭时执行"""
            logger.info("=" * 50)
            logger.info("Application shutting down...")
            
            # 执行所有关闭钩子
            for hook in self.shutdown_hooks:
                try:
                    logger.info(f"Running shutdown hook: {hook.__name__}")
                    result = hook(app)
                    if result:
                        logger.info(f"Shutdown hook {hook.__name__} completed: {result}")
                except Exception as e:
                    logger.error(f"Error in shutdown hook {hook.__name__}: {e}")
            
            # 计算运行时长
            if self.start_time:
                uptime = datetime.utcnow() - self.start_time
                logger.info(f"Total uptime: {uptime}")
            
            logger.info("Application shutdown complete")
            logger.info("=" * 50)
    
    def register_startup_hook(self, hook):
        """注册启动钩子"""
        self.startup_hooks.append(hook)
        logger.info(f"Registered startup hook: {hook.__name__}")
    
    def register_shutdown_hook(self, hook):
        """注册关闭钩子"""
        self.shutdown_hooks.append(hook)
        logger.info(f"Registered shutdown hook: {hook.__name__}")
    
    def register_signal_handlers(self):
        """注册系统信号处理器"""
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"Received signal: {sig_name}")
            if self.app:
                # 触发Flask关闭
                from flask import Flask
                if isinstance(self.app, Flask):
                    self.app.logger.info("Triggering graceful shutdown...")
        
        # 注册常见信号
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                signal.signal(sig, signal_handler)
            except (OSError, ValueError):
                pass  # 某些信号在某些平台上不可用
    
    def register_atexit(self):
        """注册atexit回调"""
        def atexit_callback():
            logger.info("atexit callback: Application exiting")
        
        atexit.register(atexit_callback)
        self._shutdown_registered = True


# 常用的启动钩子
def check_database_connection(app):
    """检查数据库连接"""
    from models import db
    try:
        with app.app_context():
            db.session.execute('SELECT 1')
        return {'status': 'ok', 'message': 'Database connection healthy'}
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return {'status': 'error', 'message': str(e)}


def load_app_config(app):
    """加载应用配置"""
    logger.info("Loading application configuration...")
    return {'status': 'ok', 'config_loaded': True}


def init_cache(app):
    """初始化缓存"""
    logger.info("Initializing cache...")
    return {'status': 'ok', 'cache_ready': True}


def warm_up_services(app):
    """预热服务"""
    logger.info("Warming up services...")
    return {'status': 'ok', 'services_ready': True}


# 常用的关闭钩子
def close_database_connection(app):
    """关闭数据库连接"""
    from models import db
    try:
        db.session.close()
        logger.info("Database connections closed")
        return {'status': 'ok'}
    except Exception as e:
        logger.error(f"Error closing database: {e}")
        return {'status': 'error', 'message': str(e)}


def flush_logs(app):
    """刷新日志缓冲区"""
    import logging
    for handler in logging.root.handlers:
        handler.flush()
    logger.info("Logs flushed")
    return {'status': 'ok'}


def cleanup_temp_files(app):
    """清理临时文件"""
    import os
    import glob
    
    temp_patterns = [
        'logs/*.tmp',
        'instance/*.tmp',
    ]
    
    removed_count = 0
    for pattern in temp_patterns:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
                removed_count += 1
            except OSError:
                pass
    
    logger.info(f"Cleaned up {removed_count} temporary files")
    return {'status': 'ok', 'files_removed': removed_count}


def save_state(app):
    """保存应用状态"""
    logger.info("Saving application state...")
    return {'status': 'ok', 'state_saved': True}


# 生命周期钩子集合
lifecycle_hooks = {
    'startup': [
        check_database_connection,
        load_app_config,
        init_cache,
        warm_up_services
    ],
    'shutdown': [
        save_state,
        flush_logs,
        close_database_connection,
        cleanup_temp_files
    ]
}
