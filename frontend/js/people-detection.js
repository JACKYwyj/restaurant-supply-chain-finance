/**
 * 客流分析 - TensorFlow.js 实时人体检测 + 个体追踪
 * 简化版：使用 coco-ssd人体检测 + BlazeFace人脸检测
 */

let tfReady = false;
let cocoModel = null;
let blazefaceModel = null;
let isDetecting = false;
let detectionHistory = [];

// 追踪配置
const TRACKER_CONFIG = {
    maxDisappeared: 20,
    maxDistance: 300,
    iouThreshold: 0.1,
    confidenceThreshold: 0.2
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
        script.onerror = () => reject(new Error('Failed: ' + src));
        document.head.appendChild(script);
    });
}

// 初始化
async function initDetectionModel() {
    try {
        showToast('🤖 正在加载 AI 模型...', 'info');
        
        // 加载 TensorFlow.js
        if (!window.tf) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.10.0/dist/tf.min.js');
        }
        
        // 加载 BlazeFace
        if (!window.blazeface) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface@0.1.0/dist/index.js');
        }
        
        // 加载 COCO-SSD
        if (!window.cocoSsd) {
            await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.2/dist/coco-ssd.min.js');
        }
        
        await window.tf.ready();
        
        // 初始化 BlazeFace
        if (!blazefaceModel) {
            blazefaceModel = await window.blazeface.load();
            console.log('✅ BlazeFace 加载完成');
        }
        
        // 初始化 COCO-SSD
        if (!cocoModel) {
            cocoModel = await window.cocoSsd.load({
                base: 'lite_mobilenet_v2'
            });
            console.log('✅ COCO-SSD 加载完成');
        }
        
        tfReady = true;
        showToast('✅ AI 模型加载完成', 'success');
        return true;
        
    } catch (err) {
        console.error('❌ 模型加载失败:', err);
        showToast('❌ AI 模型加载失败', 'error');
        return false;
    }
}

// ==================== 检测 ====================

