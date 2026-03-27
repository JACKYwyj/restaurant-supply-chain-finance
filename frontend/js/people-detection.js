/**
 * 客流分析 - TensorFlow.js 实时人体检测 + 个体追踪
 * 双模式：BlazeFace人脸检测 + COCO-SSD人体检测，上半身即可识别
 */

let tfReady = false;
let cocoModel = null;
let faceModel = null;
let isDetecting = false;
let detectionHistory = [];

// 追踪配置
const TRACKER_CONFIG = {
    maxDisappeared: 20,
    maxDistance: 250,
    iouThreshold: 0.15,
    confidenceThreshold: 0.25
};

// 追踪器状态
let nextPersonId = 1;
let peopleTracker = new Map();
let activePeopleInStore = 0;
let totalEntered = 0;
let totalExited = 0;

// 画面分区
const ZONES = {
    TOP_LINE: 0.30,
    BOTTOM_LINE: 0.80
};

// 加载脚本
function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = () => {
            console.warn('脚本加载失败:', src);
            reject(new Error(`Failed to load: ${src}`));
        };
        document.head.appendChild(script);
    });
}

// 初始化
async function initDetectionModel() {
    if (cocoModel && faceModel) return true;
    
    try {
        showToast('🤖 正在加载 AI 模型...', 'info');
        
        // 加载 TensorFlow.js 核心
        if (!window.tf) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0/dist/tf.min.js');
        }
        
        // 加载 BlazeFace (人脸检测 - 快速、侧脸也能检测)
        if (!window.blazeface) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface@0.1.0/dist/blazeface.min.js');
        }
        
        // 加载 COCO-SSD (人体检测 - 补充)
        if (!window.cocoSsd) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.2/dist/coco-ssd.min.js');
        }
        
        await window.tf.ready();
        
        // 初始化人脸检测模型
        if (!faceModel) {
            faceModel = await window.blazeface.load({
                backend: 'tfjs',
                maxFaces: 10
            });
            console.log('✅ BlazeFace 模型加载完成');
        }
        
        // 初始化人体检测模型
        if (!cocoModel) {
            cocoModel = await window.cocoSsd.load({
                base: 'lite_mobilenet_v2',
                scoreThreshold: TRACKER_CONFIG.confidenceThreshold
            });
            console.log('✅ COCO-SSD 模型加载完成');
        }
        
        tfReady = true;
        showToast('✅ AI 模型加载完成 (人脸+人体双模式)', 'success');
        return true;
        
    } catch (err) {
        console.error('模型加载失败:', err);
        showToast('❌ AI 模型加载失败: ' + err.message, 'error');
        return false;
    }
}

// ==================== 检测 ====================

/**
 * 综合检测：BlazeFace人脸 + COCO人体
 */
async function detectPeople(video) {
    const results = [];
    
    try {
        // 1. BlazeFace 人脸检测（主要，对上半身/侧脸友好）
        if (faceModel) {
            const faces = await faceModel.estimateFaces(video, false);
            
            for (const face of faces) {
                // 使用 start/end 关键点确定人脸区域
                const topLeft = face.topLeft;
                const bottomRight = face.bottomRight;
                const faceWidth = bottomRight[0] - topLeft[0];
                const faceHeight = bottomRight[1] - topLeft[1];
                
                // 扩展为上半身区域
                const expandedBbox = [
                    topLeft[0] - faceWidth * 0.5,
                    topLeft[1] - faceHeight * 2.5,
                    faceWidth * 2,
                    faceHeight * 4
                ];
                
                // 检查置信度
                const prob = face.probability ? face.probability[0] : 0.9;
                if (prob > 0.5) {
                    results.push({
                        class: 'face',
                        bbox: expandedBbox,
                        confidence: prob,
                        type: 'face'
                    });
                }
            }
        }
        
        // 2. COCO-SSD 人体检测（补充）
        if (cocoModel) {
            const bodies = await cocoModel.detect(video);
            
            for (const pred of bodies) {
                if (pred.class === 'person' && pred.score > TRACKER_CONFIG.confidenceThreshold) {
                    results.push({
                        class: 'person',
                        bbox: pred.bbox,
                        confidence: pred.score,
                        type: 'body'
                    });
                }
            }
        }
        
    } catch (err) {
        console.error('检测出错:', err);
    }
    
    return results;
}

