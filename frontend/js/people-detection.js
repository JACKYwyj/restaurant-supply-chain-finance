/**
 * 客流分析 - TensorFlow.js 实时人体检测 + 个体追踪
 * 简化版：只统计进出次数，在店人数=当前追踪中的人数
 */

let tfReady = false;
let cocoModel = null;
let isDetecting = false;
let detectionHistory = [];  // 带时间戳的历史记录

// 追踪配置
const TRACKER_CONFIG = {
    maxDisappeared: 30,
    maxDistance: 400,
    iouThreshold: 0.05,
    confidenceThreshold: 0.12
};

// 追踪器状态
let nextPersonId = 1;
let peopleTracker = new Map();
let activePeopleInStore = 0;     // 当前在店人数 = 追踪中的人数
let totalEntered = 0;           // 累计进店人数
let totalExited = 0;            // 累计离店人数

// 画面分区
const ZONES = {
    ENTER_LINE: 0.75,   // 下方75%处 - 进入线
    EXIT_LINE: 0.25     // 上方25%处 - 离开线
};

function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = () => reject(new Error('Failed: ' + src));
        document.head.appendChild(script);
    });
}

async function initDetectionModel() {
    try {
        showToast('info', 'AI模型', '正在加载 AI 模型...');
        
        if (!window.tf) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0/dist/tf.min.js');
        }
        if (!window.cocoSsd) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.2/dist/coco-ssd.min.js');
        }
        
        await window.tf.ready();
        
        if (!cocoModel) {
            cocoModel = await window.cocoSsd.load({ base: 'lite_mobilenet_v2' });
            console.log('✅ COCO-SSD 加载完成');
        }
        
        tfReady = true;
        showToast('success', 'AI模型', 'AI 模型加载完成');
        return true;
        
    } catch (err) {
        console.error('❌ 模型加载失败:', err);
        showToast('error', 'AI模型', 'AI 模型加载失败');
        return false;
    }
}

async function detectPeople(video) {
    const results = [];
    try {
        if (!cocoModel) return results;
        const predictions = await cocoModel.detect(video);
        for (const pred of predictions) {
            if (pred.class === 'person' && pred.score > TRACKER_CONFIG.confidenceThreshold) {
                results.push({ bbox: pred.bbox, confidence: pred.score });
            }
        }
    } catch (err) {
        console.error('检测出错:', err);
    }
    return results;
}

function computeIoU(b1, b2) {
    const [x1,y1,w1,h1] = b1, [x2,y2,w2,h2] = b2;
    const xi1 = Math.max(x1,x2), yi1 = Math.max(y1,y2);
    const xi2 = Math.min(x1+w1,x2+w2), yi2 = Math.min(y1+h1,y2+h2);
    const inter = Math.max(0,xi2-xi1) * Math.max(0,yi2-yi1);
    const union = w1*h1 + w2*h2 - inter;
    return union > 0 ? inter/union : 0;
}

function dist(c1, c2) {
    return Math.sqrt((c1.x-c2.x)**2 + (c1.y-c2.y)**2);
}

function getCenter(b) { return { x: b[0]+b[2]/2, y: b[1]+b[3]/2 }; }

function getPosition(centerY, frameHeight) {
    const ratio = centerY / frameHeight;
    if (ratio > ZONES.ENTER_LINE) return 'bottom';
    if (ratio < ZONES.EXIT_LINE) return 'top';
    return 'middle';
}

function recordUpdate() {
    // 每次数值变化时记录时间戳
    const now = new Date();
    detectionHistory.push({
        time: now.toISOString(),
        timeStr: now.toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'}),
        inShop: activePeopleInStore,
        enterToday: totalEntered,
        exitToday: totalExited
    });
    if (detectionHistory.length > 1000) detectionHistory.shift();
    try { localStorage.setItem('cfh', JSON.stringify(detectionHistory)); } catch(e) {}
}

// 注册新人
function registerPerson(detection, frameHeight) {
    const bbox = detection.bbox;
    const c = getCenter(bbox);
    const pos = getPosition(c.y, frameHeight);
    
    // 新注册的人如果在中下方区域，计入在店和进店
    if (pos === 'middle' || pos === 'bottom') {
        activePeopleInStore++;
        totalEntered++;
        recordUpdate();
        console.log('[进入] #' + nextPersonId + ' 进店 在店:' + activePeopleInStore + ' 累计进:' + totalEntered);
    }
    
    const person = {
        id: nextPersonId++,
        bbox: [...bbox],
        center: {...c},
        position: pos,
        disappeared: 0,
        isInStore: (pos === 'middle' || pos === 'bottom'),
        firstSeen: Date.now()
    };
    
    peopleTracker.set(person.id, person);
    return person;
}

