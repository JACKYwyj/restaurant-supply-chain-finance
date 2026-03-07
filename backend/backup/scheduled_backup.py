#!/usr/bin/env python3
"""
定时备份脚本
用于cron job或系统服务定时执行数据库备份
"""

import os
import sys
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backup.backup_restore import BackupService, ScheduledBackup


def main():
    parser = argparse.ArgumentParser(description='餐饮供应链金融平台 - 定时备份脚本')
    parser.add_argument('--backup-dir', type=str, default=None,
                        help='备份目录路径')
    parser.add_argument('--retention-days', type=int, default=30,
                        help='备份保留天数，默认30天')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='静默模式，只输出结果')
    
    args = parser.parse_args()
    
    if not args.quiet:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行定时备份...")
    
    result = ScheduledBackup.run_scheduled_backup(
        backup_dir=args.backup_dir,
        retention_days=args.retention_days
    )
    
    if result['success']:
        if not args.quiet:
            print(f"✓ 备份成功: {result['backup']['backup_file']}")
            print(f"  文件大小: {result['backup']['file_size']} bytes")
            if result['deleted_old_backups']:
                print(f"  已删除过期备份: {len(result['deleted_old_backups'])}个")
        return 0
    else:
        print(f"✗ 备份失败: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
