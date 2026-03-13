/*==============================================================================
生成模拟商户数据 - 区域与行业虚拟变量
RTV模型模拟数据生成

生成100家商户的区域和行业信息
==============================================================================*/

clear
set seed 20260312
set obs 100

* 商户ID
gen merchant_id = _n

* 商户名称
gen merchant_name = "商户" + string(_n)

*===== 区域虚拟变量生成 =====*

* 区域分布 (参考中国城市分级)
* 一线城市: 20%
* 二线城市: 30%  
* 三四线城市: 35%
* 县域: 15%

gen rand_region = uniform()
gen region = .
replace region = 1 if rand_region < 0.20  // T1 一线城市
replace region = 2 if rand_region >= 0.20 & rand_region < 0.50  // T2 二线城市
replace region = 3 if rand_region >= 0.50 & rand_region < 0.85  // T3 三四线
replace region = 4 if rand_region >= 0.85  // T4 县域

* 区域名称
gen region_name = ""
replace region_name = "一线城市" if region == 1
replace region_name = "二线城市" if region == 2
replace region_name = "三四线城市" if region == 3
replace region_name = "县域" if region == 4

* 区域虚拟变量
gen t1 = (region == 1)
gen t2 = (region == 2)
gen t3 = (region == 3)
gen t4 = (region == 4)

*===== 行业虚拟变量生成 =====*

* 行业分布
* 正餐: 25%
* 快餐: 30%
* 火锅: 20%
* 饮品: 15%
* 其他: 10%

gen rand_industry = uniform()
gen industry = .
replace industry = 1 if rand_industry < 0.25  // I1 正餐
replace industry = 2 if rand_industry >= 0.25 & rand_industry < 0.55  // I2 快餐
replace industry = 3 if rand_industry >= 0.55 & rand_industry < 0.75  // I3 火锅
replace industry = 4 if rand_industry >= 0.75 & rand_industry < 0.90  // I4 饮品
replace industry = 5 if rand_industry >= 0.90  // I5 其他

* 行业名称
gen industry_name = ""
replace industry_name = "正餐" if industry == 1
replace industry_name = "快餐小吃" if industry == 2
replace industry_name = "火锅" if industry == 3
replace industry_name = "饮品甜品" if industry == 4
replace industry_name = "其他" if industry == 5

* 行业虚拟变量
gen i1 = (industry == 1)
gen i2 = (industry == 2)
gen i3 = (industry == 3)
gen i4 = (industry == 4)
gen i5 = (industry == 5)

*===== 添加城市信息 =====*

* 一线城市
gen city = ""
replace city = "北京" if region == 1 & uniform() < 0.25
replace city = "上海" if region == 1 & uniform() < 0.25
replace city = "广州" if region == 1 & uniform() < 0.25
replace city = "深圳" if region == 1 & city == ""

* 二线城市
replace city = "杭州" if region == 2 & uniform() < 0.10
replace city = "南京" if region == 2 & uniform() < 0.10
replace city = "成都" if region == 2 & uniform() < 0.10
replace city = "武汉" if region == 2 & uniform() < 0.10
replace city = "西安" if region == 2 & uniform() < 0.10
replace city = "重庆" if region == 2 & uniform() < 0.10
replace city = "天津" if region == 2 & uniform() < 0.10
replace city = "苏州" if region == 2 & uniform() < 0.10
replace city = "长沙" if region == 2 & uniform() < 0.10
replace city = "郑州" if region == 2 & city == ""

* 三四线城市 (示例)
replace city = "无锡" if region == 3 & uniform() < 0.10
replace city = "宁波" if region == 3 & uniform() < 0.10
replace city = "青岛" if region == 3 & uniform() < 0.10
replace city = "济南" if region == 3 & uniform() < 0.10
replace city = "大连" if region == 3 & uniform() < 0.10
replace city = "厦门" if region == 3 & uniform() < 0.10
replace city = "福州" if region == 3 & uniform() < 0.10
replace city = "沈阳" if region == 3 & uniform() < 0.10
replace city = "昆明" if region == 3 & uniform() < 0.10
replace city = "哈尔滨" if region == 3 & city == ""

* 县域 (示例)
replace city = "义乌" if region == 4 & uniform() < 0.15
replace city = "昆山" if region == 4 & uniform() < 0.15
replace city = "常熟" if region == 4 & uniform() < 0.15
replace city = "张家港" if region == 4 & uniform() < 0.15
replace city = "江阴" if region == 4 & uniform() < 0.15
replace city = "慈溪" if region == 4 & uniform() < 0.15
replace city = "余姚" if region == 4 & uniform() < 0.15
replace city = "海宁" if region == 4 & uniform() < 0.10
replace city = "桐乡" if region == 4 & uniform() < 0.10
replace city = "其他县级市" if region == 4 & city == ""

* 完整地址
gen address = city + "市辖区"

*===== 标签 =====*
label var merchant_id "商户ID"
label var merchant_name "商户名称"
label var address "地址"
label var region "区域代码"
label var region_name "区域名称"
label var city "城市"
label var industry "行业代码"
label var industry_name "行业名称"
label var t1 "一线城市"
label var t2 "二线城市"
label var t3 "三四线城市"
label var t4 "县域"
label var i1 "正餐"
label var i2 "快餐"
label var i3 "火锅"
label var i4 "饮品"
label var i5 "其他"

*===== 保存 =====*
save "merchant_info.dta", replace

*===== 统计 =====*
di "===== 区域分布 ====="
tab region_name

di "===== 行业分布 ====="
tab industry_name

di "===== 交叉分布 ====="
tab region_name industry_name

*===== 导出Excel =====*
export excel using "merchant_info.xlsx", replace firstrow(varlabels)

di "数据已保存到 merchant_info.dta 和 merchant_info.xlsx"