// ==================== 追踪 ====================

function computeIoU(bbox1, bbox2) {
    const [x1, y1, w1, h1] = bbox1;
    const [x2, y2, w2, h2] = bbox2;
    
    const xi1 = Math.max(x1, x2);
    const yi1 = Math.max(y1, y2);
    const xi2 = Math.min(x1 + w1, x2 + w2);
    const yi2 = Math.min(y1 + h1, y2 + h2);
    
    const interArea = Math.max(0, xi2 - xi1) * Math.max(0, yi2 - yi1);
    const unionArea = w1 * h1 + w2 * h2 - interArea;
    
    return unionArea > 0 ? interArea / unionArea : 0;
}

function computeDistance(center1, center2) {
    return Math.sqrt(Math.pow(center1.x - center2.x, 2) + Math.pow(center1.y - center2.y, 2));
}

function getBboxCenter(bbox) {
    return { x: bbox[0] + bbox[2] / 2, y: bbox[1] + bbox[3] / 2 };
}

function getZone(centerY, frameHeight) {
    const ratio = centerY / frameHeight;
    if (ratio < ZONES.TOP_LINE) return 'top';
    if (ratio > ZONES.BOTTOM_LINE) return 'bottom';
    return 'middle';
}

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
        inStore: zone === 'middle' || zone === 'bottom',
        counted: { enter: false, exit: false },
        zone: zone,
        type: detection.type,
        firstSeen: Date.now(),
        lastSeen: Date.now()
    };
    
    peopleTracker.set(person.id, person);
    console.log(`[Tracker] 新增 #${person.id} (${detection.type}) 位置: ${zone}`);
    
    return person;
}

function updatePerson(existingPerson, detection, frameHeight) {
    const newBbox = detection.bbox;
    const newCenter = getBboxCenter(newBbox);
    const oldZone = existingPerson.zone;
    const newZone = getZone(newCenter.y, frameHeight);
    
    existingPerson.bbox = [...newBbox];
    existingPerson.center = { ...newCenter };
    existingPerson.zone = newZone;
    existingPerson.disappeared = 0;
    existingPerson.lastSeen = Date.now();
    existingPerson.type = detection.type;
    
    // 判断进出
    if (!existingPerson.counted.enter) {
        if ((oldZone === 'top' && newZone === 'middle') || 
            (oldZone === 'top' && newZone === 'bottom')) {
            totalEntered++;
            activePeopleInStore++;
            existingPerson.counted.enter = true;
            existingPerson.inStore = true;
            console.log(`[Tracker] #${existingPerson.id} 进店! 累计: ${totalEntered}`);
        }
    }
    
    if (!existingPerson.counted.exit && existingPerson.inStore) {
        if (oldZone !== 'bottom' && newZone === 'bottom') {
            totalExited++;
            activePeopleInStore = Math.max(0, activePeopleInStore - 1);
            existingPerson.counted.exit = true;
            existingPerson.inStore = false;
            console.log(`[Tracker] #${existingPerson.id} 离店! 累计: ${totalExited}`);
        }
    }
}

