"""
餐饮供应链金融平台 - 数据模型
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Merchant(db.Model):
    """商户模型"""
    __tablename__ = 'merchants'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # 商户基本信息
    business_name = db.Column(db.String(200), nullable=False)  # 店名
    business_license = db.Column(db.String(50))  # 营业执照号
    contact_person = db.Column(db.String(50))  # 联系人
    contact_phone = db.Column(db.String(20))  # 联系电话
    address = db.Column(db.String(500))  # 地址
    business_type = db.Column(db.String(50))  # 业态类型
    
    # 经营数据
    customer_count_today = db.Column(db.Integer, default=0)  # 今日客流
    customer_count_month = db.Column(db.Integer, default=0)  # 本月累计客流
    transaction_amount_today = db.Column(db.Float, default=0.0)  # 今日流水
    transaction_amount_month = db.Column(db.Float, default=0.0)  # 本月累计流水
    
    # 授信相关
    credit_score = db.Column(db.Float, default=500.0)  # 信用评分 (300-900)
    credit_limit = db.Column(db.Float, default=0.0)  # 授信额度
    credit_used = db.Column(db.Float, default=0.0)  # 已用额度
    credit_status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    
    # 风控状态
    risk_level = db.Column(db.String(20), default='normal')  # normal/medium/high
    risk_score = db.Column(db.Float, default=0.0)  # 风控评分
    last_risk_alert = db.Column(db.DateTime)  # 最近风控预警时间
    
    # RTV模型数据
    rtv_correlation = db.Column(db.Float, default=0.0)  # 客流-流水相关系数
    rtv_anomaly_score = db.Column(db.Float, default=0.0)  # 异常得分
    rtv_quality_score = db.Column(db.Float, default=0.0)  # RTV质量得分
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_transaction_time = db.Column(db.DateTime)  # 最近交易时间
    
    # 关联
    transactions = db.relationship('Transaction', backref='merchant', lazy='dynamic')
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'business_name': self.business_name,
            'business_license': self.business_license,
            'contact_person': self.contact_person,
            'contact_phone': self.contact_phone,
            'address': self.address,
            'business_type': self.business_type,
            'customer_count_today': self.customer_count_today,
            'customer_count_month': self.customer_count_month,
            'transaction_amount_today': self.transaction_amount_today,
            'transaction_amount_month': self.transaction_amount_month,
            'credit_score': self.credit_score,
            'credit_limit': self.credit_limit,
            'credit_used': self.credit_used,
            'credit_status': self.credit_status,
            'risk_level': self.risk_level,
            'risk_score': self.risk_score,
            'rtv_correlation': self.rtv_correlation,
            'rtv_anomaly_score': self.rtv_anomaly_score,
            'rtv_quality_score': self.rtv_quality_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_transaction_time': self.last_transaction_time.isoformat() if self.last_transaction_time else None
        }


class Transaction(db.Model):
    """交易流水模型"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False, index=True)
    
    # 交易信息
    transaction_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    payment_channel = db.Column(db.String(20), nullable=False)  # alipay/wechat/cash
    transaction_type = db.Column(db.String(20), default='consumption')  # consumption/refund
    
    # 客流相关
    customer_count = db.Column(db.Integer, default=1)  # 关联客流
    
    # 状态
    status = db.Column(db.String(20), default='completed')  # pending/completed/failed
    
    # 时间
    transaction_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 异常标记
    is_anomaly = db.Column(db.Boolean, default=False)
    anomaly_reason = db.Column(db.String(200))
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'transaction_id': self.transaction_id,
            'amount': self.amount,
            'payment_channel': self.payment_channel,
            'transaction_type': self.transaction_type,
            'customer_count': self.customer_count,
            'status': self.status,
            'transaction_time': self.transaction_time.isoformat() if self.transaction_time else None,
            'is_anomaly': self.is_anomaly,
            'anomaly_reason': self.anomaly_reason
        }


class DailyStats(db.Model):
    """每日统计模型"""
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False, index=True)
    
    # 日期
    stat_date = db.Column(db.Date, nullable=False, index=True)
    
    # 经营数据
    customer_count = db.Column(db.Integer, default=0)  # 日客流
    transaction_count = db.Column(db.Integer, default=0)  # 日交易笔数
    transaction_amount = db.Column(db.Float, default=0.0)  # 日交易金额
    avg_transaction = db.Column(db.Float, default=0.0)  # 客单价
    
    # RTV指标
    rtv_correlation = db.Column(db.Float, default=0.0)  # 客流-流水相关系数
    rtv_anomaly_score = db.Column(db.Float, default=0.0)  # 异常得分
    
    # 风控
    risk_score = db.Column(db.Float, default=0.0)  # 日风控评分
    
    # 时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'stat_date': self.stat_date.isoformat() if self.stat_date else None,
            'customer_count': self.customer_count,
            'transaction_count': self.transaction_count,
            'transaction_amount': self.transaction_amount,
            'avg_transaction': self.avg_transaction,
            'rtv_correlation': self.rtv_correlation,
            'rtv_anomaly_score': self.rtv_anomaly_score,
            'risk_score': self.risk_score
        }


class CreditRecord(db.Model):
    """授信记录模型"""
    __tablename__ = 'credit_records'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False, index=True)
    
    # 授信信息
    credit_type = db.Column(db.String(20), nullable=False)  # initial/increase/decrease
    amount = db.Column(db.Float, nullable=False)
    before_limit = db.Column(db.Float, nullable=False)
    after_limit = db.Column(db.Float, nullable=False)
    
    # 状态
    status = db.Column(db.String(20), default='approved')  # pending/approved/rejected
    
    # 原因
    reason = db.Column(db.String(500))
    
    # 时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'credit_type': self.credit_type,
            'amount': self.amount,
            'before_limit': self.before_limit,
            'after_limit': self.after_limit,
            'status': self.status,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None
        }


class RiskAlert(db.Model):
    """风控预警模型"""
    __tablename__ = 'risk_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False, index=True)
    
    # 预警信息
    alert_type = db.Column(db.String(50), nullable=False)  # anomaly/high_risk/low_correlation
    alert_level = db.Column(db.String(20), nullable=False)  # low/medium/high/critical
    risk_score = db.Column(db.Float, nullable=False)
    
    # 详情
    description = db.Column(db.String(500))
    details = db.Column(db.Text)  # JSON格式的详细信息
    
    # 状态
    status = db.Column(db.String(20), default='active')  # active/resolved/ignored
    
    # 时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'alert_type': self.alert_type,
            'alert_level': self.alert_level,
            'risk_score': self.risk_score,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
