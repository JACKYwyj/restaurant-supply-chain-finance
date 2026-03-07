#!/bin/bash

# 餐饮供应链金融赋能平台 - 停止服务

set -e

echo "正在停止服务..."
docker-compose down

echo "服务已停止"
