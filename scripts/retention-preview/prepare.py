"""Create an isolated frontend copy; never change production routes or policy."""
from pathlib import Path
import shutil
import json
import hashlib

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'hengxin-smart-image/frontend'
TARGET = ROOT / 'output/retention-preview-20261021'
HERE = Path(__file__).resolve().parent
TARGET.mkdir(parents=True, exist_ok=True)
for name in ('src', 'public'):
    shutil.copytree(SOURCE / name, TARGET / name, dirs_exist_ok=True)
for name in ('package.json', 'tsconfig.json', 'index.html', 'vite.config.ts'):
    shutil.copy2(SOURCE / name, TARGET / name)
config = TARGET / 'vite.config.ts'
config.write_text(config.read_text(encoding='utf-8').replace('isolatedPreview = false', 'isolatedPreview = true').replace("proxy: mode === 'demo' ? undefined : {", "proxy: ['mock', 'demo'].includes(mode) ? undefined : {"), encoding='utf-8')
route = TARGET / 'src/router/modules/index.ts'
route.write_text(route.read_text(encoding='utf-8').replace("    { path: 'users',", "    { path: 'retention', title: '自动清理', icon: 'ri:delete-bin-6-line', roles: ['super_admin', 'design_manager'] },\n    { path: 'users',"), encoding='utf-8')
for source in HERE.glob('*.vue'):
    shutil.copy2(source, TARGET / 'src/views/hengxin/admin' / source.name)
shutil.copy2(HERE / 'retention-data.ts', TARGET / 'src/views/hengxin/admin/retention-data.ts')
settings = TARGET / 'src/views/hengxin/admin/preview/SettingsPreview.vue'
settings.write_text(settings.read_text(encoding='utf-8').replace('连续闲置 7 天', '连续闲置 3 天'), encoding='utf-8')
hashes = {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (SOURCE / 'src').rglob('*') if p.is_file()}
(TARGET / 'source-hashes.json').write_text(json.dumps(hashes), encoding='utf-8')
print(TARGET)
