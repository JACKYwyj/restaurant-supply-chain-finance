"""
餐饮供应链金融平台 - 授信API
基于RTV评分的授信额度计算
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models import db, Merchant, CreditRecord
from services.rtv_model import RTVModel
from services.risk_control import RiskControl
import math

credit_bp = Blueprint('credit', __name__)

# 初始化服务
rtv_model = RTVModel()
risk_control = RiskControl()


# ============================================================
# RTV评分 → 评级映射
# ============================================================
RTV_RATING_CONFIG = {
    'A': {'min_score': 90, 'max_score': 100, 'flow_multiplier': 6.0, 'max_limit': 5000000},
    'B': {'min_score': 80, 'max_score': 89,  'flow_multiplier': 4.0, 'max_limit': 2000000},
    'C': {'min_score': 70, 'max_score': 79,  'flow_multiplier': 2.5, 'max_limit': 1000000},
    'D': {'min_score': 0,  'max_score': 69,  'flow_multiplier': 1.0, 'max_limit': 300000},
}


def get_rt_rating(rtv_score: float) -> str:
    """根据RTV评分获取评级"""
    if rtv_score >= 90:
        return 'A'
    elif rtv_score >= 80:
        return 'B'
    elif rtv_score >= 70:
        return 'C'
    else:
        return 'D'


def get_rating_config(rating: str) -> dict:
    """获取评级配置"""
    return RTV_RATING_CONFIG.get(rating, RTV_RATING_CONFIG['D'])


def calculate_credit_limit(merchant: Merchant) -> dict:
    """
    计算授信额度 — 基于RTV评分 + 月均流水
    
    公式：授信额度 = 月均流水 × 评级系数 × 风控系数
    
    评级标准：
    - A级 (90-100分): 月流水×6倍，上限500万
    - B级 (80-89分):  月流水×4倍，上限200万
    - C级 (70-79分):  月流水×2.5倍，上限100万
    - D级 (<70分):   月流水×1倍，上限30万
    """
    # 获取RTV评分（综合得分，0-100）
    rtv_score = merchant.rtv_quality_score or 50.0
    
    # 确定评级
    rating = get_rt_rating(rtv_score)
    rating_config = get_rating_config(rating)
    
    # 基础额度 = 月流水 × 评级系数
    monthly_flow = merchant.transaction_amount_month or 0.0
    base_limit = monthly_flow * rating_config['flow_multiplier']
    
    # 风控调整系数
    if merchant.risk_level == 'high':
        risk_multiplier = 0.3
    elif merchant.risk_level == 'medium':
        risk_multiplier = 0.6
    else:
        risk_multiplier = 1.0
    
    # 异常行为扣减
    anomaly_penalty = 0.0
    if merchant.rtv_anomaly_score and merchant.rtv_anomaly_score > 0.7:
        anomaly_penalty = 0.5  # 刷单嫌疑严重，减半
    elif merchant.rtv_anomaly_score and merchant.rtv_anomaly_score > 0.5:
        anomaly_penalty = 0.2  # 有一定异常，打八折
    
    # 计算最终额度
    final_limit = base_limit * risk_multiplier * (1.0 - anomaly_penalty)
    
    # 应用评级上限
    max_limit = rating_config['max_limit'] * risk_multiplier
    final_limit = min(final_limit, max_limit)
    
    # 应用绝对限额（最低1万，最高按评级）
    final_limit = max(10000, final_limit)
    
    return {
        'rating': rating,
        'rtv_score': round(rtv_score, 1),
        'monthly_flow': round(monthly_flow, 2),
        'flow_multiplier': rating_config['flow_multiplier'],
        'risk_multiplier': risk_multiplier,
        'anomaly_penalty': anomaly_penalty,
        'base_limit': round(base_limit, 2),
        'max_limit_by_rating': rating_config['max_limit'],
        'calculated_limit': round(final_limit, 2)
    }


def calculate_credit_score(merchant: Merchant) -> dict:
    """
    计算信用评分并返回评级
    RTV综合得分直接作为信用评分核心
    """
    # RTV综合得分（0-100）
    rtv_score = merchant.rtv_quality_score or 50.0
    
    # 基准分 = RTV得分（直接映射到300-900区间的低端）
    score = 300 + (rtv_score * 6)  # 0分→300, 100分→900
    
    # 客流-流水相关性加分（0-1 → 0-50分）
    if merchant.rtv_correlation:
        correlation_bonus = merchant.rtv_correlation * 50
        score += max(0, correlation_bonus)
    
    # 月流水规模加分
    monthly_flow = merchant.transaction_amount_month or 0
    if monthly_flow > 100000:
        score += 30
    elif monthly_flow > 50000:
        score += 15
    elif monthly_flow > 20000:
        score += 5
    
    # 风控扣分
    if merchant.risk_level == 'high':
        score -= 80
    elif merchant.risk_level == 'medium':
        score -= 30
    
    # 刷单异常扣分
    anomaly = merchant.rtv_anomaly_score or 0
    if anomaly > 0.7:
        score -= 100
    elif anomaly > 0.5:
        score -= 50
    elif anomaly > 0.3:
        score -= 20
    
    # 限制在300-900分范围内
    score = max(300, min(900, score))
    
    # 确定评级
    rating = get_rt_rating(rtv_score)
    
    return {
        'score': round(score, 1),
        'rating': rating,
        'rtv_score': round(rtv_score, 1)
    }


@credit_bp.route('/apply', methods=['POST'])
@jwt_required()
def apply_credit():
    """申请授信"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    # 检查是否有待处理的申请
    pending_application = CreditRecord.query.filter_by(
        merchant_id=merchant_id,
        status='pending'
    ).first()
    
    if pending_application:
        return jsonify({
            'error': 'You have a pending credit application',
            'application': pending_application.to_dict()
        }), 400
    
    # 计算信用评分
    credit_result = calculate_credit_score(merchant)
    credit_score = credit_result['score']
    merchant.credit_score = credit_score
    
    # 计算授信额度
    limit_calculation = calculate_credit_limit(merchant)
    calculated_limit = limit_calculation['calculated_limit']
    
    # 用户申请的额度（可选）
    data = request.get_json()
    requested_amount = data.get('amount') if data else None
    
    if requested_amount:
        # 不能超过计算额度
        approved_amount = min(requested_amount, calculated_limit)
    else:
        approved_amount = calculated_limit
    
    # 创建授信记录
    credit_record = CreditRecord(
        merchant_id=merchant_id,
        credit_type='initial',
        amount=approved_amount,
        before_limit=merchant.credit_limit,
        after_limit=approved_amount,
        status='approved',
        reason='Auto approved based on RTV and risk assessment',
        approved_at=datetime.utcnow()
    )
    
    db.session.add(credit_record)
    
    # 更新商户授信额度
    merchant.credit_limit = approved_amount
    merchant.credit_status = 'approved'
    
    db.session.commit()
    
    return jsonify({
        'message': 'Credit application approved',
        'credit_record': credit_record.to_dict(),
        'credit_score': credit_result['score'],
        'credit_rating': credit_result['rating'],
        'rtv_score': credit_result['rtv_score'],
        'limit_calculation': limit_calculation
    }), 201


