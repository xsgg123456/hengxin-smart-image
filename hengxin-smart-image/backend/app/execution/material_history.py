"""Bounded, read-only history extraction. Never return raw logs or commands."""
import json
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .diagnostics import _safe_read
from .material_literals import image_calls

LIMIT = 64 * 1024 * 1024


def public_text(text):
    text = re.sub(r'(?i)\b(?:sk-[\w-]{12,}|Bearer\s+[\w.~-]+)', '[凭据已隐藏]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|password|secret)["\']?\s*[=:]\s*["\']?)[^\s,;"\']+', r'\1[已隐藏]', text)
    text = re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@', r'\1[凭据已隐藏]@', text)
    text = re.sub(r'(?<![\w:/])/(?!work(?:/|\b)|/)[A-Za-z_.][^\s"\'<>，。；）]*', '[内部路径已隐藏]', text)
    return re.sub(r'\b[A-Za-z]:[\\/][^\s"\'<>，。；）]*', '[内部路径已隐藏]', text)


def read(path, limit=2 * 1024 * 1024):
    return _safe_read(path, limit, allow_windows_fallback=True).decode('utf-8')


def epoch(value):
    if not value:
        return None
    date = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    return date.replace(tzinfo=timezone.utc).timestamp() if date.tzinfo is None else date.timestamp()


@lru_cache(maxsize=8)
def history(root, task_id, round_id, started, ended, cache_bucket):
    del cache_bucket
    result = {'systemPrompts': [], 'toolCalls': [], 'notices': []}
    task_root = Path(root).absolute() / task_id
    try:
        prompts = []
        for suffix in ('', '-intervention-1'):
            path = task_root / 'control' / (round_id + suffix) / 'request.txt'
            try:
                prompt = read(path)
            except FileNotFoundError:
                continue
            prompts.append(prompt)
            result['systemPrompts'].append({'label': f'系统任务提示词 {len(prompts)}', 'text': public_text(prompt)})
        if not prompts:
            result['notices'].append('本轮系统任务提示词未采集或执行材料目录未挂载。')
            return result
        directory = task_root / 'home' / '.codex' / 'sessions'
        for parent in (directory, *directory.parents):
            if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
                raise ValueError('unsafe directory')
        files = []
        total = 0
        for path in directory.rglob('*.jsonl'):
            files.append(path)
            total += path.stat().st_size
            if len(files) > 128 or total > LIMIT:
                raise ValueError('history limit')
        calls, unsupported, prompt_bytes = [], False, 0
        for path in sorted(files):
            active = False
            for line in read(path, LIMIT).splitlines():
                event = json.loads(line)
                timestamp = epoch(event.get('timestamp'))
                if timestamp is None or timestamp < started or (ended and timestamp > ended):
                    continue
                payload = event.get('payload', {})
                if event.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'user':
                    content = '\n'.join(part.get('text', '') for part in payload.get('content', []) if isinstance(part, dict))
                    active = any(prompt in content for prompt in prompts)
                if not active or event.get('type') != 'response_item' or payload.get('type') != 'function_call':
                    continue
                name, arguments = payload.get('name'), payload.get('arguments')
                if not isinstance(arguments, str):
                    continue
                if name in ('exec', 'functions.exec'):
                    parsed, invalid = image_calls(arguments)
                    unsupported |= invalid
                elif name in ('image_gen__imagegen', 'image_gen.imagegen'):
                    parsed = [json.loads(arguments)]
                else:
                    continue
                for call in parsed:
                    if not isinstance(call, dict) or not isinstance(call.get('prompt'), str):
                        unsupported = True
                        continue
                    paths = call.get('referenced_image_paths') or []
                    prompt_bytes += len(call['prompt'].encode('utf-8'))
                    if prompt_bytes > 4 * 1024 * 1024:
                        raise ValueError('prompt evidence limit')
                    calls.append((timestamp, {'prompt': public_text(call['prompt']), 'images': [p for p in paths
                        if isinstance(p, str) and p.startswith('/work/') and '..' not in p.split('/')]}))
        for _, call in sorted(calls, key=lambda item: item[0]):
            result['toolCalls'].append({'label': f'生图调用 {len(result["toolCalls"]) + 1}', **call})
        if unsupported:
            result['notices'].append('部分生图调用使用动态参数，无法安全还原完整提示词，未展示推测内容。')
        if not result['toolCalls']:
            result['notices'].append('尚无可核实的本轮生图工具提示词；可能尚未调用、会话材料缺失或记录格式不支持。')
    except PermissionError:
        result['notices'].append('历史执行材料读取权限不足，请管理员配置受控只读访问。')
    except (OSError, ValueError, TypeError, AttributeError, RecursionError):
        result['toolCalls'] = []
        result['notices'].append('历史执行材料缺失、超过读取限额或未通过完整性检查；未展示截断内容。')
    return result


def read_history(root, task_id, round_id, started, ended=None):
    return history(str(root), str(task_id), str(round_id), epoch(started), epoch(ended), int(time.time() // 15))
