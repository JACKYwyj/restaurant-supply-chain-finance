"""
客流检测器 - 基于YOLO的目标检测
使用YOLOv8nano模型进行轻量化边缘端部署
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Detection:
    """检测结果数据结构"""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str


class PersonDetector:
    """基于YOLO的人员检测器"""
    
    # COCO数据集人物类ID
    PERSON_CLASS_ID = 0
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.5,
        device: str = "cpu"
    ):
        """
        初始化检测器
        
        Args:
            model_path: YOLO模型路径
            conf_threshold: 置信度阈值
            device: 运行设备 ('cpu' 或 'cuda')
        """
        self.conf_threshold = conf_threshold
        self.device = device
        
        # 延迟导入，避免依赖问题
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.model.to(device)
            self.model_loaded = True
        except ImportError:
            print("Warning: ultralytics未安装，使用模拟模式")
            self.model = None
            self.model_loaded = False
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        检测视频帧中的人员
        
        Args:
            frame: OpenCV读取的图像帧 (BGR格式)
            
        Returns:
            检测结果列表
        """
        if not self.model_loaded:
            return self._mock_detect(frame)
        
        # 执行推理
        results = self.model(
            frame,
            conf=self.conf_threshold,
            classes=[self.PERSON_CLASS_ID],  # 只检测人
            verbose=False
        )
        
        detections = []
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy()
                
                for box, conf, cls_id in zip(boxes, confs, class_ids):
                    x1, y1, x2, y2 = map(int, box)
                    detections.append(Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=float(conf),
                        class_id=int(cls_id),
                        class_name="person"
                    ))
        
        return detections
    
    def _mock_detect(self, frame: np.ndarray) -> List[Detection]:
        """模拟检测（用于测试）"""
        h, w = frame.shape[:2]
        # 返回一个随机检测用于测试
        return [
            Detection(
                bbox=(w//4, h//4, 3*w//4, 3*h//4),
                confidence=0.9,
                class_id=0,
                class_name="person"
            )
        ]
    
    def get_center(self, detection: Detection) -> Tuple[int, int]:
        """获取检测框中心点"""
        x1, y1, x2, y2 = detection.bbox
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return cx, cy
    
    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """在帧上绘制检测结果"""
        result = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # 绘制边界框
            cv2.rectangle(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # 绘制标签
            label = f"{det.class_name}: {det.confidence:.2f}"
            cv2.putText(result, label, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return result
