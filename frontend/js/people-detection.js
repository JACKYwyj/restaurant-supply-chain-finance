/**
 * 客流分析 - TensorFlow.js 实时人体检测 + 个体追踪
 * 使用 IoU (Intersection over Union) 实现跨帧人员追踪
 */

let tfReady = false;
let cocoModel = null;
let isDetecting = false;
let detectionHistory = [];

// 追踪配置
const TRACKER_CONFIG = {
    maxDisappeared: 15,       // 最多丢失15帧才删除轨迹
    maxDistance: 150,         // 最大移动距离阈值(pixel)
    iouThreshold: 0.3,        // IoU匹配阈值
    bufferSize: 3             // 稳定检测缓冲帧数
};

// 追踪器状态
let nextPersonId = 1;                          // 下一个分配的人员ID
let peopleTracker = new Map();                  // personId -> { bbox, center, disappeared, inStore, counted, stableCount }
let activePeopleInStore = 0;                    // 当前在店人数
let totalEntered = 0;                           // 今日累计进店
let totalExited = 0;                            // 今日累计离店
let lastFrameTime = 0;                          // 上一帧时间

// 画面分区（用于判断进出）
const ZONES = {
    TOP_LINE: 0.25,     // 上区进入线
    BOTTOM_LINE: 0.75   // 下区离开线
};

// 初始化
async function initDetectionModel() {
    if (cocoModel) return true;
    
    try {
        showToast('🤖 正在加载 AI 模型...', 'info');
        
        if (!window.tf) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0/dist/tf.min.js');
        }
        if (!window.cocoSsd) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.2/dist/coco-ssd.min.js');
        }
        
        await window.tf.ready();
        cocoModel = await window.cocoSsd.load({ base: 'lite_mobilenet_v2' });
        
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

function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// ==================== 核心追踪逻辑 ====================

/**
 * 计算两个 bbox 之间的 IoU
 */
function computeIoU(bbox1, bbox2) {
    const [x1, y1, w1, h1] = bbox1;
    const [x2, y2, w2, h2] = bbox2;
    
    const xi1 = Math.max(x1, x2);
    const yi1 = Math.max(y1, y2);
    const xi2 = Math.min(x1 + w1, x2 + w2);
    const yi2 = Math.min(y1 + h1, y2 + h2);
    
    const interArea = Math.max(0, xi2 - xi1) * Math.max(0, yi2 - yi1);
    const bbox1Area = w1 * h1;
    const bbox2Area = w2 * h2;
    const unionArea = bbox1Area + bbox2Area - interArea;
    
    return unionArea > 0 ? interArea / unionArea : 0;
}

/**
 * 计算两个中心点之间的欧几里得距离
 */
function computeDistance(center1, center2) {
    const dx = center1.x - center2.x;
    const dy = center1.y - center2.y;
    return Math.sqrt(dx * dx + dy * dy);
}

/**
 * 获取 bbox 中心点
 */
function getBboxCenter(bbox) {
    const [x, y, w, h] = bbox;
    return { x: x + w / 2, y: y + h / 2 };
}

/**
 * 判断人员位置区域
 * 返回: 'top'(进入区) | 'middle'(在店区) | 'bottom'(离开区)
 */
function getZone(centerY, frameHeight) {
    const ratio = centerY / frameHeight;
    if (ratio < ZONES.TOP_LINE) return 'top';
    if (ratio > ZONES.BOTTOM_LINE) return 'bottom';
    return 'middle';
}

/**
 * 注册新人员到追踪器
 */
function registerPerson(detection) {
    const bbox = detection.bbox;
    const center = getBboxCenter(bbox);
    const frameHeight = document.getElementById('cameraVideo').videoHeight || 480;
    const zone = getZone(center.y, frameHeight);
    
    const person = {
        id: nextPersonId++,
        bbox: [...bbox],
        center: { ...center },
        disappeared: 0,
        inStore: zone === 'middle' || zone === 'bottom',  // 如果在中间或下方区域则认为已在店
        counted: { enter: false, exit: false },
        zone: zone,
        firstSeen: Date.now(),
        lastSeen: Date.now()
    };
    
    peopleTracker.set(person.id, person);
    console.log(`[Tracker] 新增人员 #${person.id}, 位置: ${zone}, bbox: [${bbox.join(', ')}]`);
    
    return person;
}

/**
 * 更新追踪器中已有人员的状态
 */
