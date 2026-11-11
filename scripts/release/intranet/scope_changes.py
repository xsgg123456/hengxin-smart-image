"""Fail-closed ownership check for independently released backend sources.

Ownership comes from both releases' reachable Python imports, never directory
names. Unknown resources and dynamic Python loaders need a joint upgrade plan.
"""
import ast
from pathlib import Path, PurePosixPath
import re

import snapshot


ENTRYPOINTS = {
    'domestic': ('app.main', 'app.modules.api_image_edits.celery_app',
                 'app.modules.api_image_edits.outbox', 'app.modules.files.variant_worker',
                 'app.worker.outbox', 'app.worker.celery_app', 'app.retention.worker'),
    'overseas': ('app.overseas.main', 'app.overseas.management.skill_publisher',
                 'app.overseas.execution.worker', 'app.overseas.execution.outbox'),
    'shared': ('app.identity.main', 'app.account_management.service',
               'app.execution.credential_broker'),
}


def backend_files(manifest):
    return {name: digest for name, digest in manifest['files'].items()
            if name.startswith('backend/')}


def sources(root, manifest):
    """Use only manifest-authenticated bytes, with complete backend provenance."""
    files = backend_files(manifest)
    provenance = manifest.get('provenance', {}).get('source_files', {})
    if files != {n: h for n, h in provenance.items() if n.startswith('backend/')}:
        raise RuntimeError('Incomplete backend source provenance; separate upgrade plan required')
    result = {}
    for name, digest in files.items():
        parts = PurePosixPath(name).parts
        if ('\\' in name or ':' in name or name.startswith('/')
                or any(p in ('', '.', '..') for p in name.split('/'))):
            raise RuntimeError('Unsafe backend source path: ' + name)
        path = Path(root)
        for part in parts:
            path = path / part
            if path.is_symlink():
                raise RuntimeError('Backend source symlink: ' + name)
        data = path.read_bytes()
        if snapshot.sha(data) != digest:
            raise RuntimeError('Backend source differs from manifest: ' + name)
        if name.endswith('.py'):
            result[name] = data
    return result


class Imports:
    def __init__(self, code):
        self.code, self.modules, self.packages = code, {}, set()
        for name in code:
            parts = name.removeprefix('backend/').removesuffix('.py').split('/')
            if parts[-1] == '__init__':
                parts.pop()
            module = '.'.join(parts)
            if module in self.modules:
                raise RuntimeError('Ambiguous Python module: ' + module)
            self.modules[module] = name
            self.packages.update('.'.join(parts[:i]) for i in range(1, len(parts)))
            if name.endswith('/__init__.py'):
                self.packages.add(module)
        self.cache = {}

    def resolve(self, module, required=False):
        if required and module not in self.modules and module not in self.packages:
            raise RuntimeError('Unresolved local import: ' + module + '; joint upgrade required')
        parts = module.split('.')
        return {self.modules[p] for i in range(1, len(parts) + 1)
                if (p := '.'.join(parts[:i])) in self.modules}

    def dependencies(self, name):
        if name in self.cache:
            return self.cache[name]
        try:
            tree = ast.parse(self.code[name], filename=name)
        except (SyntaxError, ValueError) as exc:
            raise RuntimeError('Cannot analyze backend source: ' + name) from exc
        module = name.removeprefix('backend/').removesuffix('.py').replace('/', '.')
        package = module.rsplit('.', 1)[0]
        dependencies = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = ([a.name for a in node.names] if isinstance(node, ast.Import)
                            else [node.module or ''])
                if any(m.split('.')[0] in {'importlib', 'runpy', 'builtins'} for m in imported):
                    raise RuntimeError('Dynamic Python loader in ' + name + '; joint upgrade required')
            if isinstance(node, ast.Name) and node.id in {'__import__', '__builtins__', 'exec', 'eval'}:
                raise RuntimeError('Dynamic Python execution in ' + name + '; joint upgrade required')
            if isinstance(node, ast.Attribute) and node.attr in {
                    'import_module', '__import__', 'run_module', 'run_path', 'load_module',
                    'exec_module', 'spec_from_file_location', 'spec_from_loader',
                    'autodiscover_tasks', 'import_string'}:
                raise RuntimeError('Dynamic Python loader in ' + name + '; joint upgrade required')
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.update(self.resolve(alias.name, alias.name.split('.')[0] == 'app'))
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    parts = package.split('.')
                    if node.level > len(parts):
                        raise RuntimeError('Invalid relative import in ' + name)
                    base = '.'.join(parts[:len(parts) - node.level + 1] + ([base] if base else []))
                dependencies.update(self.resolve(base, base.split('.')[0] == 'app'))
                for alias in node.names:
                    if alias.name != '*':
                        dependencies.update(self.resolve(base + '.' + alias.name))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Celery include lists and python -m subprocesses are runtime imports.
                if re.fullmatch(r'app(?:\.[A-Za-z_]\w*)+', node.value):
                    dependencies.update(self.resolve(node.value))
        self.cache[name] = dependencies
        return dependencies

    def owners(self):
        owners = {}
        for scope, entries in ENTRYPOINTS.items():
            pending, visited = set(), set()
            for module in entries:
                pending.update(self.resolve(module, required=True))
            while pending:
                name = pending.pop()
                if name in visited:
                    continue
                visited.add(name)
                owners.setdefault(name, set()).add(scope)
                pending.update(self.dependencies(name) - visited)
        return owners


def check(u, before_root, candidate_root, scope, mode):
    """Validate before any single-scope drain or mutation; return changed paths."""
    if scope not in ENTRYPOINTS or mode not in ('frontend', 'full'):
        raise RuntimeError('Invalid independent release scope or mode')
    before = snapshot.manifest(u, before_root)
    candidate = snapshot.manifest(u, candidate_root)
    # A complete Git snapshot can include an independently advanced other side.
    # Keep dependency/schema checks global; evaluate frontend backend ownership
    # below rather than requiring the entire app tree to match the selected side.
    snapshot.compatible(before, candidate, 'full')
    if before.get('runtime_inputs') != candidate.get('runtime_inputs'):
        raise RuntimeError('Codex runtime inputs changed; separate upgrade plan required')
    old_files, new_files = backend_files(before), backend_files(candidate)
    changed = sorted(n for n in old_files.keys() | new_files.keys()
                     if old_files.get(n) != new_files.get(n))
    if not changed:
        return changed
    old_owners = Imports(sources(before_root, before)).owners()
    new_owners = Imports(sources(candidate_root, candidate)).owners()
    denied, target_changes = {}, []
    for name in changed:
        owners = old_owners.get(name, set()) | new_owners.get(name, set())
        # Every extant version must have known ownership. A newly introduced
        # import cannot retrospectively establish ownership of old orphan code.
        unknown = ((name in old_files and not old_owners.get(name))
                   or (name in new_files and not new_owners.get(name)))
        if unknown:
            denied[name] = []
        elif owners == {scope}:
            target_changes.append(name)
        elif len(owners) != 1 or not owners <= {'domestic', 'overseas'}:
            denied[name] = sorted(owners)
        # Otherwise this is a proven exclusive other-business source, loaded by
        # neither the old nor new target graph. Preserve it in the complete pack.
    if denied:
        details = '; '.join(n + ' [' + (', '.join(owners) or 'unknown ownership') + ']'
                            for n, owners in denied.items())
        raise RuntimeError('Single-scope backend change refused; shared/joint upgrade plan required: ' + details)
    if mode == 'frontend' and target_changes:
        raise RuntimeError('Frontend-only release contains backend changes: ' + ', '.join(target_changes))
    return changed
