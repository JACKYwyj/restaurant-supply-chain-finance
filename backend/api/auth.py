"""
餐饮供应链金融平台 - 认证API
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from models import db, Merchant

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    商户注册
    ---
    tags:
      - 认证
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
            - email
            - business_name
          properties:
            username:
              type: string
              description: 用户名
            password:
              type: string
              description: 密码
            email:
              type: string
              format: email
              description: 邮箱
            business_name:
              type: string
              description: 商户名称
            business_license:
              type: string
              description: 营业执照号
            contact_person:
              type: string
              description: 联系人
            contact_phone:
              type: string
              description: 联系电话
            address:
              type: string
              description: 地址
            business_type:
              type: string
              default: restaurant
              description: 业务类型
    responses:
      201:
        description: 注册成功
        schema:
          type: object
          properties:
            message:
              type: string
            merchant:
              type: object
            access_token:
              type: string
      400:
        description: 参数错误或用户名/邮箱已存在
    """
    data = request.get_json()
    
    # 验证必填字段
    required_fields = ['username', 'password', 'email', 'business_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # 检查用户名是否已存在
    if Merchant.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    # 检查邮箱是否已存在
    if Merchant.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # 创建新商户
    merchant = Merchant(
        username=data['username'],
        email=data['email'],
        business_name=data['business_name'],
        business_license=data.get('business_license'),
        contact_person=data.get('contact_person'),
        contact_phone=data.get('contact_phone'),
        address=data.get('address'),
        business_type=data.get('business_type', 'restaurant')
    )
    merchant.set_password(data['password'])
    
    db.session.add(merchant)
    db.session.commit()
    
    # 生成token
    access_token = create_access_token(identity=merchant.id)
    
    return jsonify({
        'message': 'Registration successful',
        'merchant': merchant.to_dict(),
        'access_token': access_token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    商户登录
    ---
    tags:
      - 认证
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              description: 用户名
            password:
              type: string
              description: 密码
    responses:
      200:
        description: 登录成功
        schema:
          type: object
          properties:
            message:
              type: string
            merchant:
              type: object
            access_token:
              type: string
      400:
        description: 用户名或密码不能为空
      401:
        description: 用户名或密码错误
    """
    data = request.get_json()
    
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400
    
    merchant = Merchant.query.filter_by(username=data['username']).first()
    
    if not merchant or not merchant.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # 生成token
    access_token = create_access_token(identity=merchant.id)
    
    return jsonify({
        'message': 'Login successful',
        'merchant': merchant.to_dict(),
        'access_token': access_token
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    获取当前用户信息
    ---
    tags:
      - 认证
    security:
      - Bearer: []
    responses:
      200:
        description: 用户信息
      401:
        description: 未授权
      404:
        description: 商户不存在
    """
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    return jsonify(merchant.to_dict()), 200


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_current_user():
    """
    更新当前用户信息
    ---
    tags:
      - 认证
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            business_name:
              type: string
              description: 商户名称
            business_license:
              type: string
              description: 营业执照号
            contact_person:
              type: string
              description: 联系人
            contact_phone:
              type: string
              description: 联系电话
            address:
              type: string
              description: 地址
            business_type:
              type: string
              description: 业务类型
    responses:
      200:
        description: 更新成功
      401:
        description: 未授权
      404:
        description: 商户不存在
    """
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    
    # 允许更新的字段
    updatable_fields = [
        'business_name', 'business_license', 'contact_person',
        'contact_phone', 'address', 'business_type'
    ]
    
    for field in updatable_fields:
        if field in data:
            setattr(merchant, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Update successful',
        'merchant': merchant.to_dict()
    }), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    修改密码
    ---
    tags:
      - 认证
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - old_password
            - new_password
          properties:
            old_password:
              type: string
              description: 原密码
            new_password:
              type: string
              description: 新密码
    responses:
      200:
        description: 密码修改成功
      400:
        description: 原密码和新密码不能为空
      401:
        description: 原密码错误或未授权
      404:
        description: 商户不存在
    """
    merchant_id = get_jwt_identity()
    merchant = Merchant.query.get(merchant_id)
    
    if not merchant:
        return jsonify({'error': 'Merchant not found'}), 404
    
    data = request.get_json()
    
    if not data.get('old_password') or not data.get('new_password'):
        return jsonify({'error': 'Old password and new password are required'}), 400
    
    if not merchant.check_password(data['old_password']):
        return jsonify({'error': 'Old password is incorrect'}), 401
    
    merchant.set_password(data['new_password'])
    db.session.commit()
    
    return jsonify({'message': 'Password changed successfully'}), 200
