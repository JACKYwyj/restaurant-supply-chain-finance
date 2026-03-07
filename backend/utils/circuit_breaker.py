"""
服务降级与熔断器模式实现
"""

import time
import threading
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Any, Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常关闭
    OPEN = "open"          # 熔断开启
    HALF_OPEN = "half_open"  # 半开状态


class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        """
        初始化熔断器
        
        Args:
            name: 熔断器名称
            failure_threshold: 失败次数阈值，达到此值则开启熔断
            success_threshold: 半开状态下成功次数阈值，达到此值则关闭熔断
            timeout: 熔断超时时间（秒），超过此时间后进入半开状态
            half_open_max_calls: 半开状态下的最大调用次数
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
        
        # 统计数据
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
        logger.info(f"CircuitBreaker '{name}' initialized with threshold={failure_threshold}, timeout={timeout}s")
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态，自动根据超时转换"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # 检查是否超时
                if time.time() - self._last_failure_time >= self.timeout:
                    logger.info(f"CircuitBreaker '{self.name}' transitioning from OPEN to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数调用，带熔断保护"""
        with self._lock:
            self.total_calls += 1
            current_state = self.state
            
            # 如果处于开启状态，直接拒绝
            if current_state == CircuitState.OPEN:
                self._half_open_calls += 1
                if self._half_open_calls > self.half_open_max_calls:
                    # 超过半开最大调用次数，重新计算
                    raise CircuitBreakerOpenError(
                        f"CircuitBreaker '{self.name}' is OPEN. Call rejected."
                    )
                logger.warning(f"CircuitBreaker '{self.name}' is OPEN, allowing test call ({self._half_open_calls}/{self.half_open_max_calls})")
            
            # 如果处于半开状态，限制调用
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"CircuitBreaker '{self.name}' is HALF_OPEN. Max test calls reached."
                    )
                self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """记录成功调用"""
        with self._lock:
            self.total_successes += 1
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"CircuitBreaker '{self.name}' success in HALF_OPEN state "
                    f"({self._success_count}/{self.success_threshold})"
                )
                if self._success_count >= self.success_threshold:
                    logger.info(f"CircuitBreaker '{self.name}' transitioning to CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # 成功时重置失败计数
                self._failure_count = 0
    
    def _on_failure(self):
        """记录失败调用"""
        with self._lock:
            self.total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.CLOSED:
                logger.warning(
                    f"CircuitBreaker '{self.name}' failure "
                    f"({self._failure_count}/{self.failure_threshold})"
                )
                if self._failure_count >= self.failure_threshold:
                    logger.warning(f"CircuitBreaker '{self.name}' transitioning to OPEN")
                    self._state = CircuitState.OPEN
            elif self._state == CircuitState.HALF_OPEN:
                logger.warning(f"CircuitBreaker '{self.name}' failure in HALF_OPEN, transitioning to OPEN")
                self._state = CircuitState.OPEN
                self._success_count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取熔断器统计信息"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
                'total_calls': self.total_calls,
                'total_failures': self.total_failures,
                'total_successes': self.total_successes,
                'last_failure_time': self._last_failure_time
            }
    
    def reset(self):
        """手动重置熔断器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.info(f"CircuitBreaker '{self.name}' manually reset")


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass


class CircuitBreakerManager:
    """熔断器管理器"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    success_threshold=success_threshold,
                    timeout=timeout
                )
            return self._breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有熔断器统计"""
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self._breakers.items()}
    
    def reset_all(self):
        """重置所有熔断器"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("All circuit breakers reset")


# 全局熔断器管理器
circuit_breaker_manager = CircuitBreakerManager()


def circuit_breaker(
    name: str = None,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 30.0,
    fallback: Callable = None
):
    """
    熔断器装饰器
    
    Usage:
        @circuit_breaker('external_api', failure_threshold=3)
        def call_external_api():
            return external_api.request()
    """
    def decorator(func: Callable) -> Callable:
        breaker_name = name or func.__module__ + '.' + func.__name__
        breaker = circuit_breaker_manager.get_or_create(
            breaker_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return breaker.call(func, *args, **kwargs)
            except CircuitBreakerOpenError:
                if fallback:
                    logger.info(f"Calling fallback for {breaker_name}")
                    return fallback(*args, **kwargs)
                raise
            except Exception as e:
                # 记录其他异常但不触发熔断（由call内部处理）
                logger.error(f"Error in {breaker_name}: {e}")
                raise
        
        # 附加熔断器信息到函数
        wrapper._circuit_breaker = breaker
        return wrapper
    
    return decorator


class ServiceDegradation:
    """服务降级管理器"""
    
    def __init__(self):
        self._degraded_services: Dict[str, bool] = {}
        self._fallbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        
        # 降级统计
        self.degradation_history = deque(maxlen=100)
    
    def degrade_service(self, service_name: str, reason: str = None):
        """标记服务为降级状态"""
        with self._lock:
            self._degraded_services[service_name] = True
            self.degradation_history.append({
                'service': service_name,
                'action': 'degrade',
                'reason': reason,
                'timestamp': time.time()
            })
            logger.warning(f"Service '{service_name}' degraded. Reason: {reason}")
    
    def restore_service(self, service_name: str):
        """恢复服务"""
        with self._lock:
            self._degraded_services[service_name] = False
            self.degradation_history.append({
                'service': service_name,
                'action': 'restore',
                'timestamp': time.time()
            })
            logger.info(f"Service '{service_name}' restored")
    
    def is_degraded(self, service_name: str) -> bool:
        """检查服务是否降级"""
        with self._lock:
            return self._degraded_services.get(service_name, False)
    
    def register_fallback(self, service_name: str, fallback_func: Callable):
        """注册降级时的回调函数"""
        with self._lock:
            self._fallbacks[service_name] = fallback_func
    
    def get_fallback(self, service_name: str) -> Optional[Callable]:
        """获取降级回调函数"""
        with self._lock:
            return self._fallbacks.get(service_name)
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有服务状态"""
        with self._lock:
            return {
                'services': dict(self._degraded_services),
                'recent_history': list(self.degradation_history)[-10:]
            }


# 全局服务降级管理器
service_degradation = ServiceDegradation()


def degraded(fallback: Callable = None, service_name: str = None):
    """
    服务降级装饰器
    
    Usage:
        @degraded(fallback=get_cached_data, service_name='cache')
        def get_data():
            return database.query()
    """
    def decorator(func: Callable) -> Callable:
        svc_name = service_name or func.__module__ + '.' + func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查是否已降级
            if service_degradation.is_degraded(svc_name):
                fallback_func = service_degradation.get_fallback(svc_name) or fallback
                if fallback_func:
                    logger.info(f"Service '{svc_name}' degraded, calling fallback")
                    return fallback_func(*args, **kwargs)
                raise ServiceDegradedError(f"Service '{svc_name}' is degraded and no fallback available")
            
            try:
                result = func(*args, **kwargs)
                # 检查返回值是否表示降级
                if isinstance(result, dict) and result.get('_degraded'):
                    service_degradation.degrade_service(svc_name, result.get('reason'))
                    fallback_func = service_degradation.get_fallback(svc_name) or fallback
                    if fallback_func:
                        return fallback_func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Service '{svc_name}' error: {e}")
                # 可以选择在此处自动降级
                # service_degradation.degrade_service(svc_name, str(e))
                raise
        
        return wrapper
    
    return decorator


class ServiceDegradedError(Exception):
    """服务降级异常"""
    pass