function matchDetectionsToTracker(detections, frameHeight) {
    // 为每个检测结果找匹配
    for (const detection of detections) {
        const detCenter = getBboxCenter(detection.bbox);
        let bestMatch = null;
        let bestScore = Infinity;
        
        for (const [personId, person] of peopleTracker) {
            const iou = computeIoU(detection.bbox, person.bbox);
            const distance = computeDistance(detCenter, person.center);
            
            // 优先用IoU匹配，其次用距离
            if (iou > TRACKER_CONFIG.iouThreshold) {
                const score = 1 - iou + distance * 0.01;
                if (score < bestScore) {
                    bestScore = score;
                    bestMatch = personId;
                }
            }
        }
        
        if (bestMatch !== null) {
            updatePerson(peopleTracker.get(bestMatch), detection, frameHeight);
        } else {
            // 检查是否距离太近（防止重复创建）
            let tooClose = false;
            for (const [pid, person] of peopleTracker) {
                if (computeDistance(detCenter, person.center) < TRACKER_CONFIG.maxDistance * 0.5) {
                    tooClose = true;
                    break;
                }
            }
            if (!tooClose) {
                registerPerson(detection);
            }
        }
    }
    
    // 增加未匹配人员的 disappeared
    for (const [personId, person] of peopleTracker) {
        person.disappeared++;
        
        if (person.disappeared > TRACKER_CONFIG.maxDisappeared) {
            if (person.inStore && !person.counted.exit) {
                totalExited++;
                activePeopleInStore = Math.max(0, activePeopleInStore - 1);
            }
            peopleTracker.delete(personId);
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
            video: { 
                facingMode: 'environment', 
                width: { ideal: 1280 }, 
                height: { ideal: 720 } 
            } 
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
    
    if (!cocoModel || !faceModel) {
        const loaded = await initDetectionModel();
        if (!loaded) return;
    }
    
    if (isDetecting) return;
    isDetecting = true;
    
    if (detectionCanvas) {
        detectionCanvas.width = video.videoWidth || 640;
        detectionCanvas.height = video.videoHeight || 480;
    }
    
    historyInterval = setInterval(recordCustomerFlow, 5000);
    
    requestAnimationFrame(detectFrame);
    
    showToast('🤖 AI 客流分析已开启（人脸+人体双模式）', 'success');
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
        const predictions = await detectPeople(video);
        
        matchDetectionsToTracker(predictions, frameHeight);
        
        if (detectionCtx && detectionCanvas) {
            drawDetections(detectionCtx, predictions, detectionCanvas.width, frameHeight);
        }
        
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
    
    // 区域线
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 2;
    
    const topY = height * ZONES.TOP_LINE;
    const bottomY = height * ZONES.BOTTOM_LINE;
    
    ctx.beginPath();
    ctx.moveTo(0, topY);
    ctx.lineTo(width, topY);
    ctx.stroke();
    ctx.fillStyle = '#34C759';
    ctx.font = 'bold 12px Arial';
    ctx.fillText('进入检测线', 5, topY - 5);
    
    ctx.beginPath();
    ctx.moveTo(0, bottomY);
    ctx.lineTo(width, bottomY);
    ctx.stroke();
    ctx.fillStyle = '#FF3B30';
    ctx.fillText('离开检测线', 5, bottomY - 5);
    
    ctx.setLineDash([]);
    
    // 绘制追踪人员
    for (const [personId, person] of peopleTracker) {
        const [x, y, w, h] = person.bbox;
        
        let color = '#34C759';
        if (!person.inStore) color = '#FF9500';
        if (person.counted.enter && !person.counted.exit) color = '#007AFF';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = person.type === 'face' ? 3 : 2;
        
        if (person.type === 'face') {
            // 人脸：画椭圆
            const cx = x + w / 2;
            const cy = y + h * 0.4;
            ctx.beginPath();
            ctx.ellipse(cx, cy, w / 2, h * 0.4, 0, 0, Math.PI * 2);
            ctx.stroke();
        } else {
            ctx.strokeRect(x, y, w, h);
        }
        
        // 标签
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 25, 60, 22);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 11px Arial';
        const label = person.type === 'face' ? `👤${personId}` : `🚶${personId}`;
        ctx.fillText(label, x + 3, y - 10);
    }
    
    // 统计面板
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(10, 10, 170, 85);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 13px Arial';
    ctx.fillText(`追踪: ${peopleTracker.size}人`, 18, 30);
    ctx.fillText(`在店: ${activePeopleInStore}人`, 18, 50);
    ctx.fillText(`进: ${totalEntered}  离: ${totalExited}`, 18, 70);
    ctx.font = '10px Arial';
    ctx.fillStyle = '#888';
    ctx.fillText(`检测源: 人脸+人体`, 18, 88);
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
    
    peopleTracker.clear();
    nextPersonId = 1;
}

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
    if (detectionHistory.length > 288) detectionHistory.shift();
    
    try {
        localStorage.setItem('customerFlowHistory', JSON.stringify(detectionHistory));
    } catch (e) {}
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
    } catch (e) {}
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

window.PeopleDetector = {
    init: initDetectionModel,
    start: startRealDetection,
    stop: stopDetection,
    reset: resetCustomerStats,
    export: exportCustomerFlowData,
    isRunning: () => isDetecting
};

document.addEventListener('DOMContentLoaded', restoreCustomerFlowData);
