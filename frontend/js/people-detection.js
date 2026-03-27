/**
 * 客流分析 - TensorFlow.js 实时人体检测 + 个体追踪
 * 简化稳定版
 */

let tfReady = false;
let cocoModel = null;
let isDetecting = false;
let detectionHistory = [];

// 追踪配置
const TRACKER_CONFIG = {
    maxDisappeared: 30,
    maxDistance: 400,
    iouThreshold: 0.05,
    confidenceThreshold: 0.12
};

// 追踪器
let nextPersonId = 1;
let peopleTracker = new Map();
let activePeopleInStore = 0;
let totalEntered = 0;
let totalExited = 0;

// 画面分区（从下往上数：下方=进入区，中部=在店区，上方=离开区）
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

// 判断人的位置：上方/中部/下方
function getPosition(centerY, frameHeight) {
    const ratio = centerY / frameHeight; // 0=顶部，1=底部
    if (ratio > ZONES.ENTER_LINE) return 'bottom';  // 下方区域
    if (ratio < ZONES.EXIT_LINE) return 'top';      // 上方区域
    return 'middle';                                  // 中部区域
}

function registerPerson(detection, frameHeight) {
    const bbox = detection.bbox;
    const c = getCenter(bbox);
    const pos = getPosition(c.y, frameHeight);
    
    const person = {
        id: nextPersonId++,
        bbox: [...bbox],
        center: {...c},
        position: pos,
        disappeared: 0,
        counted: {enter: false, exit: false},
        firstSeen: Date.now()
    };
    
    peopleTracker.set(person.id, person);
    console.log('[注册] #' + person.id + ' 位置:' + pos + ' 累计追踪:' + peopleTracker.size);
    return person;
}

function updatePerson(person, detection, frameHeight) {
    const newBbox = detection.bbox;
    const newCenter = getCenter(newBbox);
    const oldPos = person.position;
    const newPos = getPosition(newCenter.y, frameHeight);
    
    person.bbox = [...newBbox];
    person.center = {...newCenter};
    person.position = newPos;
    person.disappeared = 0;
    
    // 判断进入：从下方进入中部
    if (!person.counted.enter && oldPos === 'bottom' && newPos === 'middle') {
        totalEntered++;
        activePeopleInStore++;
        person.counted.enter = true;
        console.log('[进入] #' + person.id + ' 进店! 在店:' + activePeopleInStore + ' 累计:' + totalEntered);
    }
    
    // 判断离开：从中部离开到上方
    if (!person.counted.exit && oldPos === 'middle' && newPos === 'top') {
        totalExited++;
        activePeopleInStore = Math.max(0, activePeopleInStore - 1);
        person.counted.exit = true;
        console.log('[离开] #' + person.id + ' 离店! 在店:' + activePeopleInStore + ' 累计:' + totalExited);
    }
}

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
            // 检查是否距离已有追踪者太近
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
    
    // 未匹配的追踪者增加消失计数
    for (const [pid, person] of peopleTracker) {
        if (!matchedPersons.has(pid)) {
            person.disappeared++;
            if (person.disappeared > TRACKER_CONFIG.maxDisappeared) {
                console.log('[删除] #' + pid + ' 长时间消失，移除追踪');
                peopleTracker.delete(pid);
            }
        }
    }
}

// ==================== 检测循环 ====================

let videoStream = null;
let canvas = null;
let ctx2d = null;
let histInterval = null;

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
    
    // 设置画布尺寸
    if (canvas) {
        const w = video.videoWidth || 640;
        const h = video.videoHeight || 480;
        canvas.width = w;
        canvas.height = h;
        console.log('[画布] 尺寸: ' + w + 'x' + h);
    }
    
    histInterval = setInterval(recordFlow, 5000);
    
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
        
        // 更新统计显示
        document.getElementById('enterCount').textContent = totalEntered;
        document.getElementById('shopCount').textContent = activePeopleInStore;
        document.getElementById('exitCount').textContent = totalExited;
        
    } catch (err) {
        console.error('检测循环错误:', err);
    }
    
    if (isDetecting) requestAnimationFrame(detectFrame);
}