function updatePerson(existingPerson, detection, frameHeight) {
    const newBbox = detection.bbox;
    const newCenter = getBboxCenter(newBbox);
    const oldCenter = existingPerson.center;
    const oldZone = existingPerson.zone;
    const newZone = getZone(newCenter.y, frameHeight);
    
    // 计算移动距离
    const moveDistance = computeDistance(oldCenter, newCenter);
    
    // 更新位置
    existingPerson.bbox = [...newBbox];
    existingPerson.center = { ...newCenter };
    existingPerson.zone = newZone;
    existingPerson.disappeared = 0;
    existingPerson.lastSeen = Date.now();
    
    // 判断进出逻辑（只计算一次）
    if (!existingPerson.counted.enter) {
        // 从顶部区域进入中间区域 = 进店
        if (oldZone === 'top' && newZone === 'middle') {
            totalEntered++;
            activePeopleInStore++;
            existingPerson.counted.enter = true;
            existingPerson.inStore = true;
            console.log(`[Tracker] #${existingPerson.id} 进店! 累计进店: ${totalEntered}, 当前在店: ${activePeopleInStore}`);
        }
        // 从顶部直接跳到下方（快速通过）
        else if (oldZone === 'top' && newZone === 'bottom') {
            totalEntered++;
            activePeopleInStore++;
            existingPerson.counted.enter = true;
            existingPerson.inStore = true;
            console.log(`[Tracker] #${existingPerson.id} 进店(快速通过)! 累计进店: ${totalEntered}`);
        }
    }
    
    if (!existingPerson.counted.exit && existingPerson.inStore) {
        // 从中间或下方区域离开画面 = 离店
        if (oldZone !== 'bottom' && newZone === 'bottom') {
            totalExited++;
            activePeopleInStore = Math.max(0, activePeopleInStore - 1);
            existingPerson.counted.exit = true;
            existingPerson.inStore = false;
            console.log(`[Tracker] #${existingPerson.id} 离店! 累计离店: ${totalExited}, 当前在店: ${activePeopleInStore}`);
        }
    }
}

/**
 * 匹配检测结果到追踪器 - 使用 IoU + 距离混合匹配
 */
function matchDetectionsToTracker(detections, frameHeight) {
    const matchedIds = new Set();
    const unmatchedDetections = [];
    
    // 第一步：IoU 匹配（高精度匹配）
    for (const detection of detections) {
        let bestMatch = null;
        let bestScore = 0;
        
        for (const [personId, person] of peopleTracker) {
            if (matchedIds.has(personId)) continue;
            
            const iou = computeIoU(detection.bbox, person.bbox);
            const distance = computeDistance(getBboxCenter(detection.bbox), person.center);
            
            // 综合评分：IoU * 0.6 + (1 - 距离/最大距离) * 0.4
            const normalizedDist = Math.min(distance / TRACKER_CONFIG.maxDistance, 1);
            const score = iou * 0.6 + (1 - normalizedDist) * 0.4;
            
            if (score > TRACKER_CONFIG.iouThreshold && score > bestScore) {
                bestScore = score;
                bestMatch = personId;
            }
        }
        
        if (bestMatch !== null) {
            matchedIds.add(bestMatch);
            updatePerson(peopleTracker.get(bestMatch), detection, frameHeight);
        } else {
            unmatchedDetections.push(detection);
        }
    }
    
    // 第二步：对未匹配的检测，尝试距离匹配
    for (const detection of unmatchedDetections) {
        const detCenter = getBboxCenter(detection.bbox);
        let bestMatch = null;
        let bestScore = Infinity;
        
        for (const [personId, person] of peopleTracker) {
            if (matchedIds.has(personId)) continue;
            
            const distance = computeDistance(detCenter, person.center);
            if (distance < TRACKER_CONFIG.maxDistance && distance < bestScore) {
                bestScore = distance;
                bestMatch = personId;
            }
        }
        
        if (bestMatch !== null) {
            matchedIds.add(bestMatch);
            updatePerson(peopleTracker.get(bestMatch), detection, frameHeight);
        } else {
            // 第三步：注册为新人员
            registerPerson(detection);
        }
    }
    
    // 增加未匹配人员的 disappeared 计数
    for (const [personId, person] of peopleTracker) {
        if (!matchedIds.has(personId)) {
            person.disappeared++;
            
            // 如果在画面外太久且已计数的，标记为离开
            if (person.disappeared > TRACKER_CONFIG.maxDisappeared) {
                if (person.inStore && !person.counted.exit) {
                    totalExited++;
                    activePeopleInStore = Math.max(0, activePeopleInStore - 1);
                    console.log(`[Tracker] #${personId} 失踪标记离店, 累计离店: ${totalExited}`);
                }
                peopleTracker.delete(personId);
                console.log(`[Tracker] 删除轨迹 #${personId}`);
            }
        }
    }
}