async function detectPeople(video) {
    const results = [];
    
    try {
        // 1. BlazeFace 人脸检测
        if (blazefaceModel) {
            const faces = await blazefaceModel.estimateFaces(video, false);
            
            for (const face of faces) {
                const tl = face.topLeft;
                const br = face.bottomRight;
                const w = br[0] - tl[0];
                const h = br[1] - tl[1];
                
                // 扩展为上半身区域
                const bbox = [
                    tl[0] - w * 0.5,      // x
                    tl[1] - h * 2.0,      // y (向上扩展)
                    w * 2.0,              // width
                    h * 4.0               // height (向下扩展到上半身)
                ];
                
                results.push({
                    class: 'face',
                    bbox: bbox,
                    confidence: 0.9,
                    type: 'face'
                });
            }
        }
        
        // 2. COCO-SSD 人体检测
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

function computeIoU(b1, b2) {
    const [x1,y1,w1,h1] = b1;
    const [x2,y2,w2,h2] = b2;
    
    const xi1 = Math.max(x1,x2), yi1 = Math.max(y1,y2);
    const xi2 = Math.min(x1+w1,x2+w2), yi2 = Math.min(y1+h1,y2+h2);
    const inter = Math.max(0,xi2-xi1) * Math.max(0,yi2-yi1);
    const union = w1*h1 + w2*h2 - inter;
    return union > 0 ? inter/union : 0;
}

function dist(c1, c2) {
    return Math.sqrt((c1.x-c2.x)**2 + (c1.y-c2.y)**2);
}

function center(b) {
    return { x: b[0]+b[2]/2, y: b[1]+b[3]/2 };
}

function zone(cy, fh) {
    const r = cy / fh;
    if (r < ZONES.TOP_LINE) return 'top';
    if (r > ZONES.BOTTOM_LINE) return 'bottom';
    return 'middle';
}

function register(det) {
    const bbox = det.bbox;
    const c = center(bbox);
    const fh = document.getElementById('cameraVideo').videoHeight || 480;
    const z = zone(c.y, fh);
    
    const p = {
        id: nextPersonId++,
        bbox: [...bbox],
        center: {...c},
        disappeared: 0,
        inStore: z !== 'top',
        counted: {enter: false, exit: false},
        zone: z,
        type: det.type
    };
    
    peopleTracker.set(p.id, p);
    console.log('[Tracker] 新增 #' + p.id + ' (' + det.type + ') 位置:' + z);
    return p;
}

function updatePerson(p, det, fh) {
    const nb = det.bbox;
    const nc = center(nb);
    const oz = p.zone;
    const nz = zone(nc.y, fh);
    
    p.bbox = [...nb];
    p.center = {...nc};
    p.zone = nz;
    p.disappeared = 0;
    p.type = det.type;
    
    if (!p.counted.enter) {
        if ((oz === 'top' && nz === 'middle') || (oz === 'top' && nz === 'bottom')) {
            totalEntered++;
            activePeopleInStore++;
            p.counted.enter = true;
            p.inStore = true;
            console.log('[Tracker] #' + p.id + ' 进店! 累计:' + totalEntered);
        }
    }
    
    if (!p.counted.exit && p.inStore) {
        if (oz !== 'bottom' && nz === 'bottom') {
            totalExited++;
            activePeopleInStore = Math.max(0, activePeopleInStore - 1);
            p.counted.exit = true;
            p.inStore = false;
            console.log('[Tracker] #' + p.id + ' 离店! 累计:' + totalExited);
        }
    }
}

function matchDetections(dets, fh) {
    const matched = new Set();
    
    for (const det of dets) {
        const dc = center(det.bbox);
        let best = null, bestScore = Infinity;
        
        for (const [pid, p] of peopleTracker) {
            const iou = computeIoU(det.bbox, p.bbox);
            const d = dist(dc, p.center);
            if (iou > TRACKER_CONFIG.iouThreshold || d < TRACKER_CONFIG.maxDistance) {
                const score = d + (1-iou)*100;
                if (score < bestScore) {
                    bestScore = score;
                    best = pid;
                }
            }
        }
        
        if (best !== null) {
            matched.add(best);
            updatePerson(peopleTracker.get(best), det, fh);
        } else {
            // 检查是否太近
            let close = false;
            for (const p of peopleTracker.values()) {
                if (dist(dc, p.center) < TRACKER_CONFIG.maxDistance * 0.3) {
                    close = true; break;
                }
            }
            if (!close) register(det);
        }
    }
    
    for (const [pid, p] of peopleTracker) {
        if (!matched.has(pid)) {
            p.disappeared++;
            if (p.disappeared > TRACKER_CONFIG.maxDisappeared) {
                if (p.inStore && !p.counted.exit) {
                    totalExited++;
                    activePeopleInStore = Math.max(0, activePeopleInStore - 1);
                }
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
        
        showToast('📷 摄像头已开启', 'success');
    } catch (err) {
        console.error('摄像头失败:', err);
        showToast('❌ 摄像头访问失败: ' + err.message, 'error');
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
    
    showToast('⏹ 摄像头已关闭', 'info');
}

async function toggleDetection() {
    if (!videoStream) {
        showToast('❌ 请先开启摄像头', 'error');
        return;
    }

    if (isDetecting) {
        stopDetection();
        showToast('🤖 AI客流分析已停止', 'info');
        return;
    }

    showToast('🤖 正在启动 AI 客流分析...', 'info');

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
    
    histInterval = setInterval(recordFlow, 5000);
    
    requestAnimationFrame(detectFrame);
    
    showToast('🤖 AI 客流分析已开启', 'success');
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
        const preds = await detectPeople(video);
        
        matchDetections(preds, fh);
        
        if (ctx2d && canvas) drawFrame(ctx2d, preds, canvas.width, fh);
        
        document.getElementById('enterCount').textContent = totalEntered;
        document.getElementById('shopCount').textContent = activePeopleInStore;
        document.getElementById('exitCount').textContent = totalExited;
        
    } catch (err) {
        console.error('检测循环错误:', err);
    }
    
    if (isDetecting) requestAnimationFrame(detectFrame);
}

function drawFrame(ctx, preds, w, h) {
    ctx.clearRect(0, 0, w, h);
    
    // 区域线
    ctx.setLineDash([5,5]);
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 2;
    
    const ty = h * ZONES.TOP_LINE;
    const by = h * ZONES.BOTTOM_LINE;
    
    ctx.beginPath(); ctx.moveTo(0,ty); ctx.lineTo(w,ty); ctx.stroke();
    ctx.fillStyle = '#34C759'; ctx.font = 'bold 12px Arial';
    ctx.fillText('进入线', 5, ty-5);
    
    ctx.beginPath(); ctx.moveTo(0,by); ctx.lineTo(w,by); ctx.stroke();
    ctx.fillStyle = '#FF3B30';
    ctx.fillText('离开线', 5, by-5);
    
    ctx.setLineDash([]);
    
    // 绘制追踪人员
    for (const [pid, p] of peopleTracker) {
        const [x,y,w2,h2] = p.bbox;
        
        let color = '#34C759';
        if (!p.inStore) color = '#FF9500';
        if (p.counted.enter && !p.counted.exit) color = '#007AFF';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = p.type === 'face' ? 3 : 2;
        
        if (p.type === 'face') {
            // 人脸椭圆
            const cx = x + w2/2, cy = y + h2*0.4;
            ctx.beginPath();
            ctx.ellipse(cx, cy, w2/2, h2*0.4, 0, 0, Math.PI*2);
            ctx.stroke();
        } else {
            ctx.strokeRect(x, y, w2, h2);
        }
        
        // 标签
        ctx.fillStyle = color;
        ctx.fillRect(x, y-22, 55, 20);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 11px Arial';
        ctx.fillText(p.type === 'face' ? '👤'+pid : '🚶'+pid, x+3, y-8);
    }
    
    // 统计面板
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    ctx.fillRect(10,10,160,80);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 13px Arial';
    ctx.fillText('追踪: ' + peopleTracker.size + '人', 18, 30);
    ctx.fillText('在店: ' + activePeopleInStore + '人', 18, 50);
    ctx.fillText('进: ' + totalEntered + ' 离: ' + totalExited, 18, 70);
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
    if (detectionHistory.length === 0) { showToast('暂无数据', 'warning'); return; }
    const data = { exportTime: new Date().toISOString(), total: {enter:totalEntered, exit:totalExited, current:activePeopleInStore}, history: detectionHistory };
    const blob = new Blob([JSON.stringify(data,null,2)], {type:'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = '客流数据_' + new Date().toISOString().split('T')[0] + '.json';
    a.click();
    showToast('📥 已导出', 'success');
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
