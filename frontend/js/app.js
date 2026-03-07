// 餐饮供应链金融平台 - 前端交互脚本

document.addEventListener('DOMContentLoaded', function() {
    console.log('餐饮供应链金融平台已加载');
    
    // 初始化图表动画
    initChartAnimation();
    
    // 初始化实时时钟
    initClock();
    
    // 模拟实时数据更新
    initRealTimeUpdates();
});

// 图表动画效果
function initChartAnimation() {
    const bars = document.querySelectorAll('.chart-bar');
    if (bars.length === 0) return;
    
    bars.forEach((bar, index) => {
        const height = bar.style.height;
        bar.style.height = '0';
        
        setTimeout(() => {
            bar.style.transition = 'height 0.8s ease-out';
            bar.style.height = height;
        }, index * 100);
    });
}

// 实时时钟
function initClock() {
    // 可以添加实时时钟功能
    console.log('时钟初始化完成');
}

// 实时数据更新模拟
function initRealTimeUpdates() {
    // 模拟客流数据实时更新
    setInterval(() => {
        const statValue = document.querySelector('.stat-card .stat-value');
        if (statValue && statValue.textContent.includes('328')) {
            // 模拟客流微调
            const currentValue = parseInt(statValue.textContent);
            const newValue = currentValue + Math.floor(Math.random() * 3);
            statValue.textContent = newValue;
        }
    }, 30000); // 每30秒更新一次
}

// 格式化金额
function formatAmount(amount) {
    return '¥' + amount.toLocaleString('zh-CN');
}

// 显示通知
function showNotification(message, type = 'info') {
    // 可以扩展为Toast通知
    console.log(`[${type}] ${message}`);
}

// 导出全局函数供控制台调试
window.FinanceApp = {
    formatAmount,
    showNotification
};