/**
 * 清理长时间未匹配的人员（防止漂移）
 */
function cleanupOldTracks() {
    const now = Date.now();
    for (const [personId, person] of peopleTracker) {
        // 如果5分钟内没有更新，删除
        if (now - person.lastSeen > 5 * 60 * 1000) {
            if (person.inStore && !person.counted.exit) {
                totalExited++;
                activePeopleInStore = Math.max(0, activePeopleInStore - 1);
            }
            peopleTracker.delete(personId);
            console.log(`[Tracker] 清理超时轨迹 #${personId}`);
        }
    }
}

// ==================== 检测循环 ====================

let videoStream = null;
let detectionCanvas = null;
let detectionCtx = null;
let historyInterval = null;

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
        
        showToast('📷 摄像头已开启', 'success');
    } catch (err) {
        console.error('摄像头访问失败:', err);
        if (err.name === 'NotAllowedError') {
            showToast('❌ 请允许浏览器访问摄像头权限', 'error');
        } else if (err.name === 'NotFoundError') {
            showToast('❌ 未找到可用摄像头设备', 'error');
        } else {
            showToast('❌ 摄像头访问失败: ' + err.message, 'error');
        }
    }
}

function stopCamera() {
    const video = document.getElementById('cameraVideo');
    const overlay = document.getElementById('videoOverlay');
    const statsOverlay = document.getElementById('statsOverlay');
    
    stopDetection();
    
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    
    video.srcObject = null;
    overlay.style.display = 'flex';
    statsOverlay.style.display = 'none';
    
    showToast('⏹ 摄像头已关闭', 'info');
}

async function toggleDetection() {
    const video = document.getElementById('cameraVideo');

    if (!videoStream) {
        showToast('❌ 请先开启摄像头', 'error');
        return;
    }

    if (window.PeopleDetector && window.PeopleDetector.isRunning && window.PeopleDetector.isRunning()) {
        window.PeopleDetector.stop();
        showToast('🤖 AI客流分析已停止', 'info');
        return;
    }

    showToast('🤖 正在启动 AI 客流分析...', 'info');

    (async () => {
        await window.PeopleDetector.init();
        window.PeopleDetector.start();
    })();
}

async function startRealDetection() {
    const video = document.getElementById('cameraVideo');
    detectionCanvas = document.getElementById('detectionCanvas');
    detectionCtx = detectionCanvas ? detectionCanvas.getContext('2d') : null;
    
    if (!cocoModel) {
        const loaded = await initDetectionModel();
        if (!loaded) return;
    }
    
    if (isDetecting) return;
    isDetecting = true;
    
    // 初始化画布
    if (detectionCanvas) {
        detectionCanvas.width = video.videoWidth || 640;
        detectionCanvas.height = video.videoHeight || 480;
    }
    
    // 启动历史记录
    historyInterval = setInterval(() => {
        recordCustomerFlow();
        cleanupOldTracks(); // 定期清理旧轨迹
    }, 5000);
    
    // 启动检测循环
    requestAnimationFrame(detectFrame);
    
    showToast('🤖 AI 客流分析已开启（个体追踪模式）', 'success');
}

async function detectFrame() {
    if (!isDetecting) return;
    
    const video = document.getElementById('cameraVideo');
    
    try {
        if (video.readyState < 2) {
            requestAnimationFrame(detectFrame);
            return;
        }
        
        const frameHeight = video.videoHeight || 480;
        
        // 执行检测
        const predictions = await cocoModel.detect(video);
        const people = predictions.filter(p => p.class === 'person');
        
        // 匹配到追踪器
        matchDetectionsToTracker(people, frameHeight);
        
        // 绘制检测结果
        if (detectionCtx && detectionCanvas) {
            drawDetections(detectionCtx, people, detectionCanvas.width, frameHeight);
        }
        
        // 更新显示
        updateStats();
        
    } catch (err) {
        console.error('检测出错:', err);
    }
    
    if (isDetecting) {
        requestAnimationFrame(detectFrame);
    }
}

