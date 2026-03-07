#!/bin/bash

# 餐饮供应链金融赋能平台 - 重启服务

set -e

echo "正在重启服务..."
docker-compose restart

echo "服务已重启"
echo ""
echo "服务状态:"
docker-compose ps
