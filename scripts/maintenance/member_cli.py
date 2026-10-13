"""Explicit database selection only; errors never echo database URL/parameters."""
import argparse
import json
import os
import sys

from sqlalchemy.exc import SQLAlchemyError

from member_audit import audit
from member_catalog import engine_for
from member_codec import SafetyError, read_json, write_json
from member_reconcile import reconcile
from member_restore import restore


def main(mode):
    parser = argparse.ArgumentParser(description='成员历史核查；默认只读，必须人工审核后显式 apply')
    parser.add_argument('--business', required=True, choices=['domestic', 'overseas'])
    parser.add_argument('--database-url-env', required=True, help='显式提供 URL 的环境变量名；不读取应用配置')
    parser.add_argument('--schema')
    parser.add_argument('--output', required=True)
    if mode == 'reconcile':
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument('--approved-list')
        source.add_argument('--restore')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--recovery-dir')
    args = parser.parse_args()
    engine = None
    try:
        url = os.environ.get(args.database_url_env)
        if not url:
            raise SafetyError('explicit_database_url_required')
        # Parse approval before opening a database connection.
        payload = read_json(args.restore or args.approved_list) if mode == 'reconcile' else None
        engine = engine_for(url)
        if mode == 'audit':
            result = audit(engine, args.business, args.schema)
        elif args.restore:
            result = restore(engine, args.business, payload, schema=args.schema, apply=args.apply)
        else:
            result = reconcile(engine, args.business, payload, schema=args.schema,
                               apply=args.apply, recovery_dir=args.recovery_dir)
        write_json(args.output, result)
        print(json.dumps({'operation': result['operation'], 'business': args.business,
                          'apply': result.get('apply', False), 'reportWritten': True}))
        return 0
    except SafetyError as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2
    except (SQLAlchemyError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'error': 'operation_failed_no_sensitive_details'}), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()
