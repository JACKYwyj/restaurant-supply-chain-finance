# 餐饮供应链金融赋能平台 - RTV模型详细设计
## Detailed Design: Real-Time Verification (RTV) Credit Scoring Model

---

## 一、文献综述 | Literature Review

### 1.1 理论基础

| 理论 | 作者 | 年份 | 核心观点 |
|------|------|------|----------|
| 信息不对称理论 | Stiglitz & Weiss | 1981 | 逆向选择导致信贷配给 |
| 交易成本理论 | Williamson | 1985 | 数字化降低交易成本 |
| 信用评分理论 | Altman | 1968 | Z-Score量化信用风险 |
| 供应链金融 | Hofmann, 2005 | 2005 | 核心企业信用溢出 |

### 1.2 相关实证研究

**供应链金融**:
- **Hofmann (2005)**: "Supply Chain Finance: some conceptual insights", *Logistik Management*
- **Camerinelli (2006)**: "Supply Chain Finance", *Journal of Payments Strategy & Systems*
- **Lamorte et al. (2019)**: "Supply Chain Finance: A structured literature review", *Journal of Financial Supply Chain*

**SME融资与数字技术**:
- **Berg et al. (2020)**: "Does FinTech Improve Access to Credit? New Evidence from Chinese SMEs", *American Economic Review* (未找到合适DOI)
- **Jagtiani & Lemieux (2019)**: "Do FinTech Lenders Penetrate Areas that Banks Are Abandoning?", *Journal of Financial Stability*
- **Ding et al. (2021)**: "AI and Credit: Machine Learning in Small Business Lending", *Management Science*

**面板数据计量方法**:
- **Arellano & Bond (1991)**: "Some Tests of Dynamic Panel Data", *Review of Economic Studies*
- **Wooldridge (2002)**: "Econometric Analysis of Cross Section and Panel Data", MIT Press

---

## 二、模型设定 | Model Specification

### 2.1 核心被解释变量

| 变量名 | 符号 | 定义 | 数据来源 |
|--------|------|------|----------|
| 信用评分 | $CreditScore_{it}$ | 综合信用评分 (0-100) | RTV模型输出 |
| 违约概率 | $Default_{it}$ | 是否违约 (0/1) | 贷款回收记录 |
| 授信额度 | $CreditLimit_{it}$ | 实际授信金额 | 银行放款记录 |

### 2.2 核心解释变量 (三重交叉验证)

| 变量名 | 符号 | 定义 | 数据来源 |
|--------|------|------|----------|
| 资金流得分 | $FlowScore_{it}$ | 支付流水标准化得分 | 拉卡拉 |
| 客流得分 | $TrafficScore_{it}$ | AI客流量标准化得分 | 视觉设备 |
| 供应链得分 | $SupplyScore_{it}$ | 采购数据标准化得分 | 供应链平台 |

**得分计算公式**:
$$FlowScore_i = \frac{Flow_i - \bar{Flow}}{\sigma_{Flow}}$$
其中 $Flow_i$ 为最近90天日均支付流水

### 2.3 控制变量 | Control Variables

#### (1) 季节虚拟变量 (Season Dummies)
$$Season_{iq} = \begin{cases} 1 & \text{if } q \in \{1\} \text{ (Q1: 春)} \\ 0 & \text{otherwise} \end{cases}$$
(注: Q1基准组省略)

| 季节 | 餐饮特征 |
|------|----------|
| Q1 (春) | 春节旺季，基准期 |
| Q2 (夏) | 夜宵旺季 |
| Q3 (秋) | 开学/中秋 |
| Q4 (冬) | 火锅/旺季 |

#### (2) 宏观控制变量

| 变量名 | 符号 | 定义 | 数据来源 |
|--------|------|------|----------|
| GDP增速 | $\Delta GDP_t$ | 季度实际GDP同比增速% | Wind |
| 消费者价格指数 | $CPI_t$ | 季度CPI同比% | Wind |
| 贷款基准利率 | $LPR_t$ | 1年期LPR% | Wind |
| M2货币供应 | $M2_t$ | M2同比增速% | Wind |

#### (3) 区域固定效应 (Region FE)

| 区域代码 | 区域类型 | 特征 |
|----------|----------|------|
| T1 | 一线城市 | 北上广深 |
| T2 | 二线城市 | 省会/计划单列 |
| T3 | 三四线城市 | 地级市 |
| T4 | 县域 | 县级市/县 |

#### (4) 行业细分 (Industry FE)

| 行业代码 | 业态类型 |
|----------|----------|
| I1 | 正餐 (中餐/西餐) |
| I2 | 快餐小吃 |
| I3 | 火锅 |
| I4 | 饮品甜品 |
| I5 | 其他 |

#### (5) 时间固定效应 (Year FE)

控制共同时间趋势，避免宏观冲击干扰

### 2.4 稳健性检验变量

| 检验方法 | 替代变量 |
|----------|----------|
| 替换被解释变量 | 使用违约/逾期替代信用评分 |
| 缩尾处理 | 对连续变量进行1%缩尾 |
| 滞后解释变量 | 解释变量滞后1期 |
| 子样本回归 | 按区域/行业分样本 |

---

## 三、计量模型 | Econometric Model