@credit_bp.route('/status', methods=['GET'])
@jwt_required()
def get_credit_status():
    """获取授信状态"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    # 计算当前可用的授信额度
    available_credit = merchant.credit_limit - merchant.credit_used
    utilization_rate = (merchant.credit_used / merchant.credit_limit * 100) if merchant.credit_limit > 0 else 0
    
    # 实时计算信用评分
    credit_result = calculate_credit_score(merchant)
    
    # 实时计算建议额度
    limit_calculation = calculate_credit_limit(merchant)
    
    return jsonify({
        'credit_status': merchant.credit_status,
        'credit_score': credit_result['score'],
        'credit_rating': credit_result['rating'],
        'rtv_score': credit_result['rtv_score'],
        'credit_limit': merchant.credit_limit,
        'credit_used': merchant.credit_used,
        'credit_available': available_credit,
        'utilization_rate': round(utilization_rate, 2),
        'limit_calculation': limit_calculation
    }), 200


@credit_bp.route('/increase', methods=['POST'])
@jwt_required()
def increase_credit():
    """申请提额"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    if merchant.credit_status != 'approved':
        return jsonify({'error': 'No active credit line'}), 400
    
    data = request.get_json()
    requested_amount = data.get('amount')
    
    if not requested_amount or requested_amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    # 重新计算信用评分和额度
    credit_result = calculate_credit_score(merchant)
    credit_score = credit_result['score']
    merchant.credit_score = credit_score
    
    limit_calculation = calculate_credit_limit(merchant)
    max_limit = limit_calculation['calculated_limit']
    
    # 检查是否超过最大额度
    if merchant.credit_limit + requested_amount > max_limit:
        return jsonify({
            'error': 'Requested amount exceeds maximum allowed limit',
            'current_limit': merchant.credit_limit,
            'max_limit': max_limit,
            'max_increase': max_limit - merchant.credit_limit
        }), 400
    
    # 检查风控状态
    if merchant.risk_level == 'high':
        return jsonify({
            'error': 'Cannot increase credit due to high risk level',
            'risk_level': merchant.risk_level,
            'risk_score': merchant.risk_score
        }), 400
    
    # 创建提额记录
    old_limit = merchant.credit_limit
    new_limit = old_limit + requested_amount
    
    credit_record = CreditRecord(
        merchant_id=merchant_id,
        credit_type='increase',
        amount=requested_amount,
        before_limit=old_limit,
        after_limit=new_limit,
        status='approved',
        reason='Approved based on improved RTV score and risk assessment',
        approved_at=datetime.utcnow()
    )
    
    db.session.add(credit_record)
    merchant.credit_limit = new_limit
    
    db.session.commit()
    
    return jsonify({
        'message': 'Credit increase approved',
        'credit_record': credit_record.to_dict(),
        'new_limit': new_limit,
        'credit_score': credit_score
    }), 201


