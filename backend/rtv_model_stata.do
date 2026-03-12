/*==============================================================================
RTV Credit Scoring Model - Stata Implementation
餐饮供应链金融实时验证模型 - Stata实现

Author: RTV Research Team
Date: 2026-03-12
Reference: RTV_model_design_v2.md

文献参考:
- Altman (1968) - Z-Score信用评分
- Arellano & Bond (1991) - 动态面板GMM
- Berg et al. (2020) - FinTech信贷研究
- Ding et al. (2021) - AI与信贷

Note: 需要安装: ssc install xtabond2, estout, outreg2
==============================================================================*/

clear all
set more off
cap log close

*==============================================================================
* 1. 数据导入与预处理
*==============================================================================

* 导入面板数据 (假设数据格式: panel_data.dta)
* import excel "panel_data.xlsx", sheet("Sheet1") firstrow clear

* 示例数据结构:
* id      year    quarter   credit_score   flow_score   traffic_score  supply_score
* 1001    2023    1         75.3           1.23         0.87           0.95
* 1001    2023    2         78.5           1.35         1.02           1.08

* 创建示例数据 (用于演示)
clear
set seed 20260312
set obs 800

* 商户ID (100家商户 × 8个季度)
gen id = floor((_n-1)/8) + 1
gen year = 2023 + floor((mod(_n-1,8))/4)
gen quarter = mod(_n-1,4) + 1

* 时间趋势
gen time_index = (year - 2023) * 4 + quarter

* 核心解释变量 (标准化得分)
gen flow_score = rnormal(0.8, 0.3)
gen traffic_score = rnormal(0.7, 0.35)
gen supply_score = rnormal(0.75, 0.32)

* 添加商户固定效应
bys id: gen firm_fe = rnormal(0, 0.5)
replace flow_score = flow_score + firm_fe
replace traffic_score = traffic_score + firm_fe * 0.8
replace supply_score = supply_score + firm_fe * 0.6

* 被解释变量: 信用评分 (加入核心变量的影响)
gen credit_score = 60 + 8*flow_score + 5*traffic_score + 4*supply_score ///
    + rnormal(0, 1.5)
replace credit_score = 60 + 8*flow_score + 5*traffic_score + 4*supply_score ///
    + 0.3*firm_fe + rnormal(0, 1.5)

* 季节虚拟变量
gen q1 = (quarter == 1)
gen q2 = (quarter == 2)
gen q3 = (quarter == 3)
gen q4 = (quarter == 4)

* 宏观控制变量 (模拟)
gen gdp_growth = 5.2 + rnormal(0, 0.5) - 0.1*time_index
gen cpi = 2.1 + rnormal(0, 0.3)
gen lpr = 3.65 + rnormal(0, 0.05)
gen m2_growth = 10.5 + rnormal(0, 0.8)

* 区域虚拟变量
gen region = mod(id, 4) + 1
gen t1 = (region == 1)
gen t2 = (region == 2)
gen t3 = (region == 3)
gen t4 = (region == 4)

* 行业虚拟变量
gen industry = mod(id, 5) + 1
forvalues i = 2/5 {
    gen i`i' = (industry == `i')
}

* 违约变量 (派生)
gen default = (credit_score < 70 & uniform() < 0.15)

* 标签
label var id "商户ID"
label var year "年份"
label var quarter "季度"
label var credit_score "信用评分"
label var flow_score "资金流得分"
label var traffic_score "客流得分"
label var supply_score "供应链得分"
label var q1 "Q1(春)"
label var q2 "Q2(夏)"
label var q3 "Q3(秋)"
label var q4 "Q4(冬)"
label var gdp_growth "GDP增速(%)"
label var cpi "CPI同比(%)"
label var lpr "1年期LPR(%)"
label var m2_growth "M2增速(%)"
label var t1 "一线城市"
label var t2 "二线城市"
label var t3 "三四线城市"
label var t4 "县域"
label var i2 "快餐"
label var i3 "火锅"
label var i4 "饮品"
label var i5 "其他"
label var default "是否违约"

* 面板数据设置
xtset id quarter

save "rtv_panel_data.dta", replace

*==============================================================================
* 2. 描述性统计
*==============================================================================

log using "descriptive_stats.log", replace

di "===== 表1: 描述性统计 ====="
sum credit_score flow_score traffic_score supply_score, detail

di "===== 按季度均值 ====="
bys quarter: sum credit_score flow_score traffic_score supply_score

di "===== 按区域均值 ====="
bys region: sum credit_score flow_score traffic_score supply_score

log close

*==============================================================================
* 3. 相关性分析
*==============================================================================

di "===== 表2: 相关系数矩阵 ====="
pwcorr credit_score flow_score traffic_score supply_score, star(0.05)

*==============================================================================
* 4. 基准回归: Pooled OLS
*==============================================================================

* 安装必要的包 (如未安装)
cap ssc install estout, replace
cap ssc install outreg2, replace

* 表3: 基准OLS回归
eststo clear

* 模型1: 仅核心变量
eststo: reg credit_score flow_score traffic_score supply_score, robust

* 模型2: 加入季节虚拟变量
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4, robust

* 模型3: 加入宏观变量
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth, robust

* 模型4: 加入区域和行业固定效应
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth t2 t3 t4 i2 i3 i4 i5, robust

