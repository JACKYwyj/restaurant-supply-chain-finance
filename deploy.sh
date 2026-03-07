#!/bin/bash

# 餐饮供应链金融赋能平台 - 部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  餐饮供应链金融赋能平台 - 部署脚本${NC}"
echo -e "${GREEN}=========================================${NC}"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker未安装${NC}"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose未安装${NC}"
    exit 1
fi

# 创建必要目录
echo -e "${YELLOW}[1/5] 创建必要目录...${NC}"
mkdir -p logs data

# 设置环境变量文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}[2/5] 创建环境变量文件...${NC}"
    cat > .env << EOF
# Flask配置
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# 数据库配置 (如使用MySQL)
# DB_ROOT_PASSWORD=your_root_password
# DB_USER=restaurant_finance
# DB_PASSWORD=your_password
EOF
    echo -e "${GREEN}已创建 .env 文件，请根据需要修改${NC}"
else
    echo -e "${YELLOW}[2/5] 环境变量文件已存在，跳过创建${NC}"
fi

# 构建Docker镜像
echo -e "${YELLOW}[3/5] 构建Docker镜像...${NC}"
docker-compose build

# 启动服务
echo -e "${YELLOW}[4/5] 启动服务...${NC}"
docker-compose up -d

# 等待服务启动
echo -e "${YELLOW}[5/5] 等待服务启动...${NC}"
sleep 5

# 检查服务状态
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "服务状态:"
docker-compose ps
echo ""
echo -e "访问地址:"
echo -e "  - 后端API: ${GREEN}http://localhost:5000${NC}"
echo -e "  - 前端页面: ${GREEN}http://localhost${NC}"
echo -e "  - 健康检查: ${GREEN}http://localhost:5000/health${NC}"
echo ""
echo -e "常用命令:"
echo -e "  - 查看日志: ${YELLOW}docker-compose logs -f${NC}"
echo -e "  - 停止服务: ${YELLOW}docker-compose down${NC}"
echo -e "  - 重启服务: ${YELLOW}docker-compose restart${NC}"
echo -e "  - 重新构建: ${YELLOW}docker-compose build --no-cache${NC}"
echo ""
