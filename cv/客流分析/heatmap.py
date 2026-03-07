"""
热力图模块 - 客流热力图统计与分析
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from collections import defaultdict
import time


@dataclass
class HeatmapConfig:
    """热力图配置"""
    grid_size: Tuple[int, int] = (32, 32)  # 网格大小
    sigma: float = 10.0  # 高斯核sigma
    alpha: float = 0.3  # 历史数据衰减因子
    min_frames: int = 1  # 最小帧数阈值
    show_grid: bool = False  # 是否显示网格


class HeatmapGenerator:
    """热力图生成器"""
    
    # 热力图颜色映射 (BGR)
    COLormap = [
        (0, 0, 255),      # 红色 - 最高
        (0, 69, 255),     # 橙红
        (0, 140, 255),    # 橙色
        (0, 255, 255),    # 黄色
        (0, 255, 200),    # 黄绿
        (0, 255, 100),    # 绿色
        (0, 255, 0),      # 浅绿
        (100, 255, 0),    # 青绿
        (200, 255, 0),    # 青
        (255, 255, 0),    # 青色
    ]
    
    def __init__(self, config: Optional[HeatmapConfig] = None):
        """
        初始化热力图生成器
        
        Args:
            config: 热力图配置
        """
        self.config = config or HeatmapConfig()
        
        # 帧尺寸
        self.frame_width = 640
        self.frame_height = 480
        
        # 热力图数据
        self.heatmap: Optional[np.ndarray] = None
        self.grid_heatmap: Optional[np.ndarray] = None
        
        # 网格参数
        self.grid_width = self.frame_width // self.config.grid_size[0]
        self.grid_height = self.frame_height // self.config.grid_size[1]
        
        # 统计数据
        self.total_points = 0
        self.frame_count = 0
        
        # 热点区域
        self.hotspots: List[Dict] = []
        
        # 初始化热力图
        self._init_heatmap()
    
    def _init_heatmap(self):
        """初始化热力图"""
        self.heatmap = np.zeros((self.frame_height, self.frame_width), dtype=np.float32)
        self.grid_heatmap = np.zeros(self.config.grid_size, dtype=np.float32)
    
    def set_frame_size(self, width: int, height: int):
        """设置帧尺寸"""
        self.frame_width = width
        self.frame_height = height
        self.grid_width = width // self.config.grid_size[0]
        self.grid_height = height // self.config.grid_size[1]
        self._init_heatmap()
    
    def add_points(self, points: List[Tuple[int, int]], weight: float = 1.0):
        """
        添加检测点到热力图
        
        Args:
            points: 检测点列表 [(x, y), ...]
            weight: 权重
        """
        if not points:
            return
        
        self.frame_count += 1
        self.total_points += len(points)
        
        # 创建当前帧的热力图
        frame_heatmap = np.zeros((self.frame_height, self.frame_width), dtype=np.float32)
        
        for x, y in points:
            # 边界检查
            if 0 <= x < self.frame_width and 0 <= y < self.frame_height:
                frame_heatmap[y, x] += weight
        
        # 应用高斯模糊
        kernel_size = int(self.config.sigma * 2) | 1  # 确保为奇数
        frame_heatmap = cv2.GaussianBlur(
            frame_heatmap, 
            (kernel_size, kernel_size), 
            self.config.sigma
        )
        
        # 归一化当前帧
        if frame_heatmap.max() > 0:
            frame_heatmap = frame_heatmap / frame_heatmap.max()
        
        # 累积到总热力图 (带衰减)
        if self.config.alpha < 1.0:
            self.heatmap = self.config.alpha * self.heatmap + (1 - self.config.alpha) * frame_heatmap
        else:
            self.heatmap += frame_heatmap
        
        # 更新网格热力图
        self._update_grid_heatmap(points)
    
    def _update_grid_heatmap(self, points: List[Tuple[int, int]]):
        """更新网格热力图"""
        for x, y in points:
            if 0 <= x < self.frame_width and 0 <= y < self.frame_height:
                gx = min(x // self.grid_width, self.config.grid_size[0] - 1)
                gy = min(y // self.grid_height, self.config.grid_size[1] - 1)
                self.grid_heatmap[gy, gx] += 1
    
    def get_heatmap_image(self, normalize: bool = True) -> np.ndarray:
        """
        获取热力图图像
        
        Args:
            normalize: 是否归一化
            
        Returns:
            热力图图像 (BGR格式)
        """
        if self.heatmap is None or self.heatmap.max() == 0:
            return np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        
        heat = self.heatmap.copy()
        
        if normalize and heat.max() > 0:
            heat = heat / heat.max()
        
        # 转换为8位
        heat = (heat * 255).astype(np.uint8)
        
        # 应用颜色映射
        heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
        
        return heat_color
    
    def get_grid_heatmap(self) -> np.ndarray:
        """获取网格热力图"""
        if self.grid_heatmap.max() > 0:
            normalized = (self.grid_heatmap / self.grid_heatmap.max() * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(self.grid_heatmap, dtype=np.uint8)
        
        # 放大到原始尺寸
        grid_img = cv2.resize(
            normalized, 
            (self.frame_width, self.frame_height),
            interpolation=cv2.INTER_NEAREST
        )
        
        return cv2.applyColorMap(grid_img, cv2.COLORMAP_JET)
    
    def analyze_hotspots(self, top_n: int = 5, threshold: float = 0.5) -> List[Dict]:
        """
        分析热点区域
        
        Args:
            top_n: 返回前N个热点
            threshold: 阈值 (0-1，相对于最大值)
            
        Returns:
            热点列表
        """
        if self.grid_heatmap.max() == 0:
            return []
        
        threshold_value = self.grid_heatmap.max() * threshold
        
        hotspots = []
        for gy in range(self.config.grid_size[1]):
            for gx in range(self.config.grid_size[0]):
                value = self.grid_heatmap[gy, gx]
                if value >= threshold_value:
                    # 计算热点区域
                    x1 = gx * self.grid_width
                    y1 = gy * self.grid_height
                    x2 = x1 + self.grid_width
                    y2 = y1 + self.grid_height
                    
                    hotspots.append({
                        'grid_pos': (gx, gy),
                        'rect': (x1, y1, x2, y2),
                        'center': ((x1 + x2) // 2, (y1 + y2) // 2),
                        'count': int(value),
                        'intensity': float(value / self.grid_heatmap.max())
                    })
        
        # 按强度排序
        hotspots.sort(key=lambda x: x['count'], reverse=True)
        
        self.hotspots = hotspots[:top_n]
        return self.hotspots
    
    def draw_hotspots(self, image: np.ndarray, top_n: int = 5) -> np.ndarray:
        """
        在图像上绘制热点区域
        
        Args:
            image: 原始图像
            top_n: 绘制前N个热点
            
        Returns:
            绘制后的图像
        """
        if not self.hotspots:
            self.analyze_hotspots(top_n=top_n)
        
        result = image.copy()
        
        for i, spot in enumerate(self.hotspots[:top_n]):
            x1, y1, x2, y2 = spot['rect']
            
            # 颜色从红到绿 (越高越红)
            color = self.COLormap[min(i, len(self.COLormap) - 1)]
            
            # 绘制矩形
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            label = f"#{i+1}: {spot['count']}"
            cv2.putText(result, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return result
    
    def get_statistics(self) -> Dict:
        """获取热力图统计信息"""
        return {
            'total_points': self.total_points,
            'frame_count': self.frame_count,
            'avg_points_per_frame': self.total_points / max(self.frame_count, 1),
            'grid_size': self.config.grid_size,
            'hotspots': self.hotspots[:5] if self.hotspots else []
        }
    
    def reset(self):
        """重置热力图"""
        self._init_heatmap()
        self.total_points = 0
        self.frame_count = 0
        self.hotspots = []
    
    def export_data(self) -> Dict:
        """导出热力图数据"""
        return {
            'heatmap': self.heatmap.tolist() if self.heatmap is not None else [],
            'grid_heatmap': self.grid_heatmap.tolist(),
            'statistics': self.get_statistics()
        }


def create_heatmap_overlay(
    frame: np.ndarray,
    heatmap: np.ndarray,
    alpha: float = 0.5
) -> np.ndarray:
    """
    创建热力图叠加层
    
    Args:
        frame: 原始帧
        heatmap: 热力图数据
        alpha: 透明度
        
    Returns:
        叠加后的图像
    """
    if heatmap is None or heatmap.max() == 0:
        return frame.copy()
    
    # 归一化热力图
    heat = heatmap.copy()
    if heat.max() > 0:
        heat = heat / heat.max()
    heat = (heat * 255).astype(np.uint8)
    
    # 应用颜色映射
    heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    
    # 调整大小以匹配帧
    if heat_color.shape[:2] != frame.shape[:2]:
        heat_color = cv2.resize(heat_color, (frame.shape[1], frame.shape[0]))
    
    # 叠加
    result = cv2.addWeighted(frame, 1 - alpha, heat_color, alpha, 0)
    
    return result
