#!/bin/bash
# CV演示测试脚本
# 用于测试CV模块功能

echo "========================================="
echo "  餐饮供应链金融 - CV演示测试脚本"
echo "========================================="
echo ""

# 配置
CV_DIR="/Users/wangyunjie/Desktop/餐饮供应链金融赋能平台/cv"
DEMO_VIDEO="$CV_DIR/demo.mp4"

# 检查依赖
echo "[1/4] 检查依赖..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg 未安装"
    exit 1
fi
echo "✓ ffmpeg 已安装"

# 检查演示视频
echo ""
echo "[2/4] 检查演示视频..."
if [ -f "$DEMO_VIDEO" ]; then
    echo "✓ 演示视频存在: $DEMO_VIDEO"
    # 获取视频信息
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$DEMO_VIDEO" 2>/dev/null)
    echo "  时长: ${DURATION}秒"
else
    echo "⚠️ 演示视频不存在: $DEMO_VIDEO"
    echo "  请运行以下命令生成示例视频："
    echo "  ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 -vf \"drawtext=text='餐饮供应链金融CV演示':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2\" -pix_fmt yuv420p $DEMO_VIDEO"
fi

# 检查客流分析目录
echo ""
echo "[3/4] 检查客流分析模块..."
if [ -d "$CV_DIR/客流分析" ]; then
    echo "✓ 客流分析目录存在"
    FILE_COUNT=$(find "$CV_DIR/客流分析" -type f | wc -l)
    echo "  文件数量: $FILE_COUNT"
else
    echo "⚠️ 客流分析目录不存在"
fi

# 演示功能
echo ""
echo "[4/4] 功能演示说明"
echo "-----------------------------------"
echo "1. 查看使用说明: cat $CV_DIR/README.md"
echo "2. 播放演示视频: open $DEMO_VIDEO"
echo "3. 查看客流分析: open \"$CV_DIR/客流分析\""
echo ""
echo "========================================="
echo "  测试完成"
echo "========================================="