// 更新追踪者
function updatePerson(person, detection, frameHeight) {
    const newBbox = detection.bbox;
    const newCenter = getCenter(newBbox);
    const oldPos = person.position;
    const oldInStore = person.isInStore;
    const newPos = getPosition(newCenter.y, frameHeight);
    const newInStore = (newPos === 'middle' || newPos === 'bottom');
    
    person.bbox = [...newBbox];
    person.center = {...newCenter};
    person.position = newPos;
    person.isInStore = newInStore;
    person.disappeared = 0;
    
    // 从店外进入店内
    if (!oldInStore && newInStore) {
        activePeopleInStore++;
        totalEntered++;
        recordUpdate();
        console.log('[进入] #' + person.id + ' 进店 在店:' + activePeopleInStore + ' 累计进:' + totalEntered);
    }
    // 从店内离开
    else if (oldInStore && !newInStore) {
        activePeopleInStore = Math.max(0, activePeopleInStore - 1);
        totalExited++;
        recordUpdate();
        console.log('[离开] #' + person.id + ' 离店 在店:' + activePeopleInStore + ' 累计离:' + totalExited);
    }
}

// 匹配检测结果到追踪器
function matchDetections(detections, frameHeight) {
    const matchedPersons = new Set();
    
    for (const det of detections) {
        const detCenter = getCenter(det.bbox);
        let bestMatch = null;
        let bestScore = Infinity;
        
        for (const [pid, person] of peopleTracker) {
            if (matchedPersons.has(pid)) continue;
            
            const iou = computeIoU(det.bbox, person.bbox);
            const d = dist(detCenter, person.center);
            const score = d + (1 - iou) * 200;
            
            if (iou > TRACKER_CONFIG.iouThreshold || d < TRACKER_CONFIG.maxDistance) {
                if (score < bestScore) {
                    bestScore = score;
                    bestMatch = pid;
                }
            }
        }
        
        if (bestMatch !== null) {
            matchedPersons.add(bestMatch);
            updatePerson(peopleTracker.get(bestMatch), det, frameHeight);
        } else {
            let tooClose = false;
            for (const p of peopleTracker.values()) {
                if (dist(detCenter, p.center) < TRACKER_CONFIG.maxDistance * 0.5) {
                    tooClose = true; break;
                }
            }
            if (!tooClose) {
                registerPerson(det, frameHeight);
            }
        }
    }
    
    // 未匹配的人增加消失计数
    for (const [pid, person] of peopleTracker) {
        if (!matchedPersons.has(pid)) {
            person.disappeared++;
            
            // 长时间消失且之前在店
            if (person.disappeared > TRACKER_CONFIG.maxDisappeared) {
                if (person.isInStore) {
                    activePeopleInStore = Math.max(0, activePeopleInStore - 1);
                    totalExited++;
                    recordUpdate();
                    console.log('[消失] #' + pid + ' 离店(失踪) 在店:' + activePeopleInStore + ' 累计离:' + totalExited);
                }
                peopleTracker.delete(pid);
            }
        }
    }
}

// ==================== 检测循环 ====================
// 注意：videoStream, canvas, ctx2d, histInterval 由 dashboard.html 统一管理（var声明）
// 不要在这里用 let 重复声明！

async function startCamera() {
    const video = document.getElementById('cameraVideo');
    const overlay = document.getElementById('videoOverlay');
    const statsOverlay = document.getElementById('statsOverlay');
    
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } 
        });
        
        video.srcObject = videoStream;
        overlay.style.display = 'none';
        statsOverlay.style.display = 'flex';
        
        showToast('success', '摄像头', '摄像头已开启');
    } catch (err) {
        console.error('摄像头失败:', err);
        showToast('error', '摄像头', '摄像头访问失败');
    }
}

function stopCamera() {
    const video = document.getElementById('cameraVideo');
    const overlay = document.getElementById('videoOverlay');
    const statsOverlay = document.getElementById('statsOverlay');
    
    stopDetection();
    
    if (videoStream) {
        videoStream.getTracks().forEach(t => t.stop());
        videoStream = null;
    }
    
    video.srcObject = null;
    overlay.style.display = 'flex';
    statsOverlay.style.display = 'none';
    
    showToast('info', '摄像头', '摄像头已关闭');
}

async function toggleDetection() {
    if (!videoStream) {
        showToast('error', '摄像头', '请先开启摄像头');
        return;
    }

    if (isDetecting) {
        stopDetection();
        showToast('info', 'AI客流', 'AI客流分析已停止');
        return;
    }

    showToast('info', 'AI客流', '正在启动 AI 客流分析...');

    const ok = await initDetectionModel();
    if (ok) startRealDetection();
}

