# 🍽️ 餐饮供应链金融赋能平台 (FoodVerify)

<div align="center">

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-green.svg)](package.json)
[![GitHub Pages](https://img.shields.io/badge/在线演示-GitHub%20Pages-brightgreen.svg)](https://jackywyj.github.io/restaurant-supply-chain-finance/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-orange.svg)](https://flask.palletsprojects.com/)

**基于多维数据验证的餐饮供应链金融赋能平台 - 商用级风控与信贷评估系统**

</div>

---

## 👀 在线演示

🔗 **GitHub Pages**: https://jackywyj.github.io/restaurant-supply-chain-finance/

> 💡 直接在浏览器中体验完整功能！

---

## ✨ 核心功能

| 模块 | 功能描述 |
|------|----------|
| 📊 **数据概览** | 实时客流、流水、授信额度监控 |
| 📹 **客流监测** | AI 视频实时客流统计与分析 |
| 💰 **流水管理** | 数字化资金往来记录 |
| 🚚 **供应商管理** | 供应链上下游协同 |
| 💳 **支付渠道** | 支付宝/微信支付接入 |
| 🏦 **融资授信** | 基于RTV评分的智能授信 |
| 📈 **RTV评分** | 多维数据信用评估模型 |
| ⚠️ **预警中心** | 风险预警与通知 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端层 (Client)                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Web   │  │  iOS   │  │ Android │  │ Desktop │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    API 网关层 (Flask REST API)              │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  信贷服务     │  │  客流分析CV   │  │  风控服务     │
│  (Credit)    │  │  (CV)        │  │  (Risk Ctrl) │
└───────────────┘  └───────────────┘  └───────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   数据库    │
                    │ (SQLite/   │
                    │  MySQL)    │
                    └─────────────┘
```

---

## 📁 项目结构

```
restaurant-supply-chain-finance/
├── backend/                    # Flask 后端服务
│   ├── api/                    # RESTful API 接口
│   │   ├── auth.py            # 认证接口
│   │   ├── credit.py          # 信贷接口
│   │   └── merchant.py        # 商户接口
│   ├── services/              # 业务服务层
│   │   ├── rtv_model.py       # RTV信用评分模型
│   │   └── risk_control.py    # 风控服务
│   ├── rtv_model/             # RTV模型分析
│   │   ├── RTV_model_design_v2.md
│   │   ├── rtv_analysis_v2.do # Stata分析代码
│   │   └── rtv_panel_data.csv # 面板数据
│   ├── models.py              # 数据模型
│   ├── monitoring/            # 系统监控
│   └── utils/                 # 工具函数
│
├── frontend/                   # Web 前端
│   ├── index.html             # 登录页
│   ├── dashboard.html         # 商户后台
│   ├── bank.html              # 银行/投资者端
│   ├── css/                   # 样式文件
│   └── js/                    # JavaScript 文件
│
├── cv/                        # 客流分析 CV 模块
│   └── 客流分析/
│       ├── detector.py        # 目标检测
│       ├── tracker.py         # 目标跟踪
│       ├── counter.py         # 客流统计
│       └── heatmap.py         # 热力图分析
│
├── electron/                  # Electron 桌面应用
├── dist/                      # 构建产物
└── screenshots/              # 项目截图
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Flask 2.0 + SQLAlchemy + JWT |
| **前端** | HTML5 + CSS3 + JavaScript (ES6+) |
| **CV** | OpenCV + YOLO + Python |
| **桌面** | Electron |
| **数据库** | SQLite (开发) / MySQL (生产) |
| **分析** | Stata + Python (RTV模型) |

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/JACKYwyj/restaurant-supply-chain-finance.git
cd restaurant-supply-chain-finance
```

### 2. 启动后端服务

```bash
cd backend

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

### 3. 访问前端

- 直接打开 `frontend/index.html` 体验
- 或访问 GitHub Pages: https://jackywyj.github.io/restaurant-supply-chain-finance/

---

## 📊 RTV 信用评分模型

本项目集成了自主研发的 **RTV (Real-Time Verification) 信用评分模型**：

### 模型变量

| 维度 | 指标 | 系数 (β) | 显著性 |
|------|------|----------|--------|
| 💵 **资金流** | 经营流水金额 | 8.13 | *** |
| 👥 **客流** | 日均客流量 | 5.07 | *** |
| 🚚 **供应链** | 供应商稳定度 | 4.17 | *** |

### 模型效果

- **R² = 96.52%** (面板数据回归)
- 数据来源：Bloomberg 宏观数据 + 模拟商户数据
- 时间跨度：2017-2024

详见: [RTV模型设计文档](backend/rtv_model/RTV_model_design_v2.docx)

---

## 📥 下载安装

### Windows
- [餐饮供应链金融平台 Setup 1.2.0.exe](https://github.com/JACKYwyj/restaurant-supply-chain-finance/releases/tag/v1.2.0)

### macOS
- [餐饮供应链金融平台-1.2.0-arm64.dmg](https://github.com/JACKYwyj/restaurant-supply-chain-finance/releases/tag/v1.2.0)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 👤 作者

**Jacky Wang**
- GitHub: https://github.com/JACKYwyj
- Email: 1230009401@student.must.edu.mo

---

<div align="center">

⭐ 如果这个项目对你有帮助，欢迎 star 支持！

</div>