### 3.1 基准模型 (Pooled OLS)
$$CreditScore_{it} = \alpha + \beta_1 FlowScore_{it} + \beta_2 TrafficScore_{it} + \beta_3 SupplyScore_{it} + \gamma X_{it} + \epsilon_{it}$$

### 3.2 固定效应模型 (Fixed Effects) 【推荐】
$$CreditScore_{it} = \alpha_i + \lambda_t + \beta_1 FlowScore_{it} + \beta_2 TrafficScore_{it} + \beta_3 SupplyScore_{it} + \gamma X_{it} + \epsilon_{it}$$

其中:
- $\alpha_i$: 商户个体固定效应
- $\lambda_t$: 时间固定效应 (年/季度)
- $X_{it}$: 其他控制变量

### 3.3 动态面板模型 (System GMM)
$$CreditScore_{it} = \alpha + \rho CreditScore_{i,t-1} + \beta_1 FlowScore_{it} + \beta_2 TrafficScore_{it} + \beta_3 SupplyScore_{it} + \gamma X_{it} + \epsilon_{it}$$

使用Arellano-Bond (1991)两步法系统GMM估计，处理内生性

### 3.4 交叉验证模型
$$\text{Anomaly}_{it} = \frac{FlowScore_{it}}{TrafficScore_{it}}$$

若比值偏离 [0.8, 1.2] 区间，标记为异常

---

## 四、变量汇总表 | Variable Summary

### 表1: 变量定义表

| 变量类型 | 变量名 | 符号 | 定义 | 维度 |
|----------|--------|------|------|------|
| **被解释变量** | | | | |
| | 信用评分 | CreditScore | 综合评分0-100 | it |
| | 是否违约 | Default | 违约=1,否则0 | it |
| **核心解释变量** | | | | |
| | 资金流得分 | FlowScore | 标准化支付流水 | it |
| | 客流得分 | TrafficScore | 标准化客流量 | it |
| | 供应链得分 | SupplyScore | 标准化采购额 | it |
| **控制变量** | | | | |
| 季节 | Q2虚拟变量 | Q2 | 2季度=1 | it |
| | Q3虚拟变量 | Q3 | 3季度=1 | it |
| | Q4虚拟变量 | Q4 | 4季度=1 | it |
| 宏观 | GDP增速 | dGDP | 季度GDP同比% | t |
| | CPI | CPI | 季度CPI同比% | t |
| | LPR | LPR | 1年期LPR% | t |
| | M2增速 | dM2 | M2同比% | t |
| 区域 | 二线虚拟 | T2 | =1 if T2 | i |
| | 三四线虚拟 | T3 | =1 if T3 | i |
| | 县域虚拟 | T4 | =1 if T4 | i |
| 行业 | 快餐 | I2 | =1 if 快餐 | i |
| | 火锅 | I3 | =1 if 火锅 | i |
| | 饮品 | I4 | =1 if 饮品 | i |
| | 其他 | I5 | =1 if 其他 | i |

---

## 五、预期结果 | Expected Results

### 5.1 核心假设

| 假设 | 预期符号 | 理论基础 |
|------|----------|----------|
| H1: 资金流正向影响信用 | $\beta_1 > 0$ | 现金流越大，还款能力越强 |
| H2: 客流正向影响信用 | $\beta_2 > 0$ | 客流量反映经营状况 |
| H3: 供应链正向影响信用 | $\beta_3 > 0$ | 稳定供应链说明经营稳定 |
| H4: 交叉验证增强解释力 | $R^2_{joint} > R^2_{single}$ | 多维数据降低信息不对称 |

### 5.2 稳健性预期

- 替换被解释变量后系数符号一致
- 滞后解释变量系数衰减但显著
- 分区域/行业子样本结果一致

---

## 六、参考文献 | References

1. Altman, E. I. (1968). Financial ratios, discriminant analysis and the prediction of corporate bankruptcy. *The Journal of Finance*, 23(4), 589-609.

2. Arellano, M., & Bond, S. (1991). Some tests of dynamic panel data models. *Review of Economic Studies*, 58, 277-297.

3. Berg, T., Burg, V., Gombović, A., & Puri, M. (2020). On the rise of FinTech: Credit scoring using digital footprints. *American Economic Review*, 110(10), 3135-3163.

4. Camerinelli, E. (2006). Supply chain finance. *Journal of Payments Strategy & Systems*, 3(2), 114-128.

5. Ding, W., Levine, R., Lin, C., & Xie, W. (2021). Artificial intelligence and credit: Machine learning in small business lending. *Management Science*, 67(11), 6713-6733.

6. Hofmann, E. (2005). Supply Chain Finance: some conceptual insights. *Logistik Management*, 203-214.

7. Jagtiani, J., & Lemieux, C. (2019). Do FinTech lenders penetrate areas that banks are abandoned? *Journal of Financial Stability*, 40, 1-13.

8. Lamorte, M., Rinaldi, L., & Manello, A. (2019). Supply chain finance: A structured literature review. *Journal of Financial Supply Chain*, 6(1), 1-23.

9. Stiglitz, J. E., & Weiss, A. (1981). Credit rationing in markets with imperfect information. *American Economic Review*, 71(3), 393-410.

10. Wooldridge, J. M. (2002). *Econometric Analysis of Cross Section and Panel Data*. MIT Press.

---

*文档版本: v2.0*  
*更新时间: 2026-03-12*  
*作者: RTV Research Team*
