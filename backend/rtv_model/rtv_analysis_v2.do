/*==============================================================================
RTV Credit Scoring Model - 完整版Stata分析代码 (v2.0)
基于真实宏观数据(Bloomberg)进行实证分析

数据: rtv_panel_data_real.xlsx (100家商户, 2017Q1-2024Q4)
宏观数据: Bloomberg真实数据 (GDP, CPI, M2, LPR)
作者: Jacky Wang
日期: 2026-03-12
==============================================================================*/

clear all
set more off
cap log close

*==============================================================================
* 0. 设置工作目录
*==============================================================================
cd "/Users/wangyunjie/Desktop/RTV_Project"

*==============================================================================
* 1. 数据导入
*==============================================================================
import excel "rtv_panel_data_real.xlsx", sheet("Sheet1") firstrow clear

* 设置面板数据
xtset merchant_id time_index

* 保存为Stata格式
save "rtv_panel_data_real.dta", replace

*==============================================================================
* 2. 描述性统计
*==============================================================================
log using "descriptive_stats.log", replace

di "===== 表1: 描述性统计 ====="
sum credit_score flow_score traffic_score supply_score default credit_limit, detail

di "===== 宏观变量描述性统计 ====="
sum gdp_growth cpi lpr m2_growth, detail

di "===== 按季度均值 ====="
bys quarter: sum credit_score flow_score traffic_score supply_score

di "===== 按区域均值 ====="
bys region: sum credit_score flow_score traffic_score supply_score

di "===== 按行业均值 ====="
bys industry: sum credit_score flow_score traffic_score supply_score

di "===== 违约率 ====="
tab default

log close

*==============================================================================
* 3. 相关性分析
*==============================================================================
di "===== 表2: 相关系数矩阵 ====="
pwcorr credit_score flow_score traffic_score supply_score, star(0.05)

*==============================================================================
* 4. OLS回归
*==============================================================================
cap ssc install estout, replace
cap ssc install outreg2, replace

eststo clear

* 模型1: 仅核心变量
eststo: reg credit_score flow_score traffic_score supply_score, robust

* 模型2: 加入季节虚拟变量
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4, robust

* 模型3: 加入宏观变量
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth, robust

* 模型4: 加入区域和行业固定效应 (全部控制变量)
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth t2 t3 t4 i2 i3 i4 i5, robust

