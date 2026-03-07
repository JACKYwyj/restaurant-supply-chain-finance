"""
轨迹跟踪器 - 使用IOU匹配进行目标跟踪
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import deque
import time


@dataclass
class Track:
    """目标轨迹"""
    track_id: int
    bbox: Tuple[int, int, int, int]
    center: Tuple[int, int]
    confidence: float
    timestamp: float
    history: deque = field(default_factory=lambda: deque(maxlen=30))
    entered: bool = False
    exited: bool = False
    state: str = "active"  # active, entered, exited


class ObjectTracker:
    """基于IOU的目标跟踪器"""
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3
    ):
        """
        初始化跟踪器
        
        Args:
            max_age: 最大未匹配帧数
            min_hits: 最小确认命中数
            iou_threshold: IOU匹配阈值
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.tracks: Dict[int, Track] = {}
        self.next_id = 1
        self.frame_count = 0
    
    def update(self, detections: List) -> List[Track]:
        """
        更新轨迹
        
        Args:
            detections: 当前帧检测结果
            
        Returns:
            确认的轨迹列表
        """
        self.frame_count += 1
        
        # 提取检测框
        det_bboxes = [d.bbox for d in detections] if detections else []
        
        # 匹配跟踪
        matched, unmatched_dets, unmatched_tracks = self._match(det_bboxes)
        
        # 更新匹配的轨迹
        for det_idx, track_idx in matched:
            track_id = list(self.tracks.keys())[track_idx]
            det = detections[det_idx]
            self.tracks[track_id].bbox = det.bbox
            self.tracks[track_id].center = self._get_center(det.bbox)
            self.tracks[track_id].confidence = det.confidence
            self.tracks[track_id].timestamp = time.time()
            self.tracks[track_id].history.append({
                'center': self.tracks[track_id].center,
                'timestamp': time.time()
            })
        
        # 为未匹配的检测创建新轨迹
        for det_idx in unmatched_dets:
            det = detections[det_idx]
            track_id = self.next_id
            self.next_id += 1
            
            self.tracks[track_id] = Track(
                track_id=track_id,
                bbox=det.bbox,
                center=self._get_center(det.bbox),
                confidence=det.confidence,
                timestamp=time.time(),
                history=deque([{
                    'center': self._get_center(det.bbox),
                    'timestamp': time.time()
                }], maxlen=30)
            )
        
        # 移除超时的轨迹
        self._remove_lost()
        
        # 返回活跃轨迹
        return [t for t in self.tracks.values() if t.state == "active"]
    
    def _match(self, det_bboxes: List[Tuple]) -> Tuple[List, List, List]:
        """IOU匹配"""
        if not self.tracks or not det_bboxes:
            unmatched_dets = list(range(len(det_bboxes)))
            unmatched_tracks = list(range(len(self.tracks)))
            return [], unmatched_dets, unmatched_tracks
        
        # 计算IOU矩阵
        iou_matrix = np.zeros((len(det_bboxes), len(self.tracks)))
        track_ids = list(self.tracks.keys())
        
        for d, det_bbox in enumerate(det_bboxes):
            for t, track_id in enumerate(track_ids):
                track_bbox = self.tracks[track_id].bbox
                iou_matrix[d, t] = self._calculate_iou(det_bbox, track_bbox)
        
        # 贪心匹配
        matched = []
        while True:
            max_iou = iou_matrix.max()
            if max_iou < self.iou_threshold:
                break
            
            max_idx = np.unravel_index(iou_matrix.shape[0] * iou_matrix.shape[1] - 1, iou_matrix.shape)
            det_idx, track_idx = np.where(iou_matrix == max_iou)
            det_idx, track_idx = det_idx[0], track_idx[0]
            
            matched.append((det_idx, track_idx))
            iou_matrix[det_idx, :] = 0
            iou_matrix[:, track_idx] = 0
        
        unmatched_dets = [i for i in range(len(det_bboxes)) if i not in [m[0] for m in matched]]
        unmatched_tracks = [i for i in range(len(self.tracks)) if i not in [m[1] for m in matched]]
        
        return matched, unmatched_dets, unmatched_tracks
    
    def _calculate_iou(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """计算IOU"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # 计算交集
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # 计算并集
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _get_center(self, bbox: Tuple) -> Tuple[int, int]:
        """获取边界框中心"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    def _remove_lost(self):
        """移除丢失的轨迹"""
        current_time = time.time()
        lost_tracks = []
        
        for track_id, track in self.tracks.items():
            if current_time - track.timestamp > self.max_age:
                lost_tracks.append(track_id)
        
        for track_id in lost_tracks:
            del self.tracks[track_id]
    
    def get_active_count(self) -> int:
        """获取当前活跃目标数"""
        return len([t for t in self.tracks.values() if t.state == "active"])
    
    def reset(self):
        """重置跟踪器"""
        self.tracks = {}
        self.next_id = 1
        self.frame_count = 0
