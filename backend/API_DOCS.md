# API接口文档

## 认证接口

### 注册
- **POST** `/api/v1/auth/register`
- Body: `{"username": "xxx", "password": "xxx", "email": "xxx"}`

### 登录
- **POST** `/api/v1/auth/login`
- Body: `{"username": "xxx", "password": "xxx"}`

## 商户接口

### 获取仪表盘
- **GET** `/api/v1/merchant/dashboard`
- Header: `Authorization: Bearer <token>`

### 添加交易
- **POST** `/api/v1/merchant/transactions`
- Body: `{"amount": 100, "payment_channel": "alipay"}`

## 信贷接口

### 申请授信
- **POST** `/api/v1/credit/apply`
- Body: `{"amount": 500000}`

### 查询额度
- **GET** `/api/v1/credit/limit`

## 错误码

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求错误 |
| 401 | 未授权 |
| 500 | 服务器错误 |
