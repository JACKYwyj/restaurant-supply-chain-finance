# 🍽️ 餐饮供应链金融赋能平台

基于多维数据验证的餐饮供应链金融赋能平台 - 商用级风控与信贷评估系统。

## 📥 下载安装

### macOS 版本
点击下载：[餐饮供应链金融平台-macOS.zip](https://github.com/JACKYwyj/restaurant-supply-chain-finance/releases/download/v1.0.0/%E9%A4%90%E9%A5%AE%E4%BE%9B%E5%BA%94%E9%93%BA%E9%93%81%E9%87%91%E8%B4%A7%E5%B9%B3%E5%8F%B0%E5%8F%B0-macOS.zip)

### Windows 版本
（待构建）

---

## 🚀 快速开始

### macOS 安装
1. 下载 macOS 版本
2. 解压 zip 文件
3. 双击打开应用

### 浏览器访问
直接在浏览器打开 `frontend/index.html`

### 后端服务
```bash
cd backend
pip install -r requirements.txt
python app.py
```

---

## 📁 项目结构

```
├── backend/           # Flask 后端
│   ├── api/          # API 接口
│   ├── services/      # 业务服务
│   └── models.py      # 数据模型
├── frontend/          # Web 前端
│   ├── index.html     # 登录页
│   └── dashboard.html # 管理后台
├── cv/               # 客流分析 CV 模块
└── electron/          # 桌面应用入口
```

---

## 🛠 技术栈

- **后端**: Flask + SQLAlchemy + JWT
- **前端**: HTML5 + CSS3 + JavaScript
- **CV**: OpenCV + YOLO
- **桌面**: Electron
