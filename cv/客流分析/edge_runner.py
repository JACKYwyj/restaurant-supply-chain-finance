"""
边缘端运行器 - 整合检测+跟踪+计数
支持摄像头输入，实时输出客流数据
"""
import cv2
import time
import numpy as np
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from detector import PersonDetector, Detection
from tracker import ObjectTracker, Track
from counter import PassengerCounter, CountingLine, Direction, CustomerEvent


@dataclass
class FrameResult:
    """单帧处理结果"""
    frame: np.ndarray
    detections: List[Detection]
    tracks: List[Track]
    events: List[CustomerEvent]
    enter_count: int
    exit_count: int
    active_count: int
    fps: float


class EdgeRunner:
    """边缘端客流分析运行器"""
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.5,
        device: str = "cpu",
        line_coords: Optional[tuple] = None,
        line_direction: Direction = Direction.IN,
        show_preview: bool = True,
        save_output: bool = False,
        output_path: str = "output.mp4"
    ):
        """
        初始化边缘运行器
        
        Args:
            model_path: YOLO模型路径
            conf_threshold: 置信度阈值
            device: 运行设备 ('cpu' 或 'cuda')
            line_coords: 计数线坐标 (x1, y1, x2, y2)，None则自动设置
            line_direction: 计数方向
            show_preview: 是否显示预览窗口
            save_output: 是否保存输出视频
            output_path: 输出视频路径
        """
        # 初始化各模块
        self.detector = PersonDetector(
            model_path=model_path,
            conf_threshold=conf_threshold,
            device=device
        )
        
        self.tracker = ObjectTracker(
            max_age=30,
            min_hits=3,
            iou_threshold=0.3
        )
        
        self.counter = PassengerCounter(
            min_velocity=2.0,
            direction_threshold=0.5
        )
        
        # 设置计数线
        if line_coords:
            x1, y1, x2, y2 = line_coords
        else:
            # 默认：画面中部水平线
            x1, y1, x2, y2 = 0, 360, 640, 360
        
        self.counter.set_counting_line(x1, y1, x2, y2, line_direction)
        
        # 运行参数
        self.show_preview = show_preview
        self.save_output = save_output
        self.output_path = output_path
        
        # 性能统计
        self.frame_count = 0
        self.start_time = None
        self.fps = 0.0
        
        # 视频写入器
        self.writer = None
        
        # 回调函数
        self.on_result: Optional[callable] = None
        self.on_event: Optional[callable] = None
    
    def process_frame(self, frame: np.ndarray) -> FrameResult:
        """
        处理单帧
        
        Args:
            frame: OpenCV图像帧
            
        Returns:
            处理结果
        """
        # 1. 人员检测
        detections = self.detector.detect(frame)
        
        # 2. 目标跟踪
        tracks = self.tracker.update(detections)
        
        # 3. 客流计数
        events = self.counter.update(tracks)
        
        # 4. 统计数据
        enter_count, exit_count = self.counter.get_current_count()
        active_count = self.tracker.get_active_count()
        
        # 计算FPS
        self.frame_count += 1
        if self.start_time is None:
            self.start_time = time.time()
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.fps = self.frame_count / elapsed
        
        # 触发回调
        if self.on_result:
            self.on_result({
                'frame_id': self.frame_count,
                'detections': detections,
                'tracks': tracks,
                'events': events,
                'enter_count': enter_count,
                'exit_count': exit_count,
                'active_count': active_count,
                'fps': self.fps
            })
        
        if events and self.on_event:
            for event in events:
                self.on_event(event)
        
        return FrameResult(
            frame=frame,
            detections=detections,
            tracks=tracks,
            events=events,
            enter_count=enter_count,
            exit_count=exit_count,
            active_count=active_count,
            fps=self.fps
        )
    
    def process_video(self, video_source: int or str) -> Dict[str, Any]:
        """
        处理视频流（摄像头或视频文件）
        
        Args:
            video_source: 摄像头索引(0,1,...)或视频文件路径
            
        Returns:
            最终统计结果
        """
        # 打开视频源
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频源: {video_source}")
        
        # 获取视频参数
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"视频参数: {width}x{height} @ {fps}fps")
        
        # 初始化视频写入器
        if self.save_output:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(self.output_path, fourcc, fps, (width, height))
        
        # 主循环
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("视频流结束")
                    break
                
                # 处理帧
                result = self.process_frame(frame)
                
                # 绘制可视化
                if self.show_preview:
                    display = self.draw_visualization(frame, result)
                    cv2.imshow('Passenger Counter', display)
                    
                    # 按ESC退出
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:
                        print("用户退出")
                        break
                
                # 保存视频
                if self.save_output and self.writer:
                    self.writer.write(result.frame)
        
        finally:
            # 释放资源
            cap.release()
            if self.writer:
                self.writer.release()
            if self.show_preview:
                cv2.destroyAllWindows()
        
        return self.get_statistics()
    
    def process_camera(
        self,
        camera_index: int = 0,
        camera_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理摄像头输入
        
        Args:
            camera_index: 本地摄像头索引
            camera_url: 网络摄像头URL（优先）
            
        Returns:
            最终统计结果
        """
        source = camera_url if camera_url else camera_index
        return self.process_video(source)
    
    def draw_visualization(self, frame: np.ndarray, result: FrameResult) -> np.ndarray:
        """
        绘制可视化结果
        
        Args:
            frame: 原始帧
            result: 处理结果
            
        Returns:
            可视化后的帧
        """
        display = frame.copy()
        
        # 绘制计数线
        if self.counter.line:
            line = self.counter.line
            cv2.line(display, (line.x1, line.y1), (line.x2, line.y2), (0, 0, 255), 2)
            # 绘制方向箭头
            mid_x = (line.x1 + line.x2) // 2
            mid_y = (line.y1 + line.y2) // 2
            arrow_len = 20
            if line.direction == Direction.IN:
                cv2.arrowedLine(display, (mid_x, mid_y + arrow_len), (mid_x, mid_y - arrow_len), (0, 255, 0), 2)
            else:
                cv2.arrowedLine(display, (mid_x, mid_y - arrow_len), (mid_x, mid_y + arrow_len), (0, 255, 0), 2)
        
        # 绘制跟踪框
        for track in result.tracks:
            x1, y1, x2, y2 = track.bbox
            # 不同ID用不同颜色
            color = (0, int(255 * (track.track_id % 5) / 5), 255)
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
            # 绘制ID
            cv2.putText(display, f"ID:{track.track_id}", (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 绘制统计信息
        info_text = [
            f"FPS: {result.fps:.1f}",
            f"Enter: {result.enter_count}",
            f"Exit: {result.exit_count}",
            f"Active: {result.active_count}"
        ]
        
        for i, text in enumerate(info_text):
            cv2.putText(display, text, (10, 30 + i*25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return display
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.counter.get_statistics()
    
    def reset(self):
        """重置计数器"""
        self.counter.reset()
        self.tracker.reset()
        self.frame_count = 0
        self.start_time = None
        self.fps = 0.0
    
    def set_result_callback(self, callback: callable):
        """设置结果回调"""
        self.on_result = callback
    
    def set_event_callback(self, callback: callable):
        """设置事件回调"""
        self.on_event = callback


def create_runner(
    model_path: str = "yolov8n.pt",
    device: str = "cpu",
    line_y: int = 360,
    direction: str = "in"
) -> EdgeRunner:
    """
    工厂函数：创建边缘运行器
    
    Args:
        model_path: YOLO模型路径
        device: 运行设备
        line_y: 计数线Y坐标
        direction: 方向 ('in' 或 'out')
        
    Returns:
        EdgeRunner实例
    """
    line_dir = Direction.IN if direction.lower() == "in" else Direction.OUT
    
    return EdgeRunner(
        model_path=model_path,
        device=device,
        line_coords=(0, line_y, 640, line_y),
        line_direction=line_dir,
        show_preview=True
    )
