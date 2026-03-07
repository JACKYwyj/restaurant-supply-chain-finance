"""
客流计数器 - 进店/离店计数与翻台率计算
"""
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from collections import deque
from enum import Enum


class Direction(Enum):
    """移动方向"""
    IN = "in"      # 进店
    OUT = "out"    # 离店
    STATIONARY = "stationary"


@dataclass
class CountingLine:
    """计数线定义"""
    x1: int
    y1: int
    x2: int
    y2: int
    direction: Direction  # 穿越方向
    
    def get_points(self) -> List[Tuple[int, int]]:
        """获取线段端点"""
        return [(self.x1, self.y1), (self.x2, self.y2)]
    
    def is_crossed(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """
        检测线段是否被穿越
        
        Args:
            p1: 起点
            p2: 终点
            
        Returns:
            是否穿越
        """
        # 计算线的方程 ax + by + c = 0
        a = self.y2 - self.y1
        b = self.x1 - self.x2
        c = self.x2 * self.y1 - self.x1 * self.y2
        
        # 计算起点和终点到直线的距离
        d1 = a * p1[0] + b * p1[1] + c
        d2 = a * p2[0] + b * p2[1] + c
        
        # 如果两点在直线两侧，则穿越
        return d1 * d2 < 0


@dataclass
class CustomerEvent:
    """顾客事件"""
    track_id: int
    event_type: str  # entered, exited
    timestamp: float
    direction: Direction


class PassengerCounter:
    """客流计数器"""
    
    def __init__(
        self,
        line: Optional[CountingLine] = None,
        min_velocity: float = 2.0,  # 最小速度（像素/帧）
        direction_threshold: float = 0.5
    ):
        """
        初始化计数器
        
        Args:
            line: 计数线定义
            min_velocity: 最小有效速度
            direction_threshold: 方向判定阈值
        """
        self.line = line
        self.min_velocity = min_velocity
        self.direction_threshold = direction_threshold
        
        # 统计数据
        self.enter_count = 0
        self.exit_count = 0
        
        # 轨迹历史（用于方向判断）
        self.track_positions: dict = {}
        
        # 事件记录
        self.events: deque = deque(maxlen=1000)
        
        # 翻台率相关
        self.table_count = 0  # 餐桌总数
        self.turnover_history: deque = deque(maxlen=100)  # 历史翻台记录
    
    def set_counting_line(self, x1: int, y1: int, x2: int, y2: int, direction: Direction):
        """设置计数线"""
        self.line = CountingLine(x1, y1, x2, y2, direction)
    
    def update(self, tracks: List) -> List[CustomerEvent]:
        """
        更新计数
        
        Args:
            tracks: 当前活跃轨迹列表
            
        Returns:
            新发生的事件列表
        """
        new_events = []
        
        for track in tracks:
            track_id = track.track_id
            
            # 记录当前位置
            prev_pos = self.track_positions.get(track_id)
            curr_pos = track.center
            
            if prev_pos is None:
                self.track_positions[track_id] = curr_pos
                continue
            
            # 检测是否穿越计数线
            if self.line and self.line.is_crossed(prev_pos, curr_pos):
                # 判断方向
                move_direction = self._judge_direction(prev_pos, curr_pos)
                
                # 根据计数线方向判断进店/离店
                if self.line.direction == Direction.IN:
                    if move_direction == Direction.OUT:
                        self.exit_count += 1
                        event = CustomerEvent(
                            track_id=track_id,
                            event_type="exited",
                            timestamp=time.time(),
                            direction=Direction.OUT
                        )
                        new_events.append(event)
                else:  # line.direction == Direction.OUT
                    if move_direction == Direction.IN:
                        self.enter_count += 1
                        event = CustomerEvent(
                            track_id=track_id,
                            event_type="entered",
                            timestamp=time.time(),
                            direction=Direction.IN
                        )
                        new_events.append(event)
            
            # 更新位置
            self.track_positions[track_id] = curr_pos
        
        # 记录事件
        self.events.extend(new_events)
        
        return new_events
    
    def _judge_direction(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> Direction:
        """判断移动方向（基于Y轴变化，假设从画面下方进入为进店）"""
        dy = p2[1] - p1[1]  # 向下为正
        
        if abs(dy) < self.min_velocity:
            return Direction.STATIONARY
        
        # 假设：屏幕下方是入口，dy < 0 表示从下往上走（进店）
        return Direction.IN if dy < 0 else Direction.OUT
    
    def get_current_count(self) -> Tuple[int, int]:
        """获取当前进店/离店人数"""
        return self.enter_count, self.exit_count
    
    def get_conversion_rate(self) -> float:
        """计算进店转化率"""
        total = self.enter_count + self.exit_count
        if total == 0:
            return 0.0
        return self.enter_count / total
    
    def get_turnover_rate(self, time_window_minutes: int = 60) -> float:
        """
        计算翻台率
        
        Args:
            time_window_minutes: 时间窗口（分钟）
            
        Returns:
            翻台率
        """
        if self.table_count == 0:
            return 0.0
        
        # 统计时间窗口内的进店人数
        current_time = time.time()
        window_start = current_time - time_window_minutes * 60
        
        recent_entries = sum(
            1 for e in self.events 
            if e.event_type == "entered" and e.timestamp >= window_start
        )
        
        return recent_entries / self.table_count
    
    def set_table_count(self, count: int):
        """设置餐桌数量"""
        self.table_count = count
    
    def get_statistics(self) -> dict:
        """获取完整统计信息"""
        return {
            "enter_count": self.enter_count,
            "exit_count": self.exit_count,
            "total_passers": self.enter_count + self.exit_count,
            "conversion_rate": self.get_conversion_rate(),
            "turnover_rate": self.get_turnover_rate(),
            "table_count": self.table_count,
            "active_tracks": len(self.track_positions)
        }
    
    def reset(self):
        """重置计数器"""
        self.enter_count = 0
        self.exit_count = 0
        self.track_positions = {}
        self.events.clear()
        self.turnover_history.clear()
    
    def get_realtime_stats(self) -> dict:
        """获取实时统计（最近N分钟）"""
        # 最近5分钟统计
        window_seconds = 300
        current_time = time.time()
        window_start = current_time - window_seconds
        
        recent_entered = sum(
            1 for e in self.events 
            if e.event_type == "entered" and e.timestamp >= window_start
        )
        
        return {
            "recent_entered_5min": recent_entered,
            "current_conversion": self.get_conversion_rate()
        }
