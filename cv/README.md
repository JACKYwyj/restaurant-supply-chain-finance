# CV演示 - 使用说明

## 概述

本目录包含餐饮供应链金融赋能平台的计算机视觉(CV)演示文件。

## 目录结构

```
cv/
├── test.sh           # 测试脚本
├── README.md         # 使用说明
├── demo.mp4          # 示例视频（需生成）
└── 客流分析/          # 客流分析模块
    └── ...
```

## 快速开始

### 1. 运行测试脚本

```bash
cd /Users/wangyunjie/Desktop/餐饮供应链金融赋能平台/cv
chmod +x test.sh
./test.sh
```

### 2. 查看示例视频

如果demo.mp4不存在，使用以下命令生成：

```bash
ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 \
  -vf "drawtext=text='餐饮供应链金融CV演示':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
  -pix_fmt yuv420p demo.mp4
```

或者使用系统默认播放器打开：

```bash
open demo.mp4
```

### 3. 客流分析模块

客流分析目录包含：
- 客流统计数据
- 时段分析图表
- 热力图可视化

## 功能特性

### 客流分析
- 实时客流统计
- 高峰时段识别
- 客流趋势分析

## 技术要求

- macOS/Linux
- ffmpeg (视频处理)
- 支持的浏览器 (查看分析结果)

## 注意事项

1. 示例视频需要手动生成
2. 客流分析需要实际数据文件
3. 确保有足够的磁盘空间存储分析结果

## 联系方式

如有问题，请联系技术支持。