* 输出结果
esttab using "table1_ols.csv", replace ///
    title("表1: OLS基准回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress r2

esttab using "table1_ols.tex", replace ///
    title("表1: OLS基准回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress booktabs

*==============================================================================
* 5. 固定效应模型
*==============================================================================
eststo clear

* 模型5: 商户固定效应
xtreg credit_score flow_score traffic_score supply_score q2 q3 q4, fe robust

* 模型6: 双向固定效应
xtreg credit_score flow_score traffic_score supply_score q2 q3 q4 i.time_index, fe robust

* 模型7: 加入宏观的双向固定效应
xtreg credit_score flow_score traffic_score supply_score q2 q3 q4 ///
    gdp_growth cpi lpr m2_growth i.time_index, fe robust

esttab using "table2_fe.csv", replace ///
    title("表2: 固定效应模型") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap compress r2

*==============================================================================
* 6. 动态面板模型 (System GMM)
*==============================================================================
cap ssc install xtabond2, replace

eststo clear

* 模型8: System GMM
xtabond2 credit_score L.credit_score flow_score traffic_score supply_score ///
    q2 q3 gdp_growth cpi, ///
    gmm(L.credit_score flow_score traffic_score supply_score, lag(1 2)) ///
    iv(q2 q3 gdp_growth cpi) ///
    twostep robust

esttab using "table3_gmm.csv", replace ///
    title("表3: System GMM回归") ///
    se star(* 0.10 ** 0.05 *** 0.01) ///
    nogap

*==============================================================================
* 7. 交叉验证分析
*==============================================================================
gen anomaly_ratio = flow_score / traffic_score
gen anomaly_flag = (anomaly_ratio < 0.8 | anomaly_ratio > 1.2)

di "===== 交叉验证异常比例 ====="
tab anomaly_flag

eststo clear
eststo: reg credit_score flow_score traffic_score supply_score anomaly_flag, robust
eststo: xtreg credit_score flow_score traffic_score supply_score anomaly_flag, fe robust

esttab using "table4_anomaly.csv", replace

*==============================================================================
* 8. 稳健性检验
*==============================================================================
eststo clear

* 检验1: Logit违约概率
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
eststo: reg w_credit_score w_flow_score w_traffic_score w_supply_score q2 q3 q4, robust

* 检验4: 分区域回归
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t1 == 1, robust
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t2 == 1, robust
eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t3 == 1, robust

esttab using "table5_robustness.csv", replace

*==============================================================================
* 9. 安慰剂检验
*==============================================================================
set seed 12345
gen placebo_flow = rnormal(0.8, 0.3)
gen placebo_traffic = rnormal(0.7, 0.35)

reg credit_score placebo_flow placebo_traffic q2 q3 q4, robust

di "如果安慰剂变量系数不显著, 则说明基准回归结果稳健"

*==============================================================================
* 10. 结果输出汇总
*==============================================================================
eststo clear

eststo: reg credit_score flow_score traffic_score supply_score q2 q3 q4 gdp_growth cpi lpr m2_growth t2 t3 t4 i2 i3 i4 i5, robust
eststo: xtreg credit_score flow_score traffic_score supply_score q2 q3 q4, fe robust
eststo: xtreg credit_score flow_score traffic_score supply_score q2 q3 q4 gdp_growth cpi lpr m2_growth i.time_index, fe robust

outreg2 using "full_results.doc", replace ///
    title("RTV模型回归结果汇总") ///
    ctitle("OLS", "FE", "TWF") ///
    label dec(3)

outreg2 using "descriptive.doc", replace ///
    sum/title("描述性统计") ///
    label dec(3) ///
    keep(credit_score flow_score traffic_score supply_score gdp_growth cpi lpr)

*==============================================================================
* 11. 诊断检验
*==============================================================================
di "===== 诊断检验 ====="

* 序列相关
di "--- 序列相关检验 ---"
xtserial credit_score flow_score traffic_score supply_score

* 异方差
di "--- 异方差检验 ---"
hettest

* 多重共线性
di "--- 多重共线性 ---"
vif

*==============================================================================
* 12. 可视化
*==============================================================================
set scheme s1color

* 分布图
histogram credit_score, normal ///
    title("信用评分分布") ///
    xtitle("信用评分") freq
graph export "fig1_distribution.png", replace

* 散点图
twoway (scatter credit_score flow_score) ///
    (lfit credit_score flow_score), ///
    title("信用评分 vs 资金流得分")
graph export "fig2_flow.png", replace

twoway (scatter credit_score traffic_score) ///
    (lfit credit_score traffic_score), ///
    title("信用评分 vs 客流得分")
graph export "fig3_traffic.png", replace

twoway (scatter credit_score supply_score) ///
    (lfit credit_score supply_score), ///
    title("信用评分 vs 供应链得分")
graph export "fig4_supply.png", replace

* 箱线图
graph box credit_score, over(region) ///
    title("信用评分按区域分布")
graph export "fig5_region.png", replace

graph box credit_score, over(industry) ///
    title("信用评分按行业分布")
graph export "fig6_industry.png", replace

* 时间趋势
collapse (mean) credit_score flow_score traffic_score supply_score, by(year quarter)
gen time = yq(year, quarter)
tsset time
twoway (line credit_score time) ///
    (line flow_score time) ///
    (line traffic_score time) ///
    (line supply_score time), ///
    title("各指标时间趋势") ///
    legend(label(1 "信用评分") label(2 "资金流") label(3 "客流") label(4 "供应链"))
graph export "fig7_trend.png", replace

*==============================================================================
* 13. 异质性分析
*==============================================================================
eststo clear

di "===== 异质性分析: 按区域 ====="
reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t1 == 1, robust
reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t2 == 1, robust
reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t3 == 1, robust
reg credit_score flow_score traffic_score supply_score q2 q3 q4 if t4 == 1, robust

di "===== 异质性分析: 按行业 ====="
forvalues i = 1/5 {
    reg credit_score flow_score traffic_score supply_score q2 q3 q4 if industry == `i', robust
}

*==============================================================================
* 14. 结束
*==============================================================================
di ""
di "=========================================="
di "       RTV模型分析完成 (v2.0)"
di "=========================================="
di ""
di "输出文件:"
di "  - table1_ols.csv/tex: OLS回归"
di "  - table2_fe.csv: 固定效应"
di "  - table3_gmm.csv: 动态面板"
di "  - table4_anomaly.csv: 交叉验证"
di "  - table5_robustness.csv: 稳健性检验"
di "  - descriptive_stats.log: 描述性统计"
di "  - full_results.doc: 完整结果"
di "  - fig1-7.png: 图形"
di ""
di "数据来源:"
di "  - 宏观数据: Bloomberg (真实)"
di "  - 商户数据: 模拟数据"
di ""
di "=========================================="

log close