function drawFrame(ctx, preds, fw, fh) {
    ctx.clearRect(0, 0, fw, fh);
    
    // 绘制区域分隔线
    ctx.setLineDash([8, 4]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 2;
    
    // 进入线（下方）
    const enterY = fh * ZONES.ENTER_LINE;
    ctx.beginPath();
    ctx.moveTo(0, enterY);
    ctx.lineTo(fw, enterY);
    ctx.stroke();
    ctx.fillStyle = '#34C759';
    ctx.font = 'bold 14px Arial';
    ctx.fillText('↓ 进入线', 8, enterY - 8);
    
    // 离开线（上方）
    const exitY = fh * ZONES.EXIT_LINE;
    ctx.beginPath();
    ctx.moveTo(0, exitY);
    ctx.lineTo(fw, exitY);
    ctx.stroke();
    ctx.fillStyle = '#FF3B30';
    ctx.fillText('↑ 离开线', 8, exitY - 8);
    
    ctx.setLineDash([]);
    
    // 绘制每个追踪的人
    for (const [pid, person] of peopleTracker) {
        const [x, y, w, h] = person.bbox;
        
        // 颜色：绿色=在店，蓝色=刚进，橙色=待删除，灰色=离开
        let color = '#34C759'; // 默认在店
        if (person.counted.exit) color = '#8E8E93';
        else if (person.position === 'top' && !person.counted.exit) color = '#FF9500';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
        
        // 标签背景
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 28, 70, 24);
        
        // 标签文字
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 12px Arial';
        ctx.fillText('🚶' + pid, x + 4, y - 10);
        
        // 位置指示
        ctx.fillStyle = color;
        ctx.font = '10px Arial';
        ctx.fillText(person.position === 'middle' ? '在店' : (person.position === 'bottom' ? '进入' : '离开'), x + 4, y + h + 14);
    }
    
    // 统计面板（右上角）
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(fw - 190, 10, 180, 95);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 13px Arial';
    ctx.fillText('🚶 追踪中: ' + peopleTracker.size + '人', fw - 180, 32);
    ctx.fillText('📍 当前在店: ' + activePeopleInStore + '人', fw - 180, 52);
    ctx.fillText('✅ 累计进店: ' + totalEntered, fw - 180, 72);
    ctx.fillText('❌ 累计离店: ' + totalExited, fw - 180, 92);
    
    // 检测人数
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, fw > 500 ? 50 : 10, 120, 35);
    ctx.fillStyle = '#fff';
    ctx.font = '12px Arial';
    ctx.fillText('检测: ' + preds.length + '人', 20, 73);
}

function stopDetection() {
    isDetecting = false;
    if (histInterval) { clearInterval(histInterval); histInterval = null; }
    if (ctx2d && canvas) ctx2d.clearRect(0, 0, canvas.width, canvas.height);
    peopleTracker.clear();
    nextPersonId = 1;
}

function recordFlow() {
    const now = new Date();
    detectionHistory.push({
        time: now.toISOString(),
        timeStr: now.toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'}),
        inShop: activePeopleInStore,
        enterToday: totalEntered,
        exitToday: totalExited
    });
    if (detectionHistory.length > 288) detectionHistory.shift();
    try { localStorage.setItem('cfh', JSON.stringify(detectionHistory)); } catch(e) {}
}

function restoreFlow() {
    try {
        const s = localStorage.getItem('cfh');
        if (s) {
            detectionHistory = JSON.parse(s);
            const today = new Date().toDateString();
            const todayRecs = detectionHistory.filter(r => new Date(r.time).toDateString() === today);
            if (todayRecs.length > 0) {
                const last = todayRecs[todayRecs.length-1];
                totalEntered = last.enterToday || 0;
                totalExited = last.exitToday || 0;
                activePeopleInStore = last.inShop || 0;
            }
        }
    } catch(e) {}
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
}

function exportFlow() {
    if (detectionHistory.length === 0) { showToast('warning', '数据导出', '暂无数据'); return; }
    const data = { exportTime: new Date().toISOString(), total: {enter:totalEntered, exit:totalExited, current:activePeopleInStore}, history: detectionHistory };
    const blob = new Blob([JSON.stringify(data,null,2)], {type:'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = '客流数据_' + new Date().toISOString().split('T')[0] + '.json';
    a.click();
    showToast('success', '数据导出', '已导出');
}

window.PeopleDetector = {
    init: initDetectionModel,
    start: startRealDetection,
    stop: stopDetection,
    reset: resetStats,
    export: exportFlow,
    isRunning: () => isDetecting
};

document.addEventListener('DOMContentLoaded', restoreFlow);
