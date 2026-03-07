/**
 * 粒子效果系统 - 餐饮供应链金融赋能平台
 * 动态背景粒子 + 鼠标交互
 */

class ParticleSystem {
    constructor(container) {
        this.container = container;
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: null, y: null, radius: 150 };
        this.connectedParticles = [];
        
        this.config = {
            particleCount: 80,
            particleColor: 'rgba(255, 102, 0, 0.6)',
            particleSecondaryColor: 'rgba(26, 61, 124, 0.4)',
            lineColor: 'rgba(255, 102, 0, 0.15)',
            particleMinSize: 2,
            particleMaxSize: 5,
            particleSpeed: 0.3,
            connectionDistance: 150,
            mouseInfluence: 100
        };
        
        this.init();
    }
    
    init() {
        // 设置 canvas 样式
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        `;
        
        this.container.style.position = 'relative';
        this.container.insertBefore(this.canvas, this.container.firstChild);
        
        this.resize();
        this.createParticles();
        this.addEventListeners();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createParticles() {
        this.particles = [];
        const isBlueTheme = Math.random() > 0.5;
        
        for (let i = 0; i < this.config.particleCount; i++) {
            const size = Math.random() * (this.config.particleMaxSize - this.config.particleMinSize) + this.config.particleMinSize;
            const x = Math.random() * this.canvas.width;
            const y = Math.random() * this.canvas.height;
            const vx = (Math.random() - 0.5) * this.config.particleSpeed;
            const vy = (Math.random() - 0.5) * this.config.particleSpeed;
            
            // 随机选择颜色
            const color = Math.random() > 0.5 ? this.config.particleColor : this.config.particleSecondaryColor;
            
            this.particles.push({
                x, y, vx, vy, size, color,
                baseX: x,
                baseY: y,
                density: (Math.random() * 30) + 1
            });
        }
    }
    
    addEventListeners() {
        // 鼠标移动
        this.container.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.mouse.x = e.clientX - rect.left;
            this.mouse.y = e.clientY - rect.top;
        });
        
        // 鼠标离开
        this.container.addEventListener('mouseleave', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
        
        // 触摸支持
        this.container.addEventListener('touchmove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const touch = e.touches[0];
            this.mouse.x = touch.clientX - rect.left;
            this.mouse.y = touch.clientY - rect.top;
        });
        
        this.container.addEventListener('touchend', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
    }
    
    // 绘制单个粒子
    drawParticle(particle) {
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        this.ctx.fillStyle = particle.color;
        this.ctx.fill();
        
        // 添加发光效果
        this.ctx.shadowBlur = 10;
        this.ctx.shadowColor = particle.color;
    }
    
    // 绘制粒子之间的连线
    drawConnections() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < this.config.connectionDistance) {
                    const opacity = (1 - distance / this.config.connectionDistance) * 0.4;
                    this.ctx.beginPath();
                    this.ctx.strokeStyle = `rgba(255, 102, 0, ${opacity})`;
                    this.ctx.lineWidth = 1;
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.stroke();
                }
            }
        }
    }
    
    // 鼠标交互效果
    handleMouseInteraction(particle) {
        if (this.mouse.x === null || this.mouse.y === null) return;
        
        const dx = this.mouse.x - particle.x;
        const dy = this.mouse.y - particle.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < this.mouse.radius) {
            const forceDirectionX = dx / distance;
            const forceDirectionY = dy / distance;
            const force = (this.mouse.radius - distance) / this.mouse.radius;
            const directionX = forceDirectionX * force * particle.density;
            const directionY = forceDirectionY * force * particle.density;
            
            particle.x -= directionX * 0.5;
            particle.y -= directionY * 0.5;
        }
    }
    
    // 更新粒子位置
    updateParticles() {
        this.particles.forEach(particle => {
            // 基础移动
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            // 边界检测 - 环绕
            if (particle.x < 0) particle.x = this.canvas.width;
            if (particle.x > this.canvas.width) particle.x = 0;
            if (particle.y < 0) particle.y = this.canvas.height;
            if (particle.y > this.canvas.height) particle.y = 0;
            
            // 鼠标交互
            this.handleMouseInteraction(particle);
        });
    }
    
    // 动画循环
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制连接线
        this.drawConnections();
        
        // 更新并绘制粒子
        this.updateParticles();
        this.particles.forEach(particle => this.drawParticle(particle));
        
        requestAnimationFrame(() => this.animate());
    }
    
    // 销毁
    destroy() {
        window.removeEventListener('resize', this.resize);
        this.canvas.remove();
    }
}

// 浮动装饰元素
class FloatingElements {
    constructor(container) {
        this.container = container;
        this.elements = [];
        this.init();
    }
    
    init() {
        // 创建浮动装饰
        const decorations = [
            { emoji: '💰', size: 40 },
            { emoji: '🍜', size: 35 },
            { emoji: '🏦', size: 45 },
            { emoji: '📊', size: 38 },
            { emoji: '💳', size: 36 },
            { emoji: '🤖', size: 42 }
        ];
        
        decorations.forEach((dec, index) => {
            const el = document.createElement('div');
            el.className = 'floating-element';
            el.textContent = dec.emoji;
            el.style.cssText = `
                position: absolute;
                font-size: ${dec.size}px;
                opacity: 0.15;
                pointer-events: none;
                z-index: 0;
                animation: float${index} ${8 + Math.random() * 4}s ease-in-out infinite;
                left: ${Math.random() * 80 + 10}%;
                top: ${Math.random() * 80 + 10}%;
            `;
            
            // 添加自定义动画
            const style = document.createElement('style');
            style.textContent = `
                @keyframes float${index} {
                    0%, 100% { transform: translate(0, 0) rotate(0deg); }
                    25% { transform: translate(${Math.random() * 30 - 15}px, ${Math.random() * -30 - 10}px) rotate(${Math.random() * 20 - 10}deg); }
                    50% { transform: translate(${Math.random() * 30 - 15}px, ${Math.random() * 30 - 15}px) rotate(${Math.random() * -20 + 10}deg); }
                    75% { transform: translate(${Math.random() * -30 + 15}px, ${Math.random() * 30 - 15}px) rotate(${Math.random() * 20 - 10}deg); }
                }
            `;
            document.head.appendChild(style);
            
            this.container.appendChild(el);
            this.elements.push(el);
        });
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    const heroSection = document.querySelector('.hero-section');
    if (heroSection) {
        // 初始化粒子系统
        new ParticleSystem(heroSection);
        
        // 初始化浮动装饰
        new FloatingElements(heroSection);
    }
});