function startRealDetection() {
    const video = document.getElementById('cameraVideo');
    canvas = document.getElementById('detectionCanvas');
    ctx2d = canvas ? canvas.getContext('2d') : null;
    
    if (isDetecting) return;
    isDetecting = true;
    
    if (canvas) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
    }
    
    // 定期记录历史
    histInterval = setInterval(() => {
        recordUpdate();
        updateChart();
    }, 5000);
    
    // 初始记录
    recordUpdate();
    
    requestAnimationFrame(detectFrame);
    
    showToast('success', 'AI客流', 'AI 客流分析已开启');
}

async function detectFrame() {
    if (!isDetecting) return;
    
    const video = document.getElementById('cameraVideo');
    
    try {
        if (video.readyState < 2) {
            requestAnimationFrame(detectFrame);
            return;
        }
        
        const fh = video.videoHeight || 480;
        const fw = video.videoWidth || 640;
        const preds = await detectPeople(video);
        
        console.log('[检测] 发现 ' + preds.length + ' 个人体');
        
        matchDetections(preds, fh);
        
        if (ctx2d && canvas) {
            drawFrame(ctx2d, preds, fw, fh);
        }
        
        // 更新显示
        document.getElementById('enterCount').textContent = totalEntered;
        document.getElementById('shopCount').textContent = activePeopleInStore;
        document.getElementById('exitCount').textContent = totalExited;
        
        // 更新折线图
        updateChart();
        
    } catch (err) {
        console.error('检测循环错误:', err);
    }
    
    if (isDetecting) requestAnimationFrame(detectFrame);
}

function drawFrame(ctx, preds, fw, fh) {
    ctx.clearRect(0, 0, fw, fh);
    
    // 区域线
    ctx.setLineDash([8, 4]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 2;
    
    const enterY = fh * ZONES.ENTER_LINE;
    const exitY = fh * ZONES.EXIT_LINE;
    
    ctx.beginPath(); ctx.moveTo(0, enterY); ctx.lineTo(fw, enterY); ctx.stroke();
    ctx.fillStyle = '#34C759'; ctx.font = 'bold 14px Arial';
    ctx.fillText('↓ 进入线', 8, enterY - 8);
    
    ctx.beginPath(); ctx.moveTo(0, exitY); ctx.lineTo(fw, exitY); ctx.stroke();
    ctx.fillStyle = '#FF3B30';
    ctx.fillText('↑ 离开线', 8, exitY - 8);
    
    ctx.setLineDash([]);
    
    // 绘制追踪的人
    for (const [pid, person] of peopleTracker) {
        const [x, y, w, h] = person.bbox;
        
        let color = person.isInStore ? '#34C759' : '#FF9500';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
        
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 28, 70, 24);
        
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 12px Arial';
        ctx.fillText('🚶' + pid, x + 4, y - 10);
    }
    
    // 统计面板
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(fw - 190, 10, 180, 95);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 13px Arial';
    ctx.fillText('🚶 追踪中: ' + peopleTracker.size + '人', fw - 180, 32);
    ctx.fillText('📍 当前在店: ' + activePeopleInStore + '人', fw - 180, 52);
    ctx.fillText('✅ 累计进店: ' + totalEntered, fw - 180, 72);
    ctx.fillText('❌ 累计离店: ' + totalExited, fw - 180, 92);
}

function stopDetection() {
    isDetecting = false;
    if (histInterval) { clearInterval(histInterval); histInterval = null; }
    if (ctx2d && canvas) ctx2d.clearRect(0, 0, canvas.width, canvas.height);
    peopleTracker.clear();
    nextPersonId = 1;
    activePeopleInStore = 0;
    totalEntered = 0;
    totalExited = 0;
    detectionHistory = [];
    localStorage.removeItem('cfh');
    console.log('[停止] 检测已停止，计数器已重置');
}

function exportCSV() {
    if (detectionHistory.length === 0) {
        showToast('warning', '数据导出', '暂无数据');
        return;
    }
    
    // CSV 头部
    let csv = '\uFEFF'; // BOM for UTF-8
    csv += '时间,在店人数,累计进店,累计离店\n';
    
    // CSV 数据
    for (const r of detectionHistory) {
        csv += r.timeStr + ',' + r.inShop + ',' + r.enterToday + ',' + r.exitToday + '\n';
    }
    
    const blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '客流数据_' + new Date().toISOString().split('T')[0] + '.csv';
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('success', '数据导出', 'CSV 已导出');
}

// 折线图（使用 Canvas 简单绘制）
let chartCanvas = null;
let chartCtx = null;

