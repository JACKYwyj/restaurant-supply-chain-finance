# RTV信用评分模型项目

餐饮供应链金融实时验证(RTV)信用评分模型 - 实证分析

## 项目概述

本项目实现了一个基于三重交叉验证机制的餐饮企业信用评分模型，通过资金流、客流、供应链三个维度的数据交叉验证，提升信用评估的准确性。

## 数据来源

| 数据类型 | 来源 | 说明 |
|----------|------|------|
| 宏观数据 | Bloomberg | GDP、CPI、M2、LPR (真实数据) |
| 商户数据 | 模拟生成 | 100家商户，2017Q1-2024Q4 (模拟数据) |

## 文件说明

### 数据文件
- `rtv_panel_data_real.xlsx` - 完整面板数据（含真实宏观数据）
- `macro_data_2017_2024.csv` - 整合后的宏观数据
- `merchant_info.xlsx` - 商户基础信息

### 代码文件
- `rtv_analysis_v2.do` - Stata完整分析代码
- `generate_merchant_data.do` - 商户数据生成代码

### 文档
- `RTV_model_design_v2.md` - 模型设计文档
- `rtv_model_stata.do` - 原始Stata代码

## 变量说明

### 被解释变量
- `credit_score` - 综合信用评分 (0-100)
- `default` - 是否违约 (0/1)
- `credit_limit` - 授信额度

### 核心解释变量
- `flow_score` - 资金流标准化得分
- `traffic_score` - 客流标准化得分
- `supply_score` - 供应链标准化得分

### 控制变量
- `q1-q4` - 季节虚拟变量
- `gdp_growth` - GDP同比增速
- `cpi` - 消费者价格指数
- `lpr` - 贷款市场报价利率
- `m2_growth` - M2同比增速
- `t1-t4` - 区域虚拟变量
- `i1-i5` - 行业虚拟变量

## 核心结论

1. **资金流得分**: 系数=8.13 (p<0.01)，显著正向影响信用评分
2. **客流得分**: 系数=5.07 (p<0.01)，显著正向影响信用评分
3. **供应链得分**: 系数=4.17 (p<0.01)，显著正向影响信用评分
4. **模型解释力**: R² = 96.52%

## 运行方式

### Stata
```stata
do rtv_analysis_v2.do
```

### Python
```python
python rtv_analysis.py
```

## 输出文件

- `table1_ols.csv` - OLS回归结果
- `table2_fe.csv` - 固定效应模型
- `table3_gmm.csv` - 动态面板GMM
- `table4_anomaly.csv` - 交叉验证分析
- `table5_robustness.csv` - 稳健性检验
- `fig1-7.png` - 可视化图形

## 作者

Jacky Wang

## 日期

2026-03-12
