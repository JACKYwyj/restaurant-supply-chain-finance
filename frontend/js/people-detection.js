/**
 * 客流分析 - TensorFlow.js 实时人体检测
 * 使用 COCO-SSD 模型进行人体检测和客流统计
 */

let tfReady = false;
let cocoModel = null;
let isDetecting = false;
let detectionHistory = [];  // 客流变化历史记录
let lastPeopleCount = 0;
let enterCount = 0;
let exitCount = 0;
let shopCount = 0;

// 进出方向检测配置
const REGION_OF_INTEREST = {
    top: 0.3,      // 画面上方30%区域 - 进入检测线
    bottom: 0.7,   // 画面下方70%区域 - 离开检测线
    left: 0.1,
    right: 0.9
};

// 稳定检测阈值（避免误检）
const STABILITY_THRESHOLD = 3;  // 连续3帧检测到才确认
let detectionBuffer = [];  // 缓存最近检测结果
const BUFFER_SIZE = 5;

// 初始化 TensorFlow.js 和 COCO-SSD 模型
async function initDetectionModel() {
    if (cocoModel) return true;
    
    try {
        showToast('🤖 正在加载 AI 模型...', 'info');
        
        // 动态加载 TensorFlow.js
        if (!window.tf) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0/dist/tf.min.js');
        }
        
        // 加载 COCO-SSD 模型
        if (!window.cocoSsd) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.2/dist/coco-ssd.min.js');
        }
        
        await window.tf.ready();
        cocoModel = await window.cocoSsd.load({
            base: 'lite_mobilenet_v2'  // 使用轻量级模型，更快
        });
        
        tfReady = true;
        console.log('✅ AI 模型加载完成');
        showToast('✅ AI 模型加载完成', 'success');
        return true;
        
    } catch (err) {
        console.error('模型加载失败:', err);
        showToast('❌ AI 模型加载失败: ' + err.message, 'error');
        return false;
    }
}

// 动态加载脚本
function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) {
            resolve();
            return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// 启动实时客流检测
async function startRealDetection() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('detectionCanvas');
    const ctx = canvas ? canvas.getContext('2d') : null;
    
    if (!cocoModel) {
        const loaded = await initDetectionModel();
        if (!loaded) return;
    }
    
    if (isDetecting) return;
    isDetecting = true;
    
    // 设置画布尺寸
    if (canvas) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
    }
    
    // 每次检测后记录历史
    let historyInterval = setInterval(() => {
        if (shopCount > 0 || detectionHistory.length > 0) {
            recordCustomerFlow();
        }
    }, 5000);  // 每5秒记录一次客流状态
    
    // 检测循环
    async function detectFrame() {
        if (!isDetecting) return;
        
        try {
            // 确保视频已加载
            if (video.readyState < 2) {
                requestAnimationFrame(detectFrame);
                return;
            }
            
            // 执行检测
            const predictions = await cocoModel.detect(video);
            
            // 筛选人体检测结果
            const people = predictions.filter(p => p.class === 'person');
            const currentCount = people.length;
            
            // 稳定检测：使用缓冲区平滑结果
            detectionBuffer.push(currentCount);
            if (detectionBuffer.length > BUFFER_SIZE) {
                detectionBuffer.shift();
            }
            const stableCount = Math.round(
                detectionBuffer.reduce((a, b) => a + b, 0) / detectionBuffer.length
            );
            
            // 检测客流变化
            detectCustomerFlow(stableCount);
            
            // 绘制检测结果
            if (ctx && canvas) {
                drawDetections(ctx, people, canvas.width, canvas.height);
            }
            
            // 更新显示
            updateStats();
            
        } catch (err) {
            console.error('检测出错:', err);
        }
        
        // 继续检测循环
        if (isDetecting) {
            requestAnimationFrame(detectFrame);
        }
    }
    
    // 保存 interval ID 供停止时清理
    window._detectionHistoryInterval = historyInterval;
    
    detectFrame();
    showToast('🤖 AI 客流分析已开启（真人识别模式）', 'success');
}

// 检测客流变化（进入/离开）
function detectCustomerFlow(currentCount) {
    if (lastPeopleCount === 0 && currentCount > 0) {
        // 首次检测到人
        shopCount = currentCount;
    } else if (currentCount > lastPeopleCount) {
        // 人数增加 = 有人进入
        const diff = currentCount - lastPeopleCount;
        for (let i = 0; i < diff; i++) {
            enterCount++;
            shopCount++;
        }
    } else if (currentCount < lastPeopleCount && shopCount > 0) {
        // 人数减少 = 有人离开
        const diff = lastPeopleCount - currentCount;
        for (let i = 0; i < diff && shopCount > 0; i++) {
            exitCount++;
            shopCount--;
        }
    }
    
    lastPeopleCount = currentCount;
}