@credit_bp.route('/decrease', methods=['POST'])
@jwt_required()
def decrease_credit():
    """申请降额"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    if merchant.credit_status != 'approved':
        return jsonify({'error': 'No active credit line'}), 400
    
    data = request.get_json()
    decrease_amount = data.get('amount')
    
    if not decrease_amount or decrease_amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    if decrease_amount >= merchant.credit_limit:
        return jsonify({'error': 'Cannot decrease below current used amount'}), 400
    
    # 创建降额记录
    old_limit = merchant.credit_limit
    new_limit = old_limit - decrease_amount
    
    credit_record = CreditRecord(
        merchant_id=merchant_id,
        credit_type='decrease',
        amount=-decrease_amount,
        before_limit=old_limit,
        after_limit=new_limit,
        status='approved',
        reason='User requested decrease',
        approved_at=datetime.utcnow()
    )
    
    db.session.add(credit_record)
    merchant.credit_limit = new_limit
    
    db.session.commit()
    
    return jsonify({
        'message': 'Credit decreased successfully',
        'credit_record': credit_record.to_dict(),
        'new_limit': new_limit
    }), 200


@credit_bp.route('/records', methods=['GET'])
@jwt_required()
def get_credit_records():
    """获取授信记录"""
    merchant_id = get_jwt_identity()
    
    # 获取所有授信记录
    records = CreditRecord.query.filter_by(
        merchant_id=merchant_id
    ).order_by(CreditRecord.created_at.desc()).all()
    
    return jsonify({
        'records': [r.to_dict() for r in records]
    }), 200


@credit_bp.route('/use', methods=['POST'])
@jwt_required()
def use_credit():
    """使用授信额度（模拟提款）"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    if merchant.credit_status != 'approved':
        return jsonify({'error': 'No active credit line'}), 400
    
    data = request.get_json()
    amount = data.get('amount')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    # 检查可用额度
    available = merchant.credit_limit - merchant.credit_used
    if amount > available:
        return jsonify({
            'error': 'Insufficient credit',
            'requested': amount,
            'available': available
        }), 400
    
    # 更新已用额度
    merchant.credit_used += amount
    
    db.session.commit()
    
    return jsonify({
        'message': 'Credit used successfully',
        'amount_used': amount,
        'credit_used': merchant.credit_used,
        'credit_available': merchant.credit_limit - merchant.credit_used
    }), 200


@credit_bp.route('/repay', methods=['POST'])
@jwt_required()
def repay_credit():
    """偿还授信（模拟还款）"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    amount = data.get('amount')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    if amount > merchant.credit_used:
        amount = merchant.credit_used
    
    # 更新已用额度
    merchant.credit_used -= amount
    
    db.session.commit()
    
    return jsonify({
        'message': 'Repayment successful',
        'amount_repaid': amount,
        'credit_used': merchant.credit_used,
        'credit_available': merchant.credit_limit - merchant.credit_used
    }), 200


@credit_bp.route('/evaluate', methods=['POST'])
@jwt_required()
def evaluate_credit():
    """评估授信（不申请，仅预览）"""
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    # 计算信用评分
    credit_result = calculate_credit_score(merchant)
    
    # 计算授信额度
    limit_calculation = calculate_credit_limit(merchant)
    
    # 用户申请的额度（可选）
    data = request.get_json()
    requested_amount = data.get('amount') if data else None
    
    if requested_amount:
        approved_amount = min(requested_amount, limit_calculation['calculated_limit'])
    else:
        approved_amount = limit_calculation['calculated_limit']
    
    return jsonify({
        'credit_score': credit_result['score'],
        'credit_rating': credit_result['rating'],
        'rtv_score': credit_result['rtv_score'],
        'requested_amount': requested_amount,
        'approved_amount': approved_amount,
        'limit_calculation': limit_calculation,
        'current_limit': merchant.credit_limit,
        'potential_increase': approved_amount - merchant.credit_limit if merchant.credit_limit > 0 else approved_amount
    }), 200
