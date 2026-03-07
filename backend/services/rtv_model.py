"""
餐饮供应链金融平台 - RTV实时验证模型服务
RTV (Real-Time Verification) 模型用于计算客流-流水相关性
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models import db, Merchant, Transaction, DailyStats
from config import Config


class RTVModel:
    """RTV实时验证模型"""
    
    def __init__(self):
        self.correlation_threshold = Config.RTV_CORRELATION_THRESHOLD
        self.anomaly_threshold = Config.RTV_ANOMALY_SCORE_THRESHOLD
        self.min_data_points = Config.RTV_MIN_DATA_POINTS
    
    def calculate_rtvs(self, merchant_id: int) -> Optional[Dict]:
        """
        计算商户的RTV指标
        
        Returns:
            dict: 包含correlation, anomaly_score, quality_score
        """
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return None
        
        # 获取最近30天的每日统计数据
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        daily_stats = DailyStats.query.filter(
            DailyStats.merchant_id == merchant_id,
            DailyStats.stat_date >= thirty_days_ago
        ).order_by(DailyStats.stat_date).all()
        
        if len(daily_stats) < 7:
            # 数据不足，返回默认值
            return {
                'correlation': 0.0,
                'anomaly_score': 0.0,
                'quality_score': 0.0,
                'data_points': len(daily_stats),
                'warning': 'Insufficient data points'
            }
        
        # 提取客流和流水数据
        customer_counts = [s.customer_count for s in daily_stats]
        transaction_amounts = [s.transaction_amount for s in daily_stats]
        
        # 计算皮尔逊相关系数
        correlation = self._calculate_correlation(customer_counts, transaction_amounts)
        
        # 计算异常得分
        anomaly_score = self._calculate_anomaly_score(
            customer_counts, transaction_amounts, correlation
        )
        
        # 计算RTV质量得分
        quality_score = self._calculate_quality_score(
            correlation, anomaly_score, len(daily_stats)
        )
        
        return {
            'correlation': round(correlation, 3),
            'anomaly_score': round(anomaly_score, 3),
            'quality_score': round(quality_score, 1),
            'data_points': len(daily_stats)
        }
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """计算皮尔逊相关系数"""
        if len(x) < 2:
            return 0.0
        
        x = np.array(x)
        y = np.array(y)
        
        # 检查标准差是否为0
        if np.std(x) == 0 or np.std(y) == 0:
            return 0.0
        
        correlation = np.corrcoef(x, y)[0, 1]
        
        # 处理NaN
        if np.isnan(correlation):
            return 0.0
        
        return float(correlation)
    
    def _calculate_anomaly_score(
        self,
        customer_counts: List[float],
        transaction_amounts: List[float],
        correlation: float
    ) -> float:
        """
        计算异常得分
        
        异常检测维度：
        1. 客流-流水相关性异常（刷单特征）
        2. 客单价异常（过高或过低）
        3. 交易时间分布异常
        """
        if len(customer_counts) < 3:
            return 0.0
        
        customer_counts = np.array(customer_counts)
        transaction_amounts = np.array(transaction_amounts)
        
        # 计算客单价
        with np.errstate(divide='ignore', invalid='ignore'):
            unit_prices = transaction_amounts / np.maximum(customer_counts, 1)
        
        # 异常1: 相关系数过低（可能刷单）
        correlation_anomaly = 0.0
        if correlation < 0.3:
            correlation_anomaly = 1.0 - correlation
        elif correlation < 0.5:
            correlation_anomaly = 0.5
        
        # 异常2: 客单价过高（异常大额交易）
        unit_price_anomaly = 0.0
        valid_prices = unit_prices[~np.isnan(unit_prices)]
        if len(valid_prices) > 0:
            mean_price = np.mean(valid_prices)
            std_price = np.std(valid_prices)
            if std_price > 0:
                # 检查是否有异常高的客单价
                high_price_ratio = np.sum(valid_prices > mean_price + 3 * std_price) / len(valid_prices)
                unit_price_anomaly = min(high_price_ratio * 2, 1.0)
        
        # 异常3: 交易金额波动异常
        transaction_anomaly = 0.0
        if np.mean(transaction_amounts) > 0:
            cv = np.std(transaction_amounts) / np.mean(transaction_amounts)
            # 波动系数过高或过低都可能是异常
            if cv > 2.0:
                transaction_anomaly = 0.8
            elif cv < 0.1:
                transaction_anomaly = 0.5
        
        # 综合异常得分
        anomaly_score = (
            correlation_anomaly * 0.5 +
            unit_price_anomaly * 0.3 +
            transaction_anomaly * 0.2
        )
        
        return min(anomaly_score, 1.0)
    
    def _calculate_quality_score(
        self,
        correlation: float,
        anomaly_score: float,
        data_points: int
    ) -> float:
        """
        计算RTV质量得分 (0-100)
        
        评分维度：
        1. 相关性得分 (0-40分)
        2. 稳定性得分 (0-30分)
        3. 数据量得分 (0-30分)
        """
        # 相关性得分
        if correlation >= 0.8:
            correlation_score = 40
        elif correlation >= 0.6:
            correlation_score = 30 + (correlation - 0.6) / 0.2 * 10
        elif correlation >= 0.4:
            correlation_score = 20 + (correlation - 0.4) / 0.2 * 10
        elif correlation >= 0.2:
            correlation_score = 10 + (correlation - 0.2) / 0.2 * 10
        else:
            correlation_score = max(0, correlation / 0.2 * 10)
        
        # 稳定性得分（基于异常得分）
        anomaly_score = max(0, 1 - anomaly_score)
        stability_score = anomaly_score * 30
        
        # 数据量得分
        if data_points >= 30:
            data_score = 30
        elif data_points >= 20:
            data_score = 20 + (data_points - 20) / 10 * 10
        elif data_points >= 10:
            data_score = 10 + (data_points - 10) / 10 * 10
        else:
            data_score = data_points / 10 * 10
        
        return correlation_score + stability_score + data_score
    
    def analyze_transaction_patterns(self, merchant_id: int) -> Dict:
        """分析交易模式"""
        # 获取最近30天的交易数据
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        transactions = Transaction.query.filter(
            Transaction.merchant_id == merchant_id,
            Transaction.transaction_time >= thirty_days_ago,
            Transaction.status == 'completed'
        ).order_by(Transaction.transaction_time).all()
        
        if len(transactions) < 10:
            return {
                'error': 'Insufficient transaction data',
                'transaction_count': len(transactions)
            }
        
        # 分析交易金额分布
        amounts = [t.amount for t in transactions]
        
        # 分析支付渠道分布
        channel_distribution = {}
        for t in transactions:
            channel = t.payment_channel
            channel_distribution[channel] = channel_distribution.get(channel, 0) + 1
        
        # 转换为百分比
        total = len(transactions)
        channel_distribution = {
            k: round(v / total * 100, 2)
            for k, v in channel_distribution.items()
        }
        
        # 检测可疑模式
        suspicious_patterns = []
        
        # 模式1: 单笔金额过大
        avg_amount = np.mean(amounts)
        if max(amounts) > avg_amount * 10:
            suspicious_patterns.append({
                'type': 'large_single_transaction',
                'severity': 'high',
                'description': f'Found transaction {max(amounts):.2f} which is {max(amounts)/avg_amount:.1f}x average'
            })
        
        # 模式2: 短时间内多笔交易
        for i in range(len(transactions) - 1):
            time_diff = (transactions[i+1].transaction_time - transactions[i].transaction_time).total_seconds()
            if time_diff < 60 and abs(amounts[i+1] - amounts[i]) < 1:
                suspicious_patterns.append({
                    'type': 'rapid_successive_transactions',
                    'severity': 'medium',
                    'description': 'Multiple transactions within 60 seconds with similar amounts'
                })
                break
        
        # 模式3: 夜间交易过多 (22:00-06:00)
        night_transactions = [t for t in transactions if t.transaction_time.hour >= 22 or t.transaction_time.hour < 6]
        if len(night_transactions) / total > 0.3:
            suspicious_patterns.append({
                'type': 'excessive_night_transactions',
                'severity': 'medium',
                'description': f'{len(night_transactions)/total*100:.1f}% of transactions occur at night'
            })
        
        return {
            'transaction_count': len(transactions),
            'avg_amount': round(avg_amount, 2),
            'median_amount': round(np.median(amounts), 2),
            'max_amount': round(max(amounts), 2),
            'min_amount': round(min(amounts), 2),
            'std_amount': round(np.std(amounts), 2),
            'channel_distribution': channel_distribution,
            'suspicious_patterns': suspicious_patterns,
            'suspicious_count': len(suspicious_patterns)
        }
    
    def get_realtime_verification(self, merchant_id: int) -> Dict:
        """获取实时验证状态"""
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return {'error': 'Merchant not found'}
        
        # 计算RTV指标
        rtv_result = self.calculate_rtvs(merchant_id) or {}
        
        # 判断验证状态
        if rtv_result.get('quality_score', 0) >= 80:
            status = 'verified'
            status_text = 'RTV验证通过，数据质量优秀'
        elif rtv_result.get('quality_score', 0) >= 60:
            status = 'acceptable'
            status_text = 'RTV验证可接受，数据质量一般'
        elif rtv_result.get('quality_score', 0) >= 40:
            status = 'warning'
            status_text = 'RTV验证警告，数据质量较差'
        else:
            status = 'failed'
            status_text = 'RTV验证失败，数据不足或异常'
        
        # 检查异常
        if rtv_result.get('anomaly_score', 0) > 0.7:
            anomaly_status = 'critical'
            anomaly_text = '检测到严重刷单异常'
        elif rtv_result.get('anomaly_score', 0) > 0.5:
            anomaly_status = 'warning'
            anomaly_text = '检测到轻度刷单风险'
        else:
            anomaly_status = 'normal'
            anomaly_text = '未检测到明显刷单异常'
        
        return {
            'merchant_id': merchant_id,
            'status': status,
            'status_text': status_text,
            'anomaly_status': anomaly_status,
            'anomaly_text': anomaly_text,
            'rtv': rtv_result,
            'recommendations': self._get_recommendations(rtv_result)
        }
    
    def _get_recommendations(self, rtv_result: Dict) -> List[str]:
        """根据RTV结果给出建议"""
        recommendations = []
        
        correlation = rtv_result.get('correlation', 0)
        anomaly_score = rtv_result.get('anomaly_score', 0)
        quality_score = rtv_result.get('quality_score', 0)
        
        if correlation < 0.5:
            recommendations.append('建议加强客流数据采集，提高客流-流水相关性')
        
        if anomaly_score > 0.5:
            recommendations.append('检测到交易异常，建议核查刷单行为')
        
        if quality_score < 60:
            recommendations.append('建议积累更多交易数据以提高RTV验证质量')
        
        if quality_score >= 80:
            recommendations.append('数据质量优秀，可申请提高授信额度')
        
        if not recommendations:
            recommendations.append('继续维护良好的经营数据，保持稳定的客流-流水关系')
        
        return recommendations
