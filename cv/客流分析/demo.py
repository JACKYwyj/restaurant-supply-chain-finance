#!/usr/bin/env python3
"""
餐饮供应链金融平台 - 实时客流分析演示
使用YOLO进行实时客流检测和计数
"""

import cv2
import numpy as np
from ultralytics import YOLO
import argparse

class RealTimeCustomerCounter:
    def __init__(self, camera_id=0, model_name='yolov8n.pt'):
        """初始化客流计数器"""
        print(f"正在加载YOLO模型: {model_name}...")
        self.model = YOLO(model_name)
        self.cap = cv2.VideoCapture(camera_id)
        
        # 设置视频参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # 计数变量
        self.enter_count = 0
        self.exit_count = 0
        self.total_count = 0
        
        # 跟踪ID
        self.track_ids = {}
        self.next_id = 1
        
        # 计数线位置（画面中线）
        self.count_line_y = 360  # 720/2
        
        # 颜色
        self.color = (0, 255, 0)  # 绿色
        
        print("模型加载完成！")
        
    def draw_count_line(self, frame):
        """绘制计数线"""
        height, width = frame.shape[:2]
        cv2.line(frame, (0, self.count_line_y), (width, self.count_line_y), (0, 255, 255), 2)
        cv2.putText(frame, f"进店: {self.enter_count}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"离店: {self.exit_count}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, f"总人数: {self.total_count}", (10, 110), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        
    def process_frame(self, frame):
        """处理每一帧"""
        # 使用YOLO进行检测
        results = self.model(frame, stream=True, classes=[0])  # class 0 = person
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # 获取边界框
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                
                if conf > 0.5:  # 置信度阈值
                    # 绘制边界框
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), 
                                 self.color, 2)
                    
                    # 获取中心点
                    center_y = (y1 + y2) / 2
                    
                    # 简单计数逻辑：检测是否穿过中线
                    if center_y < self.count_line_y:
                        cv2.putText(frame, "进店", (int(x1), int(y1)-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    else:
                        cv2.putText(frame, "在店", (int(x1), int(y1)-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
                    
                    # 显示置信度
                    cv2.putText(frame, f"{conf:.2f}", (int(x2), int(y1)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def run(self):
        """运行主循环"""
        if not self.cap.isOpened():
            print("无法打开摄像头！")
            return
        
        print("开始实时客流分析... 按 'q' 退出")
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("无法读取视频帧")
                break
            
            # 处理帧
            frame = self.process_frame(frame)
            
            # 绘制计数线
            self.draw_count_line(frame)
            
            # 显示帧
            cv2.imshow('餐饮客流分析系统', frame)
            
            # 按q退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        # 释放资源
        self.cap.release()
        cv2.destroyAllWindows()
        
        print(f"\n=== 分析结果 ===")
        print(f"进店人数: {self.enter_count}")
        print(f"离店人数: {self.exit_count}")
        print(f"当前店内人数: {self.total_count}")


def main():
    parser = argparse.ArgumentParser(description='实时客流分析')
    parser.add_argument('--camera', type=int, default=0, help='摄像头ID')
    parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO模型')
    args = parser.parse_args()
    
    counter = RealTimeCustomerCounter(args.camera, args.model)
    counter.run()


if __name__ == '__main__':
    main()
