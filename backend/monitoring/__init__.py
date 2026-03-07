"""
监控和运维模块
提供日志、性能监控、请求追踪、生命周期管理等功能
"""

from .logging_config import setup_logging, get_logger, RequestIdLogFilter
from .request_id import (
    generate_request_id,
    get_request_id,
    set_request_id,
    RequestIDMiddleware,
    request_id_utils
)
from .performance import (
    PerformanceMonitor,
    track_queries,
    monitor_performance
)
from .lifecycle import (
    LifecycleManager,
    lifecycle_hooks,
    check_database_connection,
    load_app_config,
    init_cache,
    warm_up_services,
    close_database_connection,
    flush_logs,
    cleanup_temp_files,
    save_state
)


def init_monitoring(app):
    """
    初始化所有监控组件
    
    在Flask应用创建后调用此函数来启用所有监控功能
    """
    # 1. 配置日志
    setup_logging(app)
    
    # 2. 初始化请求ID追踪
    RequestIDMiddleware(app)
    
    # 3. 初始化性能监控
    perf_monitor = PerformanceMonitor(app)
    
    # 4. 初始化生命周期管理
    lifecycle_mgr = LifecycleManager(app)
    
    # 注册默认钩子
    for hook in lifecycle_hooks['startup']:
        lifecycle_mgr.register_startup_hook(hook)
    
    for hook in lifecycle_hooks['shutdown']:
        lifecycle_mgr.register_shutdown_hook(hook)
    
    # 注册信号处理器
    lifecycle_mgr.register_signal_handlers()
    
    return {
        'performance_monitor': perf_monitor,
        'lifecycle_manager': lifecycle_mgr
    }


__all__ = [
    # 日志
    'setup_logging',
    'get_logger',
    'RequestIdLogFilter',
    
    # 请求ID
    'generate_request_id',
    'get_request_id',
    'set_request_id',
    'RequestIDMiddleware',
    'request_id_utils',
    
    # 性能监控
    'PerformanceMonitor',
    'track_queries',
    'monitor_performance',
    
    # 生命周期
    'LifecycleManager',
    'lifecycle_hooks',
    'check_database_connection',
    'load_app_config',
    'init_cache',
    'warm_up_services',
    'close_database_connection',
    'flush_logs',
    'cleanup_temp_files',
    'save_state',
    
    # 初始化函数
    'init_monitoring'
]