function initChart() {
    chartCanvas = document.getElementById('flowChart');
    if (!chartCanvas) {
        // 创建图表容器
        const container = document.createElement('div');
        container.id = 'chartContainer';
        container.style.cssText = 'margin-top:15px;background:#1c1c1e;border-radius:12px;padding:15px;';
        
        const title = document.createElement('div');
        title.style.cssText = 'color:#fff;font-size:14px;font-weight:bold;margin-bottom:10px;';
        title.textContent = '📈 客流趋势';
        container.appendChild(title);
        
        chartCanvas = document.createElement('canvas');
        chartCanvas.id = 'flowChart';
        chartCanvas.style.cssText = 'width:100%;height:150px;';
        container.appendChild(chartCanvas);
        
        // 插入到视频容器下方
        const videoContainer = document.getElementById('videoContainer');
        if (videoContainer) {
            videoContainer.parentNode.insertBefore(container, videoContainer.nextSibling);
        }
    }
    chartCtx = chartCanvas.getContext('2d');
    // 使用固定尺寸，避免 offsetWidth 为 0 的问题
    chartCanvas.width = 600;
    chartCanvas.height = 200;
    console.log('[图表] 初始化完成');
}

function updateChart() {
    if (!chartCtx || !chartCanvas) {
        initChart();
        if (!chartCtx || !chartCanvas) return;
    }
    
    const w = chartCanvas.width;
    const h = chartCanvas.height;
    const ctx = chartCtx;
    
    ctx.clearRect(0, 0, w, h);
    
    // 绘制背景
    ctx.fillStyle = '#1c1c1e';
    ctx.fillRect(0, 0, w, h);
    
    // 获取数据
    const data = detectionHistory.slice(-30);
    if (data.length === 0) {
        // 无数据时显示提示
        ctx.fillStyle = '#888';
        ctx.font = '24px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('暂无数据', w / 2, h / 2);
        return;
    }
    
    // 找出最大值用于缩放
    const maxVal = Math.max(...data.map(d => d.inShop), 5);
    
    const padding = 40;
    const chartW = w - padding * 2;
    const chartH = h - padding * 2;
    
    // 绘制网格
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (chartH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(w - padding, y);
        ctx.stroke();
    }
    
    // 绘制在店人数曲线
    ctx.strokeStyle = '#34C759';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    data.forEach((d, i) => {
        const x = padding + (chartW / Math.max(data.length - 1, 1)) * i;
        const y = padding + chartH - (d.inShop / maxVal) * chartH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // 绘制数据点
    ctx.fillStyle = '#34C759';
    data.forEach((d, i) => {
        const x = padding + (chartW / Math.max(data.length - 1, 1)) * i;
        const y = padding + chartH - (d.inShop / maxVal) * chartH;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
    });
    
    // Y轴标签
    ctx.fillStyle = '#888';
    ctx.font = '16px Arial';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
        const val = Math.round(maxVal - (maxVal / 4) * i);
        const y = padding + (chartH / 4) * i + 5;
        ctx.fillText(val.toString(), padding - 8, y);
    }
    
    // X轴标签（时间）
    ctx.textAlign = 'center';
    ctx.font = '14px Arial';
    const step = Math.max(1, Math.floor(data.length / 5));
    data.forEach((d, i) => {
        if (i % step === 0 || i === data.length - 1) {
            const x = padding + (chartW / Math.max(data.length - 1, 1)) * i;
            ctx.fillText(d.timeStr, x, h - 8);
        }
    });
    
    // 图例
    ctx.fillStyle = '#34C759';
    ctx.fillRect(w - 90, 12, 15, 3);
    ctx.fillStyle = '#fff';
    ctx.font = '14px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('在店人数', w - 70, 18);
    
    // 当前数值
    const lastData = data[data.length - 1];
    ctx.fillStyle = '#34C759';
    ctx.font = 'bold 20px Arial';
    ctx.fillText('当前: ' + lastData.inShop + '人', padding, 28);
}

function resetStats() {
    peopleTracker.clear();
    nextPersonId = 1;
    activePeopleInStore = 0;
    totalEntered = 0;
    totalExited = 0;
    detectionHistory = [];
    localStorage.removeItem('cfh');
    document.getElementById('enterCount').textContent = '0';
    document.getElementById('shopCount').textContent = '0';
    document.getElementById('exitCount').textContent = '0';
    if (chartCtx) {
        chartCtx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
    }
}

window.PeopleDetector = {
    init: initDetectionModel,
    start: startRealDetection,
    stop: stopDetection,
    reset: resetStats,
    exportCSV: exportCSV,
    isRunning: () => isDetecting
};

// 页面加载时初始化图表
document.addEventListener('DOMContentLoaded', initChart);
