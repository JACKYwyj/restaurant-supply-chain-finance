# 基于多维数据验证的餐饮供应链金融赋能平台

餐饮供应链金融赋能平台是一个集成了多维数据验证的风险控制与信贷评估系统。通过整合商户流水、客流数据、供应链交易等多维度信息，实现对餐饮企业的精准信用评估与智能风控。

## 📁 目录结构

```
餐饮供应链金融赋能平台/
├── backend/                    # 后端服务
│   ├── api/                    # API 接口层
│   │   ├── auth.py             # 认证接口
│   │   ├── merchant.py         # 商户管理接口
│   │   └── credit.py           # 信贷评估接口
│   ├── services/               # 业务服务层
│   │   ├── risk_control.py     # 风控服务
│   │   └── rtv_model.py        # RTV模型服务
│   ├── app.py                  # Flask 应用入口
│   ├── config.py               # 配置文件
│   ├── models.py               # 数据模型
│   └── requirements.txt        # Python 依赖
├── frontend/                    # 前端页面
│   ├── index.html              # 首页/登录页
│   ├── dashboard.html          # 控制台页面
│   ├── js/                     # JavaScript 脚本
│   └── css/                    # 样式文件
└── cv/                          # 计算机视觉模块
    └── 客流分析/                # 客流分析系统
        ├── detector.py         # 目标检测
        ├── tracker.py          # 目标跟踪
        ├── counter.py          # 客流计数
        ├── edge_runner.py      # Edge 端运行器
        └── main.py             # 主程序
```

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+ (可选)
- OpenCV 4.x (用于客流分析)

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 启动服务

```bash
# 启动后端服务
cd backend
python app.py
```

后端服务默认运行在 `http://localhost:5000`

### 访问前端

直接在浏览器中打开 `frontend/index.html` 即可访问系统。

## 📦 各模块说明

### 1. 后端服务 (backend/)

#### API 层 (`api/`)
- **auth.py** - 用户认证、登录登出、JWT 令牌管理
- **merchant.py** - 商户信息管理、流水数据接入
- **credit.py** - 信贷评估申请、额度查询、还款管理

#### 服务层 (`services/`)
- **risk_control.py** - 风险控制引擎，多维数据交叉验证
- **rtv_model.py** - RTV(Remaining to Value) 模型，评估存货价值

#### 核心模块
- **app.py** - Flask 应用入口，路由配置
- **config.py** - 系统配置，数据库连接等
- **models.py** - SQLAlchemy 数据模型定义

### 2. 前端 (frontend/)

- **index.html** - 系统登录页
- **dashboard.html** - 管理控制台，包含商户管理、信贷管理、风控监控等功能
- **js/** - 前端交互逻辑
- **css/** - 样式文件

### 3. 计算机视觉 (cv/)

#### 客流分析系统
基于深度学习的餐饮门店客流分析解决方案：

- **detector.py** - YOLO/SSD 目标检测模型，用于检测进出店顾客
- **tracker.py** - SORT/DeepSORT 目标跟踪，维持顾客轨迹
- **counter.py** - 客流统计计数逻辑
- **edge_runner.py** - 边缘设备部署运行器
- **main.py** - 主程序入口

## 🛠 技术栈

### 后端
- **Framework**: Flask 2.x
- **ORM**: SQLAlchemy
- **Authentication**: JWT (PyJWT)
- **Data Validation**: Marshmallow

### 前端
- **HTML5** + **CSS3**
- **JavaScript** (原生 ES6+)
- **Chart.js** - 数据可视化

### 计算机视觉
- **OpenCV 4.x** - 图像处理
- **YOLO/SSD** - 目标检测
- **SORT/DeepSORT** - 多目标跟踪

### 数据存储
- **SQLite** (开发环境)
- 支持 MySQL/PostgreSQL (生产环境)

## 📋 环境变量

在 `backend/config.py` 中配置：

```python
SECRET_KEY = "your-secret-key"
DATABASE_URI = "sqlite:///app.db"
JWT_SECRET = "your-jwt-secret"
```

## 📄 许可证

MIT License
