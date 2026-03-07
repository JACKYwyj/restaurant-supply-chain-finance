"""
餐饮供应链金融平台 - 商户API（流水数据接入）
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from models import db, Merchant, Transaction, DailyStats
from services.rtv_model import RTVModel
from services.risk_control import RiskControl
import uuid
import random

merchant_bp = Blueprint('merchant', __name__)

# 初始化服务
rtv_model = RTVModel()
risk_control = RiskControl()


@merchant_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """
    获取商户仪表板数据
    ---
    tags:
      - 商户数据
    security:
      - Bearer: []
    responses:
      200:
        description: 仪表板数据
      401:
        description: 未授权
      404:
        description: 商户不存在
    """
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    # 获取今日数据
    today = datetime.utcnow().date()
    
    # 获取最近30天的统计数据
    thirty_days_ago = today - timedelta(days=30)
    daily_stats = DailyStats.query.filter(
        DailyStats.merchant_id == merchant_id,
        DailyStats.stat_date >= thirty_days_ago
    ).order_by(DailyStats.stat_date.desc()).all()
    
    # 计算趋势数据
    recent_7_days = daily_stats[:7] if len(daily_stats) >= 7 else daily_stats
    previous_7_days = daily_stats[7:14] if len(daily_stats) >= 14 else []
    
    trend_data = {
        'customer_count_trend': 0.0,
        'transaction_amount_trend': 0.0,
    }
    
    if recent_7_days and previous_7_days:
        recent_customers = sum(s.customer_count for s in recent_7_days)
        previous_customers = sum(s.customer_count for s in previous_7_days)
        if previous_customers > 0:
            trend_data['customer_count_trend'] = round(
                (recent_customers - previous_customers) / previous_customers * 100, 2
            )
        
        recent_amount = sum(s.transaction_amount for s in recent_7_days)
        previous_amount = sum(s.transaction_amount for s in previous_7_days)
        if previous_amount > 0:
            trend_data['transaction_amount_trend'] = round(
                (recent_amount - previous_amount) / previous_amount * 100, 2
            )
    
    return jsonify({
        'merchant': merchant.to_dict(),
        'today': {
            'customer_count': merchant.customer_count_today,
            'transaction_amount': merchant.transaction_amount_today,
            'avg_transaction': round(
                merchant.transaction_amount_today / merchant.customer_count_today, 2
            ) if merchant.customer_count_today > 0 else 0
        },
        'monthly': {
            'customer_count': merchant.customer_count_month,
            'transaction_amount': merchant.transaction_amount_month,
            'avg_transaction': round(
                merchant.transaction_amount_month / merchant.customer_count_month, 2
            ) if merchant.customer_count_month > 0 else 0
        },
        'rtv': {
            'correlation': merchant.rtv_correlation,
            'anomaly_score': merchant.rtv_anomaly_score,
            'quality_score': merchant.rtv_quality_score
        },
        'risk': {
            'level': merchant.risk_level,
            'score': merchant.risk_score
        },
        'trend': trend_data,
        'daily_stats': [s.to_dict() for s in daily_stats[:30]]
    }), 200


@merchant_bp.route('/transactions', methods=['POST'])
@jwt_required()
def add_transaction():
    """接入交易流水数据"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    
    # 验证必填字段
    if not data.get('amount') or data.get('amount') <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    if not data.get('payment_channel'):
        return jsonify({'error': 'payment_channel is required'}), 400
    
    # 创建交易记录
    transaction = Transaction(
        merchant_id=merchant_id,
        transaction_id=f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}",
        amount=float(data['amount']),
        payment_channel=data.get('payment_channel', 'cash'),
        transaction_type=data.get('transaction_type', 'consumption'),
        customer_count=data.get('customer_count', 1),
        transaction_time=datetime.utcnow()
    )
    
    db.session.add(transaction)
    
    # 更新商户的当日流水
    merchant.transaction_amount_today += transaction.amount
    merchant.transaction_amount_month += transaction.amount
    merchant.last_transaction_time = datetime.utcnow()
    
    # 触发RTV模型计算
    rtv_result = rtv_model.calculate_rtvs(merchant_id)
    if rtv_result:
        merchant.rtv_correlation = rtv_result.get('correlation', 0)
        merchant.rtv_anomaly_score = rtv_result.get('anomaly_score', 0)
        merchant.rtv_quality_score = rtv_result.get('quality_score', 0)
    
    # 触发风控检查
    risk_result = risk_control.check_risk(merchant_id)
    if risk_result:
        merchant.risk_level = risk_result.get('level', 'normal')
        merchant.risk_score = risk_result.get('score', 0)
        
        # 如果检测到异常交易，标记交易
        if risk_result.get('anomaly_detected'):
            transaction.is_anomaly = True
            transaction.anomaly_reason = risk_result.get('anomaly_reason', 'Unknown anomaly')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Transaction added successfully',
        'transaction': transaction.to_dict(),
        'rtv': {
            'correlation': merchant.rtv_correlation,
            'anomaly_score': merchant.rtv_anomaly_score
        },
        'risk': {
            'level': merchant.risk_level,
            'score': merchant.risk_score
        }
    }), 201


