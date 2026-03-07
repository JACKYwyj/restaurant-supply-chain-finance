"""
餐饮供应链金融平台 - 配置文件
"""

import os
from datetime import timedelta


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-2024')
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///restaurant_finance.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-2024')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    
    # 模拟支付渠道配置
    ALIPAY_MOCK_ENABLED = True
    WECHAT_PAY_MOCK_ENABLED = True
    
    # 风控配置
    RISK_THRESHOLD_HIGH = 0.8
    RISK_THRESHOLD_MEDIUM = 0.5
    RISK_THRESHOLD_LOW = 0.3
    
    # RTV模型配置
    RTV_CORRELATION_THRESHOLD = 0.6
    RTV_ANOMALY_SCORE_THRESHOLD = 0.7
    RTV_MIN_DATA_POINTS = 30
    
    # 授信配置
    CREDIT_MULTIPLIER = 3.0  # 流水倍数
    CREDIT_MAX_AMOUNT = 1000000  # 最大授信额度
    CREDIT_MIN_AMOUNT = 10000  # 最小授信额度


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    # 生产环境建议使用环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