* 输出结果
esttab using "table3_ols.csv", replace ///
    title("表3: 基准OLS回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress r2

esttab using "table3_ols.tex", replace ///
    title("表3: 基准OLS回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress booktabs

*==============================================================================
* 5. 固定效应模型
*==============================================================================

* 表4: 固定效应回归
eststo clear

* 模型5: 商户固定效应 + 时间趋势
xtreg credit_score flow_score traffic_score supply_score q2 q3 q4, fe robust

* 模型6: 双向固定效应 (商户+时间)
xtreg credit_score flow_score traffic_score supply_score q2 q3 q4 i.time_index, fe robust

esttab using "table4_fe.csv", replace ///
    title("表4: 固定效应模型") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress r2

*==============================================================================
* 6. 动态面板模型 (System GMM)
*==============================================================================

cap ssc install xtabond2, replace

* 表5: 动态面板GMM
eststo clear

* 模型7: System GMM (两步法)
xtabond2 credit_score L.credit_score flow_score traffic_score supply_score ///
    q2 q3 gdp_growth cpi, ///
    gmm(L.credit_score flow_score traffic_score supply_score, lag(1 2)) ///
    iv(q2 q3 gdp_growth cpi) ///
    twostep robust

esttab using "table5_gmm.csv", replace ///
    title("表5: System GMM回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap

*==============================================================================
* 7. 交叉验证分析
*==============================================================================

* 计算异常指标
gen anomaly_ratio = flow_score / traffic_score
gen anomaly_flag = (anomaly_ratio < 0.8 | anomaly_ratio > 1.2)

di "===== 交叉验证异常比例 ====="
tab anomaly_flag

* 表6: 异常检验
eststo clear
eststo: reg credit_score flow_score traffic_score supply_score anomaly_flag, robust
eststo: xtreg credit_score flow_score traffic_score supply_score anomaly_flag, fe robust

esttab using "table6_anomaly.csv", replace

*==============================================================================
* 8. 稳健性检验
*==============================================================================

eststo clear

* 检验1: 替换被解释变量 (Logit: 违约概率)
logit default flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth t2 t3 t4 i2 i3 i4 i5, robust
eststo: margins, dydx(*) post

* 检验2: 滞后解释变量
gen l_flow = L.flow_score
gen l_traffic = L.traffic_score
gen l_supply = L.supply_score

reg credit_score l_flow l_traffic l_supply q2 q3 q4, robust
eststo: reg credit_score l_flow l_traffic l_supply q2 q3 q4, robust

* 检验3: 缩尾处理
foreach var of varlist credit_score flow_score traffic_score supply_score {
    cap drop _w
    egen _w = winsor(`var'), gen(w_`var') p(0.01)
}
reg w_credit_score w_flow_score w_traffic_score w_supply_score q2 q3 q4, robust

* 检验4: 按区域分样本
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t1 == 1, robust
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t2 == 1, robust

esttab using "table7_robustness.csv", replace

*==============================================================================
* 9. 安慰剂检验
*==============================================================================

* 随机生成解释变量进行回归
set seed 12345
gen placebo_flow = rnormal(0.8, 0.3)
gen placebo_traffic = rnormal(0.7, 0.35)

reg credit_score placebo_flow placebo_traffic q2 q3 q4, robust

di "如果安慰剂变量系数不显著, 则说明基准回归结果稳健"

*==============================================================================
* 10. 结果输出汇总
*==============================================================================

* 输出完整回归表 (Word兼容)
outreg2 using "full_results.doc", replace ///
    title("RTV模型回归结果汇总") ///
    ctitle("OLS(1)", "OLS(2)", "OLS(3)", "OLS(4)", "FE(5)", "FE(6)", "GMM(7)") ///
    label dec(3)

* 输出描述性统计
outreg2 using "descriptive.doc", replace ///
    sum/title("描述性统计") ///
    label dec(3) ///
    keep(credit_score flow_score traffic_score supply_score gdp_growth cpi lpr)

*==============================================================================
* 11. 诊断检验
*==============================================================================

* 序列相关检验 (面板数据)
xtserial credit_score flow_score traffic_score supply_score

* 异方差检验
hettest

* 多重共线性
vif

*==============================================================================
* 12. 图形可视化
*==============================================================================

* 信用评分分布
histogram credit_score, normal ///
    title("信用评分分布") ///
    xtitle("信用评分") freq

graph export "fig1_distribution.png", replace

* 核心变量关系
twoway (scatter credit_score flow_score) ///
    (lfit credit_score flow_score), ///
    title("信用评分 vs 资金流得分")

graph export "fig2_scatter.png", replace

* 按季度趋势
twoway (line credit_score time_index, by(id)) ///
    (line credit_score time_index, by(id)), ///
    title("信用评分时间趋势")

*==============================================================================
* End of Do-file
*==============================================================================

di "===== 分析完成 ====="
di "输出文件:"
di "  - table3_ols.csv/tex: 基准回归"
di "  - table4_fe.csv: 固定效应"
di "  - table5_gmm.csv: 动态面板"
di "  - table6_anomaly.csv: 交叉验证"
di "  - table7_robustness.csv: 稳健性检验"
di "  - descriptive_stats.log: 描述性统计"
di "  - fig1_distribution.png: 分布图"
di "  - fig2_scatter.png: 散点图"

log close
