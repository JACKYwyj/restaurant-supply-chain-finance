#!/usr/bin/env python3
"""
客流分析系统 - 主入口
支持摄像头/RTSP视频流输入，实时输出客流数据
"""
import argparse
import json
import time
import sys
from pathlib import Path

from edge_runner import EdgeRunner
from counter import Direction


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='餐饮客流分析系统 - CV模块',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认摄像头
  python main.py
  
  # 指定摄像头
  python main.py --camera 0
  
  # 使用RTSP网络摄像头
  python main.py --rtsp rtsp://admin:admin@192.168.1.100:554/stream
  
  # 处理视频文件
  python main.py --video test.mp4
  
  # 边缘端模式（无预览）
  python main.py --camera 0 --no-preview --device cpu
  
  # 设置计数线位置
  python main.py --camera 0 --line-y 400 --direction in
  
  # 保存结果到JSON
  python main.py --camera 0 --output result.json
        """
    )
    
    # 输入源
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        '--camera', type=int, default=0,
        help='本地摄像头索引 (默认: 0)'
    )
    input_group.add_argument(
        '--rtsp', type=str,
        help='RTSP网络摄像头URL'
    )
    input_group.add_argument(
        '--video', type=str,
        help='视频文件路径'
    )
    
    # 模型参数
    parser.add_argument(
        '--model', type=str, default='yolov8n.pt',
        help='YOLO模型路径 (默认: yolov8n.pt)'
    )
    parser.add_argument(
        '--conf', type=float, default=0.5,
        help='置信度阈值 (默认: 0.5)'
    )
    parser.add_argument(
        '--device', type=str, default='cpu',
        choices=['cpu', 'cuda'],
        help='运行设备 (默认: cpu)'
    )
    
    # 计数线参数
    parser.add_argument(
        '--line-y', type=int, default=360,
        help='计数线Y坐标 (默认: 360)'
    )
    parser.add_argument(
        '--direction', type=str, default='in',
        choices=['in', 'out'],
        help='计数方向 - in:进店, out:离店 (默认: in)'
    )
    
    # 输出参数
    parser.add_argument(
        '--no-preview', action='store_true',
        help='不显示预览窗口（边缘端部署用）'
    )
    parser.add_argument(
        '--save-video', action='store_true',
        help='保存处理后的视频'
    )
    parser.add_argument(
        '--output', type=str,
        help='保存统计结果到JSON文件'
    )
    
    # 其他
    parser.add_argument(
        '--tables', type=int, default=10,
        help='餐桌数量，用于计算翻台率 (默认: 10)'
    )
    parser.add_argument(
        '--api', action='store_true',
        help='启动API服务模式'
    )
    parser.add_argument(
        '--port', type=int, default=8080,
        help='API服务端口 (默认: 8080)'
    )
    
    return parser.parse_args()


def print_stats(stats: dict):
    """打印统计信息"""
    print("\n" + "="*40)
    print("📊 客流统计")
    print("="*40)
    print(f"  进店人数: {stats.get('enter_count', 0)}")
    print(f"  离店人数: {stats.get('exit_count', 0)}")
    print(f"  总人数:   {stats.get('total_passers', 0)}")
    print(f"  转化率:   {stats.get('conversion_rate', 0)*100:.1f}%")
    print(f"  翻台率:   {stats.get('turnover_rate', 0)*100:.1f}%")
    print("="*40 + "\n")


def run_cli_mode(args):
    """命令行模式"""
    # 确定输入源
    if args.rtsp:
        source = args.rtsp
        source_type = "RTSP"
    elif args.video:
        source = args.video
        source_type = "视频"
    else:
        source = args.camera
        source_type = "摄像头"
    
    print(f"🚀 启动客流分析系统")
    print(f"   输入源: {source_type}")
    print(f"   设备:   {args.device}")
    print(f"   模型:   {args.model}")
    print(f"   计数线: Y={args.line_y}, 方向={args.direction}")
    
    # 创建运行器
    line_dir = Direction.IN if args.direction == "in" else Direction.OUT
    
    runner = EdgeRunner(
        model_path=args.model,
        conf_threshold=args.conf,
        device=args.device,
        line_coords=(0, args.line_y, 640, args.line_y),
        line_direction=line_dir,
        show_preview=not args.no_preview,
        save_output=args.save_video
    )
    
    # 设置餐桌数量
    runner.counter.set_table_count(args.tables)
    
    # 实时显示统计
    def on_event(event):
        direction_str = "进店" if event.event_type == "entered" else "离店"
        print(f"  [{time.strftime('%H:%M:%S')}] 顾客ID {event.track_id} {direction_str}")
    
    runner.set_event_callback(on_event)
    
    # 启动处理
    try:
        if args.rtsp:
            stats = runner.process_camera(camera_url=args.rtsp)
        elif args.video:
            stats = runner.process_video(args.video)
        else:
            stats = runner.process_camera(camera_index=args.camera)
        
        # 打印最终统计
        print_stats(stats)
        
        # 保存到文件
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"📁 结果已保存到: {args.output}")
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def run_api_mode(args):
    """API服务模式"""
    try:
        from flask import Flask, jsonify, Response
        import cv2
    except ImportError:
        print("❌ API模式需要安装flask: pip install flask")
        sys.exit(1)
    
    app = Flask(__name__)
    
    # 全局运行器
    global_runner = None
    current_frame = None
    
    # 创建运行器
    line_dir = Direction.IN if args.direction == "in" else Direction.OUT
    global_runner = EdgeRunner(
        model_path=args.model,
        conf_threshold=args.conf,
        device=args.device,
        line_coords=(0, args.line_y, 640, args.line_y),
        line_direction=line_dir,
        show_preview=False
    )
    global_runner.counter.set_table_count(args.tables)
    
    # 视频捕获
    cap = None
    
    def generate_frames():
        """视频流生成器"""
        global cap, current_frame
        
        # 打开视频源
        if args.rtsp:
            cap = cv2.VideoCapture(args.rtsp)
        elif args.video:
            cap = cv2.VideoCapture(args.video)
        else:
            cap = cv2.VideoCapture(args.camera)
        
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            # 处理帧
            result = global_runner.process_frame(frame)
            current_frame = result
            
            # 绘制可视化
            display = global_runner.draw_visualization(frame, result)
            
            # 编码为JPEG
            ret, buffer = cv2.imencode('.jpg', display)
            if not ret:
                continue
            
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    @app.route('/')
    def index():
        """主页"""
        return '''
        <html>
        <head><title>餐饮客流分析系统</title></head>
        <body>
            <h1>📹 实时客流分析</h1>
            <img src="/video" width="100%">
            <h2>统计接口: <a href="/stats">/stats</a></h2>
        </body>
        </html>
        '''
    
    @app.route('/video')
    def video_feed():
        """视频流"""
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/stats')
    def stats():
        """统计接口"""
        if global_runner:
            return jsonify(global_runner.get_statistics())
        return jsonify({'error': '系统未启动'})
    
    @app.route('/reset', methods=['POST'])
    def reset():
        """重置统计"""
        if global_runner:
            global_runner.reset()
            return jsonify({'status': 'ok'})
        return jsonify({'error': '系统未启动'})
    
    print(f"🚀 启动API服务: http://localhost:{args.port}")
    print(f"   视频流: http://localhost:{args.port}/video")
    print(f"   统计:   http://localhost:{args.port}/stats")
    
    app.run(host='0.0.0.0', port=args.port, threaded=True)


def main():
    """主函数"""
    args = parse_args()
    
    if args.api:
        run_api_mode(args)
    else:
        run_cli_mode(args)


if __name__ == '__main__':
    main()
