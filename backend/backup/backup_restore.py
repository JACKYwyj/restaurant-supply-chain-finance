"""
数据备份和恢复服务
提供数据库备份、数据导出导入功能
"""

import os
import json
import csv
import shutil
import sqlite3
from datetime import datetime, timedelta
from io import StringIO, BytesIO
from pathlib import Path

# 备份目录
BACKUP_DIR = Path(__file__).parent / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)


class BackupService:
    """备份服务"""
    
    @staticmethod
    def get_db_path():
        """获取数据库文件路径"""
        from config import config
        db_uri = config['development'].SQLALCHEMY_DATABASE_URI
        # sqlite:///restaurant_finance.db -> restaurant_finance.db
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                # 相对路径，基于backend目录
                base_dir = Path(__file__).parent
                db_path = base_dir / db_path
            return str(db_path)
        return None
    
    @staticmethod
    def create_backup(backup_name=None, include_timestamp=True):
        """
        创建数据库备份
        
        Args:
            backup_name: 备份名称，默认使用数据库名
            include_timestamp: 是否包含时间戳
        
        Returns:
            dict: 备份信息
        """
        db_path = BackupService.get_db_path()
        if not db_path or not os.path.exists(db_path):
            return {'success': False, 'error': 'Database file not found'}
        
        # 生成备份文件名
        if backup_name is None:
            backup_name = 'restaurant_finance'
        
        if include_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'{backup_name}_{timestamp}.db'
        else:
            backup_filename = f'{backup_name}.db'
        
        backup_path = BACKUP_DIR / backup_filename
        
        try:
            # 复制数据库文件
            shutil.copy2(db_path, backup_path)
            
            # 同时备份 WAL 和 SHM 文件（如果存在）
            wal_path = db_path + '-wal'
            shm_path = db_path + '-shm'
            
            if os.path.exists(wal_path):
                shutil.copy2(wal_path, str(backup_path) + '-wal')
            if os.path.exists(shm_path):
                shutil.copy2(shm_path, str(backup_path) + '-shm')
            
            file_size = os.path.getsize(backup_path)
            
            return {
                'success': True,
                'backup_file': str(backup_path),
                'file_size': file_size,
                'created_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_backups():
        """列出所有备份文件"""
        backups = []
        if not BACKUP_DIR.exists():
            return backups
        
        for f in BACKUP_DIR.glob('*.db'):
            stat = f.stat()
            backups.append({
                'filename': f.name,
                'path': str(f),
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        # 按修改时间排序，最新的在前
        backups.sort(key=lambda x: x['modified_at'], reverse=True)
        return backups
    
    @staticmethod
    def restore_backup(backup_filename):
        """
        恢复数据库备份
        
        Args:
            backup_filename: 备份文件名
        
        Returns:
            dict: 恢复结果
        """
        db_path = BackupService.get_db_path()
        if not db_path:
            return {'success': False, 'error': 'Cannot determine database path'}
        
        backup_path = BACKUP_DIR / backup_filename
        if not backup_path.exists():
            return {'success': False, 'error': 'Backup file not found'}
        
        try:
            # 先关闭所有连接（实际使用时应确保没有活跃连接）
            # 复制备份文件到数据库路径
            shutil.copy2(backup_path, db_path)
            
            # 恢复 WAL 和 SHM 文件
            wal_backup = str(backup_path) + '-wal'
            shm_backup = str(backup_path) + '-shm'
            
            if os.path.exists(wal_backup):
                shutil.copy2(wal_backup, db_path + '-wal')
            if os.path.exists(shm_backup):
                shutil.copy2(shm_backup, db_path + '-shm')
            
            return {
                'success': True,
                'restored_from': str(backup_path),
                'restored_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_backup(backup_filename):
        """删除备份文件"""
        backup_path = BACKUP_DIR / backup_filename
        if not backup_path.exists():
            return {'success': False, 'error': 'Backup file not found'}
        
        try:
            os.remove(backup_path)
            # 同时删除 WAL 和 SHM 文件
            wal_path = str(backup_path) + '-wal'
            shm_path = str(backup_path) + '-shm'
            if os.path.exists(wal_path):
                os.remove(wal_path)
            if os.path.exists(shm_path):
                os.remove(shm_path)
            
            return {'success': True, 'deleted': backup_filename}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class ExportService:
    """数据导出服务"""
    
    @staticmethod
    def export_to_json(tables=None, include_relationships=True):
        """
        导出数据为JSON格式
        
        Args:
            tables: 要导出的表名列表，None表示所有表
            include_relationships: 是否包含关联数据
        
        Returns:
            dict: 导出结果
        """
        from models import db, Merchant, Transaction, DailyStats, CreditRecord, RiskAlert
        
        table_models = {
            'merchants': Merchant,
            'transactions': Transaction,
            'daily_stats': DailyStats,
            'credit_records': CreditRecord,
            'risk_alerts': RiskAlert
        }
        
        if tables is None:
            tables = list(table_models.keys())
        
        export_data = {}
        
        try:
            for table_name in tables:
                if table_name not in table_models:
                    continue
                
                model = table_models[table_name]
                records = db.session.query(model).all()
                export_data[table_name] = [record.to_dict() for record in records]
            
            return {
                'success': True,
                'data': export_data,
                'exported_at': datetime.now().isoformat(),
                'tables': list(export_data.keys()),
                'record_counts': {k: len(v) for k, v in export_data.items()}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def export_to_csv(table_name):
        """
        导出指定表为CSV格式
        
        Args:
            table_name: 表名
        
        Returns:
            dict: 导出结果，包含csv_data字段
        """
        from models import db, Merchant, Transaction, DailyStats, CreditRecord, RiskAlert
        
        table_models = {
            'merchants': Merchant,
            'transactions': Transaction,
            'daily_stats': DailyStats,
            'credit_records': CreditRecord,
            'risk_alerts': RiskAlert
        }
        
        if table_name not in table_models:
            return {'success': False, 'error': f'Unknown table: {table_name}'}
        
        model = table_models[table_name]
        
        try:
            records = db.session.query(model).all()
            if not records:
                return {'success': True, 'csv_data': '', 'count': 0}
            
            # 获取字段名
            first_record = records[0]
            data_dict = first_record.to_dict()
            fieldnames = list(data_dict.keys())
            
            # 生成CSV
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in records:
                writer.writerow(record.to_dict())
            
            csv_data = output.getvalue()
            
            return {
                'success': True,
                'csv_data': csv_data,
                'count': len(records),
                'table': table_name,
                'fields': fieldnames
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def export_all_to_csv():
        """导出所有表为CSV（打包成ZIP）"""
        from models import db, Merchant, Transaction, DailyStats, CreditRecord, RiskAlert
        
        table_models = {
            'merchants': Merchant,
            'transactions': Transaction,
            'daily_stats': DailyStats,
            'credit_records': CreditRecord,
            'risk_alerts': RiskAlert
        }
        
        import zipfile
        
        try:
            # 创建内存中的ZIP文件
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for table_name, model in table_models.items():
                    records = db.session.query(model).all()
                    
                    if not records:
                        continue
                    
                    # 获取字段名
                    first_record = records[0]
                    data_dict = first_record.to_dict()
                    fieldnames = list(data_dict.keys())
                    
                    # 生成CSV
                    output = StringIO()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for record in records:
                        writer.writerow(record.to_dict())
                    
                    # 添加到ZIP
                    zf.writestr(f'{table_name}.csv', output.getvalue())
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            
            return {
                'success': True,
                'zip_data': zip_data.encode('base64'),  # Base64编码
                'filename': f'all_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class ImportService:
    """数据导入服务"""
    
    @staticmethod
    def import_from_json(json_data, import_mode='merge'):
        """
        从JSON导入数据
        
        Args:
            json_data: JSON数据（dict或str）
            import_mode: 导入模式 - 'merge'（合并）或 'replace'（替换）
        
        Returns:
            dict: 导入结果
        """
        from models import db, Merchant, Transaction, DailyStats, CreditRecord, RiskAlert
        
        if isinstance(json_data, str):
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError as e:
                return {'success': False, 'error': f'Invalid JSON: {e}'}
        else:
            data = json_data
        
        table_models = {
            'merchants': Merchant,
            'transactions': Transaction,
            'daily_stats': DailyStats,
            'credit_records': CreditRecord,
            'risk_alerts': RiskAlert
        }
        
        try:
            imported_counts = {}
            
            # 如果是replace模式，先清空表
            if import_mode == 'replace':
                for model in table_models.values():
                    db.session.query(model).delete()
                db.session.commit()
            
            # 导入数据
            for table_name, records in data.items():
                if table_name not in table_models:
                    continue
                
                model = table_models[table_name]
                count = 0
                
                for record_data in records:
                    # 移除id字段，让数据库自动生成
                    record_data = dict(record_data)
                    record_data.pop('id', None)
                    
                    # 转换日期时间字符串
                    from datetime import datetime
                    for field in ['created_at', 'updated_at', 'transaction_time', 
                                  'stat_date', 'last_transaction_time', 'approved_at',
                                  'resolved_at', 'last_risk_alert']:
                        if field in record_data and record_data[field]:
                            try:
                                record_data[field] = datetime.fromisoformat(record_data[field])
                            except:
                                pass
                    
                    # 处理日期字段（date类型）
                    if 'stat_date' in record_data and record_data['stat_date']:
                        try:
                            record_data['stat_date'] = datetime.strptime(
                                record_data['stat_date'], '%Y-%m-%d'
                            ).date()
                        except:
                            pass
                    
                    # 创建记录
                    try:
                        new_record = model(**record_data)
                        db.session.add(new_record)
                        count += 1
                    except Exception as e:
                        # 跳过有问题的记录
                        pass
                
                db.session.commit()
                imported_counts[table_name] = count
            
            return {
                'success': True,
                'imported': imported_counts,
                'imported_at': datetime.now().isoformat(),
                'mode': import_mode
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def import_from_csv(csv_data, table_name, import_mode='append'):
        """
        从CSV导入数据
        
        Args:
            csv_data: CSV数据字符串
            table_name: 目标表名
            import_mode: 导入模式 - 'append'（追加）或 'replace'（替换）
        
        Returns:
            dict: 导入结果
        """
        from models import db, Merchant, Transaction, DailyStats, CreditRecord, RiskAlert
        
        table_models = {
            'merchants': Merchant,
            'transactions': Transaction,
            'daily_stats': DailyStats,
            'credit_records': CreditRecord,
            'risk_alerts': RiskAlert
        }
        
        if table_name not in table_models:
            return {'success': False, 'error': f'Unknown table: {table_name}'}
        
        model = table_models[table_name]
        
        try:
            # 解析CSV
            reader = csv.DictReader(StringIO(csv_data))
            records = list(reader)
            
            if import_mode == 'replace':
                db.session.query(model).delete()
                db.session.commit()
            
            count = 0
            for record_data in records:
                # 转换数值类型
                for field, value in record_data.items():
                    if value == '' or value is None:
                        record_data[field] = None
                    elif field in ['id', 'merchant_id', 'customer_count', 'transaction_count']:
                        try:
                            record_data[field] = int(value)
                        except:
                            pass
                    elif field in ['amount', 'transaction_amount', 'avg_transaction', 
                                   'credit_score', 'credit_limit', 'credit_used',
                                   'risk_score', 'rtv_correlation', 'rtv_anomaly_score',
                                   'transaction_amount_today', 'transaction_amount_month']:
                        try:
                            record_data[field] = float(value)
                        except:
                            pass
                
                # 移除id字段
                record_data.pop('id', None)
                
                try:
                    new_record = model(**record_data)
                    db.session.add(new_record)
                    count += 1
                except Exception as e:
                    pass
            
            db.session.commit()
            
            return {
                'success': True,
                'imported': count,
                'table': table_name,
                'mode': import_mode,
                'imported_at': datetime.now().isoformat()
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}


class ScheduledBackup:
    """定时备份调度器"""
    
    @staticmethod
    def run_scheduled_backup(backup_dir=None, retention_days=30):
        """
        运行定时备份
        
        Args:
            backup_dir: 自定义备份目录
            retention_days: 保留天数
        
        Returns:
            dict: 备份结果
        """
        global BACKUP_DIR
        
        # 临时修改备份目录
        if backup_dir:
            original_backup_dir = BACKUP_DIR
            BACKUP_DIR = Path(backup_dir)
            BACKUP_DIR.mkdir(exist_ok=True)
        
        try:
            # 创建备份
            result = BackupService.create_backup()
            
            if not result['success']:
                return result
            
            # 清理过期备份
            backup_service = BackupService()
            backups = BackupService.list_backups()
            
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted = []
            
            for backup in backups:
                backup_time = datetime.fromisoformat(backup['modified_at'])
                if backup_time < cutoff_date:
                    BackupService.delete_backup(backup['filename'])
                    deleted.append(backup['filename'])
            
            return {
                'success': True,
                'backup': result,
                'deleted_old_backups': deleted,
                'retention_days': retention_days
            }
        finally:
            # 恢复原始备份目录
            if backup_dir:
                BACKUP_DIR = original_backup_dir