// 在画面上绘制检测框
function drawDetections(ctx, predictions, width, height) {
    // 清空画布
    ctx.clearRect(0, 0, width, height);
    
    predictions.forEach(pred => {
        const [x, y, w, h] = pred.bbox;
        
        // 根据是否在店绘制不同颜色
        const color = '#34C759';  // 绿色 - 在店顾客
        
        // 绘制边框
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        
        // 绘制背景标签
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 25, 60, 25);
        
        // 绘制标签文字
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px Arial';
        ctx.fillText('顾客', x + 5, y - 7);
    });
    
    // 绘制检测区域辅助线
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1;
    
    const topY = height * REGION_OF_INTEREST.top;
    const bottomY = height * REGION_OF_INTEREST.bottom;
    
    ctx.beginPath();
    ctx.moveTo(0, topY);
    ctx.lineTo(width, topY);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(0, bottomY);
    ctx.lineTo(width, bottomY);
    ctx.stroke();
    
    ctx.setLineDash([]);
    
    // 在画面左上角显示当前人数
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, 10, 100, 40);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('当前: ' + predictions.length + '人', 20, 35);
}

// 记录客流变化到历史
function recordCustomerFlow() {
    const now = new Date();
    const record = {
        time: now.toISOString(),
        timeStr: now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        inShop: shopCount,
        enterToday: enterCount,
        exitToday: exitCount
    };
    
    detectionHistory.push(record);
    
    // 只保留最近 288 条记录（每5秒一次，可存24小时）
    if (detectionHistory.length > 288) {
        detectionHistory.shift();
    }
    
    // 保存到 localStorage
    try {
        localStorage.setItem('customerFlowHistory', JSON.stringify(detectionHistory));
    } catch (e) {
        console.warn('localStorage 存储已满');
    }
    
    // 更新客流趋势图
    updateCustomerFlowChart();
}

// 更新客流趋势图
function updateCustomerFlowChart() {
    const chartContainer = document.getElementById('customerFlowChart');
    if (!chartContainer || detectionHistory.length < 2) return;
    
    // 简化版：用文字显示最近记录
    const recent = detectionHistory.slice(-10);
    const labels = recent.map(r => r.timeStr);
    const values = recent.map(r => r.inShop);
    
    // 更新统计卡片
    document.getElementById('enterCount').textContent = enterCount;
    document.getElementById('shopCount').textContent = shopCount;
    document.getElementById('exitCount').textContent = exitCount;
}

// 停止检测
function stopDetection() {
    isDetecting = false;
    
    if (window._detectionHistoryInterval) {
        clearInterval(window._detectionHistoryInterval);
        window._detectionHistoryInterval = null;
    }
    
    // 清空画布
    const canvas = document.getElementById('detectionCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

// 重置统计数据
function resetCustomerStats() {
    enterCount = 0;
    exitCount = 0;
    shopCount = 0;
    lastPeopleCount = 0;
    detectionHistory = [];
    detectionBuffer = [];
    localStorage.removeItem('customerFlowHistory');
    updateStats();
}

// 获取客流历史数据
function getCustomerFlowHistory() {
    return detectionHistory;
}

// 导出客流数据
function exportCustomerFlowData() {
    if (detectionHistory.length === 0) {
        showToast('暂无客流数据', 'warning');
        return;
    }
    
    const data = {
        exportTime: new Date().toISOString(),
        total: {
            enter: enterCount,
            exit: exitCount,
            current: shopCount
        },
        history: detectionHistory
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `客流数据_${new Date().toFormatString('YYYY-MM-DD')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('📥 客流数据已导出', 'success');
}

// 从 localStorage 恢复数据
function restoreCustomerFlowData() {
    try {
        const saved = localStorage.getItem('customerFlowHistory');
        if (saved) {
            detectionHistory = JSON.parse(saved);
        }
        
        // 从今日第一条恢复计数
        const today = new Date().toDateString();
        const todayRecords = detectionHistory.filter(r => 
            new Date(r.time).toDateString() === today
        );
        
        if (todayRecords.length > 0) {
            const last = todayRecords[todayRecords.length - 1];
            enterCount = last.enterToday;
            exitCount = last.exitToday;
            shopCount = last.inShop;
        }
    } catch (e) {
        console.warn('恢复客流数据失败:', e);
    }
}

// 页面加载时恢复数据
document.addEventListener('DOMContentLoaded', restoreCustomerFlowData);

// 全局导出函数
window.PeopleDetector = {
    init: initDetectionModel,
    start: startRealDetection,
    stop: stopDetection,
    reset: resetCustomerStats,
    getHistory: getCustomerFlowHistory,
    export: exportCustomerFlowData
};

// 暴露关键变量到全局（供 dashboard.html 访问）
// 注意：这些会覆盖 dashboard.html 中的局部变量声明
window.getEnterCount = () => enterCount;
window.getExitCount = () => exitCount;
window.getShopCount = () => shopCount;
window.getIsDetecting = () => isDetecting;
