"""
餐饮供应链金融平台 - 风控服务
用于识别刷单异常和风险评估
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models import db, Merchant, Transaction, DailyStats, RiskAlert
from config import Config


class RiskControl:
    """风控服务"""
    
    def __init__(self):
        self.high_threshold = Config.RISK_THRESHOLD_HIGH
        self.medium_threshold = Config.RISK_THRESHOLD_MEDIUM
        self.low_threshold = Config.RISK_THRESHOLD_LOW
    
    def check_risk(self, merchant_id: int) -> Dict:
        """
        执行风控检查
        
        Returns:
            dict: 包含level, score, anomaly_detected, anomaly_reason
        """
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return {'error': 'Merchant not found'}
        
        # 综合评分
        risk_factors = []
        
        # 1. RTV异常得分
        if merchant.rtv_anomaly_score > 0.7:
            risk_factors.append({
                'factor': 'rtv_anomaly',
                'score': 40,
                'description': 'RTV异常得分过高，可能存在刷单'
            })
        elif merchant.rtv_anomaly_score > 0.5:
            risk_factors.append({
                'factor': 'rtv_anomaly',
                'score': 25,
                'description': 'RTV存在轻度异常'
            })
        
        # 2. 客流-流水相关性
        if merchant.rtv_correlation < 0.2:
            risk_factors.append({
                'factor': 'low_correlation',
                'score': 30,
                'description': '客流与流水相关性过低'
            })
        elif merchant.rtv_correlation < 0.4:
            risk_factors.append({
                'factor': 'low_correlation',
                'score': 15,
                'description': '客流与流水相关性偏低'
            })
        
        # 3. 检查最近交易异常
        anomaly_check = self._check_recent_transactions(merchant_id)
        if anomaly_check['has_anomaly']:
            risk_factors.append({
                'factor': 'transaction_anomaly',
                'score': anomaly_check['score'],
                'description': anomaly_check['description']
            })
        
        # 4. 检查交易模式
        pattern_check = self._check_transaction_patterns(merchant_id)
        if pattern_check['has_risk']:
            risk_factors.append({
                'factor': 'pattern_risk',
                'score': pattern_check['score'],
                'description': pattern_check['description']
            })
        
        # 5. 检查历史风控预警
        recent_alerts = RiskAlert.query.filter(
            RiskAlert.merchant_id == merchant_id,
            RiskAlert.status == 'active',
            RiskAlert.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        if recent_alerts >= 3:
            risk_factors.append({
                'factor': 'frequent_alerts',
                'score': 20,
                'description': f'7天内有{recent_alerts}条风控预警'
            })
        
        # 计算综合风险得分
        total_score = sum(f['score'] for f in risk_factors)
        risk_score = min(total_score / 100, 1.0)
        
        # 确定风险等级
        if risk_score >= self.high_threshold:
            risk_level = 'high'
        elif risk_score >= self.medium_threshold:
            risk_level = 'medium'
        elif risk_score >= self.low_threshold:
            risk_level = 'low'
        else:
            risk_level = 'normal'
        
        # 判断是否检测到刷单异常
        anomaly_detected = risk_score >= self.medium_threshold
        anomaly_reason = None
        if anomaly_detected and risk_factors:
            anomaly_reason = '; '.join([f['description'] for f in risk_factors])
        
        # 更新商户风控状态
        merchant.risk_level = risk_level
        merchant.risk_score = risk_score
        merchant.last_risk_alert = datetime.utcnow()
        
        # 创建风控预警记录
        if anomaly_detected:
            alert = RiskAlert(
                merchant_id=merchant_id,
                alert_type='anomaly' if merchant.rtv_anomaly_score > 0.5 else 'risk',
                alert_level=risk_level,
                risk_score=risk_score,
                description=anomaly_reason,
                details='{}'
            )
            db.session.add(alert)
        
        return {
            'level': risk_level,
            'score': round(risk_score, 3),
            'anomaly_detected': anomaly_detected,
            'anomaly_reason': anomaly_reason,
            'risk_factors': risk_factors
        }
    
    def _check_recent_transactions(self, merchant_id: int) -> Dict:
        """检查最近交易是否存在异常"""
        # 获取最近100笔交易
        recent_transactions = Transaction.query.filter(
            Transaction.merchant_id == merchant_id,
            Transaction.status == 'completed'
        ).order_by(Transaction.transaction_time.desc()).limit(100).all()
        
        if len(recent_transactions) < 10:
            return {'has_anomaly': False, 'score': 0, 'description': ''}
        
        # 分析金额分布
        amounts = [t.amount for t in recent_transactions]
        avg_amount = np.mean(amounts)
        
        # 检测1: 异常大额交易
        large_transactions = [a for a in amounts if a > avg_amount * 5]
        if len(large_transactions) / len(amounts) > 0.1:
            return {
                'has_anomaly': True,
                'score': 25,
                'description': f'发现{len(large_transactions)}笔异常大额交易'
            }
        
        # 检测2: 相同金额频繁出现
        from collections import Counter
        amount_counts = Counter(round(a, 2) for a in amounts)
        max_repeat = max(amount_counts.values())
        if max_repeat > len(amounts) * 0.2 and max_repeat >= 5:
            repeated_amount = max(amount_counts, key=amount_counts.get)
            return {
                'has_anomaly': True,
                'score': 30,
                'description': f'金额{round(repeated_amount, 2)}重复出现{max_repeat}次'
            }
        
        # 检测3: 短时间内多笔交易
        for i in range(len(recent_transactions) - 1):
            time_diff = (recent_transactions[i].transaction_time - 
                       recent_transactions[i+1].transaction_time).total_seconds()
            if time_diff < 30:
                return {
                    'has_anomaly': True,
                    'score': 20,
                    'description': '检测到短时间内多笔交易'
                }
        
        return {'has_anomaly': False, 'score': 0, 'description': ''}
    
    def _check_transaction_patterns(self, merchant_id: int) -> Dict:
        """检查交易模式风险"""
        # 获取最近30天数据
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        transactions = Transaction.query.filter(
            Transaction.merchant_id == merchant_id,
            Transaction.transaction_time >= thirty_days_ago,
            Transaction.status == 'completed'
        ).all()
        
        if len(transactions) < 20:
            return {'has_risk': False, 'score': 0, 'description': ''}
        
        # 分析1: 夜间交易比例
        night_transactions = [t for t in transactions 
                            if t.transaction_time.hour >= 22 or t.transaction_time.hour < 6]
        night_ratio = len(night_transactions) / len(transactions)
        
        if night_ratio > 0.5:
            return {
                'has_risk': True,
                'score': 20,
                'description': f'夜间交易占比{night_ratio*100:.1f}%，异常偏高'
            }
        
        # 分析2: 支付渠道单一
        channels = set(t.payment_channel for t in transactions)
        if len(channels) == 1:
            return {
                'has_risk': True,
                'score': 10,
                'description': '仅使用单一支付渠道'
            }
        
        # 分析3: 交易时间过于规律
        hours = [t.transaction_time.hour for t in transactions]
        hour_variance = np.std(hours)
        if hour_variance < 2:
            return {
                'has_risk': True,
                'score': 15,
                'description': '交易时间过于规律，可能存在异常'
            }
        
        return {'has_risk': False, 'score': 0, 'description': ''}
    
    def get_risk_report(self, merchant_id: int) -> Dict:
        """获取详细风控报告"""
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return {'error': 'Merchant not found'}
        
        # 获取最近30天的风控预警
        alerts = RiskAlert.query.filter(
            RiskAlert.merchant_id == merchant_id
        ).order_by(RiskAlert.created_at.desc()).limit(30).all()
        
        # 获取每日统计数据用于趋势分析
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        daily_stats = DailyStats.query.filter(
            DailyStats.merchant_id == merchant_id,
            DailyStats.stat_date >= thirty_days_ago
        ).order_by(DailyStats.stat_date).all()
        
        # 分析风险趋势
        risk_trend = 'stable'
        if len(daily_stats) >= 7:
            recent_avg = np.mean([s.risk_score for s in daily_stats[:7]])
            previous_avg = np.mean([s.risk_score for s in daily_stats[7:14]]) if len(daily_stats) >= 14 else recent_avg
            
            if recent_avg > previous_avg + 0.2:
                risk_trend = 'increasing'
            elif recent_avg < previous_avg - 0.2:
                risk_trend = 'decreasing'
        
        # 风险维度评分
        dimensions = {
            'data_quality': self._score_data_quality(merchant),
            'transaction_pattern': self._score_transaction_pattern(merchant_id),
            'historical_alerts': self._score_historical_alerts(merchant_id),
            'correlation': self._score_correlation(merchant)
        }
        
        # 总体评分
        overall_score = np.mean(list(dimensions.values()))
        
        return {
            'merchant_id': merchant_id,
            'overall_risk_score': round(overall_score, 2),
            'risk_level': merchant.risk_level,
            'risk_trend': risk_trend,
            'dimensions': dimensions,
            'recent_alerts': [a.to_dict() for a in alerts[:10]],
            'alert_count_30d': len([a for a in alerts if a.created_at >= datetime.utcnow() - timedelta(days=30)]),
            'recommendations': self._generate_risk_recommendations(dimensions, merchant)
        }
    
    def _score_data_quality(self, merchant: Merchant) -> float:
        """评估数据质量"""
        score = 100
        
        if merchant.rtv_quality_score < 40:
            score -= 40
        elif merchant.rtv_quality_score < 60:
            score -= 20
        
        if merchant.rtv_anomaly_score > 0.7:
            score -= 30
        elif merchant.rtv_anomaly_score > 0.5:
            score -= 15
        
        return max(0, score)
    
    def _score_transaction_pattern(self, merchant_id: int) -> float:
        """评估交易模式"""
        score = 100
        
        pattern_check = self._check_transaction_patterns(merchant_id)
        if pattern_check['has_risk']:
            score -= pattern_check['score']
        
        anomaly_check = self._check_recent_transactions(merchant_id)
        if anomaly_check['has_anomaly']:
            score -= anomaly_check['score']
        
        return max(0, score)
    
    def _score_historical_alerts(self, merchant_id: int) -> float:
        """评估历史预警"""
        score = 100
        
        # 最近30天预警数
        alerts_30d = RiskAlert.query.filter(
            RiskAlert.merchant_id == merchant_id,
            RiskAlert.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        score -= min(alerts_30d * 10, 50)
        
        # 最近7天预警数
        alerts_7d = RiskAlert.query.filter(
            RiskAlert.merchant_id == merchant_id,
            RiskAlert.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        score -= min(alerts_7d * 15, 30)
        
        return max(0, score)
    
    def _score_correlation(self, merchant: Merchant) -> float:
        """评估相关性"""
        score = 100
        
        if merchant.rtv_correlation < 0.2:
            score -= 50
        elif merchant.rtv_correlation < 0.4:
            score -= 30
        elif merchant.rtv_correlation < 0.6:
            score -= 15
        
        return max(0, score)
    
    def _generate_risk_recommendations(self, dimensions: Dict, merchant: Merchant) -> List[str]:
        """生成风控建议"""
        recommendations = []
        
        if dimensions['data_quality'] < 60:
            recommendations.append('建议改善数据质量，增加有效交易数据')
        
        if dimensions['transaction_pattern'] < 70:
            recommendations.append('检测到异常交易模式，请核查交易真实性')
        
        if dimensions['historical_alerts'] < 70:
            recommendations.append('历史预警较多，建议加强风控管理')
        
        if dimensions['correlation'] < 60:
            recommendations.append('客流与流水相关性较低，建议排查刷单风险')
        
        if merchant.risk_level == 'high':
            recommendations.append('风险等级较高，暂不建议申请提高授信额度')
        
        if not recommendations:
            recommendations.append('风控状态良好，继续保持')
        
        return recommendations
    
    def resolve_alert(self, alert_id: int, merchant_id: int) -> Dict:
        """处理预警"""
        alert = RiskAlert.query.filter_by(
            id=alert_id,
            merchant_id=merchant_id
        ).first()
        
        if not alert:
            return {'error': 'Alert not found'}
        
        alert.status = 'resolved'
        alert.resolved_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'message': 'Alert resolved',
            'alert': alert.to_dict()
        }
    
    def get_alerts(self, merchant_id: int, status: str = None) -> List[Dict]:
        """获取风控预警列表"""
        query = RiskAlert.query.filter_by(merchant_id=merchant_id)
        
        if status:
            query = query.filter_by(status=status)
        
        alerts = query.order_by(RiskAlert.created_at.desc()).all()
        
        return [a.to_dict() for a in alerts]