@merchant_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """获取交易流水列表"""
    merchant_id = get_jwt_identity()
    
    # 分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 日期过滤
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Transaction.query.filter_by(merchant_id=merchant_id)
    
    if start_date:
        query = query.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Transaction.transaction_time <= datetime.fromisoformat(end_date))
    
    # 排序
    query = query.order_by(Transaction.transaction_time.desc())
    
    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'transactions': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@merchant_bp.route('/customer-count', methods=['POST'])
@jwt_required()
def update_customer_count():
    """更新客流数据"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    customer_count = data.get('customer_count')
    
    if not customer_count or customer_count < 0:
        return jsonify({'error': 'Invalid customer_count'}), 400
    
    # 更新客流
    merchant.customer_count_today = customer_count
    merchant.customer_count_month += customer_count
    
    # 触发RTV模型重新计算
    rtv_result = rtv_model.calculate_rtvs(merchant_id)
    if rtv_result:
        merchant.rtv_correlation = rtv_result.get('correlation', 0)
        merchant.rtv_anomaly_score = rtv_result.get('anomaly_score', 0)
        merchant.rtv_quality_score = rtv_result.get('quality_score', 0)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Customer count updated',
        'customer_count_today': merchant.customer_count_today,
        'customer_count_month': merchant.customer_count_month,
        'rtv_correlation': merchant.rtv_correlation
    }), 200


@merchant_bp.route('/daily-stats', methods=['GET'])
@jwt_required()
def get_daily_stats():
    """获取每日统计数据"""
    merchant_id = get_jwt_identity()
    
    # 获取日期范围
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    
    stats = DailyStats.query.filter(
        DailyStats.merchant_id == merchant_id,
        DailyStats.stat_date >= start_date
    ).order_by(DailyStats.stat_date.desc()).all()
    
    return jsonify({
        'daily_stats': [s.to_dict() for s in stats]
    }), 200


@merchant_bp.route('/sync-data', methods=['POST'])
@jwt_required()
def sync_daily_data():
    """同步每日汇总数据"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    
    today = datetime.utcnow().date()
    
    # 查找或创建今日统计
    daily_stat = DailyStats.query.filter_by(
        merchant_id=merchant_id,
        stat_date=today
    ).first()
    
    if not daily_stat:
        daily_stat = DailyStats(
            merchant_id=merchant_id,
            stat_date=today
        )
        db.session.add(daily_stat)
    
    # 更新统计数据
    daily_stat.customer_count = data.get('customer_count', merchant.customer_count_today)
    daily_stat.transaction_count = data.get('transaction_count', 0)
    daily_stat.transaction_amount = data.get('transaction_amount', merchant.transaction_amount_today)
    
    # 计算客单价
    if daily_stat.customer_count > 0:
        daily_stat.avg_transaction = round(
            daily_stat.transaction_amount / daily_stat.customer_count, 2
        )
    
    # 更新RTV数据
    if data.get('rtv_correlation') is not None:
        daily_stat.rtv_correlation = data['rtv_correlation']
    if data.get('rtv_anomaly_score') is not None:
        daily_stat.rtv_anomaly_score = data['rtv_anomaly_score']
    
    # 更新风控数据
    if data.get('risk_score') is not None:
        daily_stat.risk_score = data['risk_score']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Daily stats synced',
        'daily_stat': daily_stat.to_dict()
    }), 200


@merchant_bp.route('/reset-daily', methods=['POST'])
@jwt_required()
def reset_daily_data():
    """重置每日数据（次日调用）"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    today = datetime.utcnow().date()
    
    # 保存今日统计到DailyStats
    daily_stat = DailyStats.query.filter_by(
        merchant_id=merchant_id,
        stat_date=today
    ).first()
    
    if not daily_stat:
        daily_stat = DailyStats(
            merchant_id=merchant_id,
            stat_date=today,
            customer_count=merchant.customer_count_today,
            transaction_count=Transaction.query.filter(
                Transaction.merchant_id == merchant_id,
                db.func.date(Transaction.transaction_time) == today
            ).count(),
            transaction_amount=merchant.transaction_amount_today
        )
        
        if daily_stat.customer_count > 0:
            daily_stat.avg_transaction = round(
                daily_stat.transaction_amount / daily_stat.customer_count, 2
            )
        
        db.session.add(daily_stat)
    else:
        daily_stat.customer_count = merchant.customer_count_today
        daily_stat.transaction_count = Transaction.query.filter(
            Transaction.merchant_id == merchant_id,
            db.func.date(Transaction.transaction_time) == today
        ).count()
        daily_stat.transaction_amount = merchant.transaction_amount_today
    
    # 重置今日数据
    merchant.customer_count_today = 0
    merchant.transaction_amount_today = 0.0
    
    db.session.commit()
    
    return jsonify({
        'message': 'Daily data reset successfully',
        'saved_stats': daily_stat.to_dict()
    }), 200