function drawDetections(ctx, predictions, width, height) {
    ctx.clearRect(0, 0, width, height);
    
    // 绘制区域辅助线
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1;
    
    const topY = height * ZONES.TOP_LINE;
    const bottomY = height * ZONES.BOTTOM_LINE;
    
    ctx.beginPath();
    ctx.moveTo(0, topY);
    ctx.lineTo(width, topY);
    ctx.stroke();
    ctx.fillText('进入检测线', 5, topY - 5);
    
    ctx.beginPath();
    ctx.moveTo(0, bottomY);
    ctx.lineTo(width, bottomY);
    ctx.stroke();
    ctx.fillText('离开检测线', 5, bottomY - 5);
    
    ctx.setLineDash([]);
    
    // 绘制每个追踪的人员
    for (const [personId, person] of peopleTracker) {
        const [x, y, w, h] = person.bbox;
        
        // 根据状态选择颜色
        let color = '#34C759'; // 绿色 - 在店
        if (!person.inStore) {
            color = '#FF9500';  // 橙色 - 已离店待删除
        }
        if (person.counted.enter && !person.counted.exit) {
            color = '#007AFF';  // 蓝色 - 刚进店
        }
        
        // 绘制边框
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
        
        // 绘制背景标签
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 30, 80, 28);
        
        // 绘制标签文字
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px Arial';
        ctx.fillText(`#${personId}`, x + 5, y - 10);
    }
    
    // 左上角显示统计
    ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    ctx.fillRect(10, 10, 160, 80);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 14px Arial';
    ctx.fillText(`追踪中: ${peopleTracker.size}人`, 20, 32);
    ctx.fillText(`在店: ${activePeopleInStore}人`, 20, 52);
    ctx.fillText(`累计进: ${totalEntered} 出: ${totalExited}`, 20, 72);
}

function updateStats() {
    document.getElementById('enterCount').textContent = totalEntered;
    document.getElementById('shopCount').textContent = activePeopleInStore;
    document.getElementById('exitCount').textContent = totalExited;
}

function stopDetection() {
    isDetecting = false;
    
    if (historyInterval) {
        clearInterval(historyInterval);
        historyInterval = null;
    }
    
    if (detectionCtx && detectionCanvas) {
        detectionCtx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
    }
    
    // 重置追踪器
    peopleTracker.clear();
    nextPersonId = 1;
}

// ==================== 历史记录 ====================

function recordCustomerFlow() {
    const now = new Date();
    const record = {
        time: now.toISOString(),
        timeStr: now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        inShop: activePeopleInStore,
        enterToday: totalEntered,
        exitToday: totalExited
    };
    
    detectionHistory.push(record);
    if (detectionHistory.length > 288) {
        detectionHistory.shift();
    }
    
    try {
        localStorage.setItem('customerFlowHistory', JSON.stringify(detectionHistory));
    } catch (e) {
        console.warn('localStorage 存储已满');
    }
}

function restoreCustomerFlowData() {
    try {
        const saved = localStorage.getItem('customerFlowHistory');
        if (saved) {
            detectionHistory = JSON.parse(saved);
        }
        
        const today = new Date().toDateString();
        const todayRecords = detectionHistory.filter(r => 
            new Date(r.time).toDateString() === today
        );
        
        if (todayRecords.length > 0) {
            const last = todayRecords[todayRecords.length - 1];
            totalEntered = last.enterToday || 0;
            totalExited = last.exitToday || 0;
            activePeopleInStore = last.inShop || 0;
        }
    } catch (e) {
        console.warn('恢复客流数据失败:', e);
    }
}

function resetCustomerStats() {
    peopleTracker.clear();
    nextPersonId = 1;
    activePeopleInStore = 0;
    totalEntered = 0;
    totalExited = 0;
    detectionHistory = [];
    localStorage.removeItem('customerFlowHistory');
    updateStats();
}

function exportCustomerFlowData() {
    if (detectionHistory.length === 0) {
        showToast('暂无客流数据', 'warning');
        return;
    }
    
    const data = {
        exportTime: new Date().toISOString(),
        total: { enter: totalEntered, exit: totalExited, current: activePeopleInStore },
        history: detectionHistory
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `客流数据_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('📥 客流数据已导出', 'success');
}

// ==================== 全局导出 ====================

window.PeopleDetector = {
    init: initDetectionModel,
    start: startRealDetection,
    stop: stopDetection,
    reset: resetCustomerStats,
    export: exportCustomerFlowData,
    isRunning: () => isDetecting
};

// 页面加载时恢复数据
document.addEventListener('DOMContentLoaded', restoreCustomerFlowData);
