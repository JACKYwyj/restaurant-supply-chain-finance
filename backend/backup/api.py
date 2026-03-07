"""
备份和恢复API
提供数据备份、导出、导入的REST API接口
"""

from flask import Blueprint, jsonify, request, send_file, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from io import BytesIO
import base64

from backup.backup_restore import (
    BackupService, ExportService, ImportService, ScheduledBackup
)

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup', methods=['POST'])
@jwt_required()
def create_backup():
    """创建数据库备份"""
    current_user_id = get_jwt_identity()
    
    data = request.get_json() or {}
    backup_name = data.get('name')
    include_timestamp = data.get('include_timestamp', True)
    
    result = BackupService.create_backup(
        backup_name=backup_name,
        include_timestamp=include_timestamp
    )
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@backup_bp.route('/backup/list', methods=['GET'])
@jwt_required()
def list_backups():
    """列出所有备份"""
    backups = BackupService.list_backups()
    return jsonify({
        'success': True,
        'backups': backups,
        'count': len(backups)
    })


@backup_bp.route('/backup/<backup_filename>', methods=['GET'])
@jwt_required()
def get_backup_info(backup_filename):
    """获取备份文件信息"""
    from pathlib import Path
    import os
    
    from backup.backup_restore import BACKUP_DIR
    
    backup_path = BACKUP_DIR / backup_filename
    if not backup_path.exists():
        return jsonify({'success': False, 'error': 'Backup not found'}), 404
    
    stat = backup_path.stat()
    
    return jsonify({
        'success': True,
        'filename': backup_filename,
        'size': stat.st_size,
        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
    })


@backup_bp.route('/backup/<backup_filename>/download', methods=['GET'])
@jwt_required()
def download_backup(backup_filename):
    """下载备份文件"""
    from pathlib import Path
    
    from backup.backup_restore import BACKUP_DIR
    
    backup_path = BACKUP_DIR / backup_filename
    if not backup_path.exists():
        return jsonify({'success': False, 'error': 'Backup not found'}), 404
    
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=backup_filename
    )


@backup_bp.route('/backup/<backup_filename>', methods=['DELETE'])
@jwt_required()
def delete_backup(backup_filename):
    """删除备份"""
    result = BackupService.delete_backup(backup_filename)
    
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code


@backup_bp.route('/backup/<backup_filename>/restore', methods=['POST'])
@jwt_required()
def restore_backup(backup_filename):
    """恢复数据库备份"""
    # 验证请求
    data = request.get_json() or {}
    confirm = data.get('confirm', False)
    
    if not confirm:
        return jsonify({
            'success': False,
            'error': 'Please confirm restoration by setting confirm=true'
        }), 400
    
    # 执行恢复
    result = BackupService.restore_backup(backup_filename)
    
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code


# ==================== 导出API ====================

@backup_bp.route('/export/json', methods=['GET'])
@jwt_required()
def export_json():
    """导出全部数据为JSON"""
    tables = request.args.get('tables')  # 逗号分隔的表名
    
    if tables:
        tables = tables.split(',')
    
    result = ExportService.export_to_json(tables=tables)
    
    if result['success']:
        # 返回JSON文件
        json_str = json.dumps(result['data'], ensure_ascii=False, indent=2)
        buffer = BytesIO(json_str.encode('utf-8'))
        
        filename = f'export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
    
    return jsonify(result), 500


@backup_bp.route('/export/json/<table_name>', methods=['GET'])
@jwt_required()
def export_table_json(table_name):
    """导出指定表为JSON"""
    result = ExportService.export_to_json(tables=[table_name])
    
    if result['success']:
        json_str = json.dumps(result['data'], ensure_ascii=False, indent=2)
        buffer = BytesIO(json_str.encode('utf-8'))
        
        filename = f'{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
    
    return jsonify(result), 500


@backup_bp.route('/export/csv/<table_name>', methods=['GET'])
@jwt_required()
def export_csv(table_name):
    """导出指定表为CSV"""
    result = ExportService.export_to_csv(table_name)
    
    if result['success']:
        buffer = BytesIO(result['csv_data'].encode('utf-8'))
        
        filename = f'{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return send_file(
            buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    return jsonify(result), 500


@backup_bp.route('/export/csv', methods=['GET'])
@jwt_required()
def export_all_csv():
    """导出所有表为CSV（ZIP打包）"""
    result = ExportService.export_all_to_csv()
    
    if result['success']:
        zip_data = base64.b64decode(result['zip_data'])
        buffer = BytesIO(zip_data)
        
        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=result['filename']
        )
    
    return jsonify(result), 500


# ==================== 导入API ====================

@backup_bp.route('/import/json', methods=['POST'])
@jwt_required()
def import_json():
    """从JSON导入数据"""
    data = request.get_json() or {}
    json_data = data.get('data')
    
    if not json_data:
        return jsonify({
            'success': False,
            'error': 'Missing data field'
        }), 400
    
    import_mode = data.get('mode', 'merge')  # merge or replace
    
    result = ImportService.import_from_json(json_data, import_mode=import_mode)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@backup_bp.route('/import/csv/<table_name>', methods=['POST'])
@jwt_required()
def import_csv(table_name):
    """从CSV导入数据"""
    data = request.get_json() or {}
    csv_data = data.get('csv_data')
    
    if not csv_data:
        return jsonify({
            'success': False,
            'error': 'Missing csv_data field'
        }), 400
    
    import_mode = data.get('mode', 'append')  # append or replace
    
    result = ImportService.import_from_csv(csv_data, table_name, import_mode=import_mode)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


# ==================== 定时备份API ====================

@backup_bp.route('/backup/scheduled/run', methods=['POST'])
@jwt_required()
def run_scheduled_backup():
    """手动运行定时备份"""
    data = request.get_json() or {}
    
    backup_dir = data.get('backup_dir')
    retention_days = data.get('retention_days', 30)
    
    result = ScheduledBackup.run_scheduled_backup(
        backup_dir=backup_dir,
        retention_days=retention_days
    )
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@backup_bp.route('/backup/status', methods=['GET'])
@jwt_required()
def get_backup_status():
    """获取备份状态"""
    backups = BackupService.list_backups()
    
    # 计算备份统计
    total_size = sum(b['size'] for b in backups)
    oldest = backups[-1] if backups else None
    newest = backups[0] if backups else None
    
    return jsonify({
        'success': True,
        'total_backups': len(backups),
        'total_size': total_size,
        'oldest_backup': oldest,
        'newest_backup': newest,
        'backup_directory': str(BackupService._BackupService__backup_dir__())
    })
