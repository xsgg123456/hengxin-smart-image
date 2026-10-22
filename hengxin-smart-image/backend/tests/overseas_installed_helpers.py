import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from app.overseas.management.skill_install import bundle, install
from app.overseas.management.installed_catalog import catalog, identity, root_config


def enable_sample(factory, name='sample'):
    """Explicit prerequisite for tests exercising an already enabled installation."""
    from app.overseas.management.models import InstalledSkillAvailability
    with factory.begin() as session:
        session.add(InstalledSkillAvailability(id=name, enabled=True, version=1))


def install_sample(name='sample', content='first', files=None, display_name='示例技能'):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'source'
        installed, _ = root_config()
        release, current = catalog()
        rows = []
        for item in current:
            if item['name'] != name:
                shutil.copytree(installed / 'releases' / release / item['name'], source / item['name'])
                rows.append(dict(name=item['name'], source=item['name'], displayName=item['displayName']))
        package = source / name
        package.mkdir(parents=True)
        (package / 'SKILL.md').write_text(
            f'---\nname: {name}\ndescription: 完整示例技能\n---\n{content}', encoding='utf-8')
        for relative, data in (files or {}).items():
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        mapping = root / 'mapping.json'
        rows.append(dict(name=name, source=name, displayName=display_name))
        mapping.write_text(json.dumps(rows), encoding='utf-8')
        result = bundle(source, mapping, root / 'output')
        install(result['path'])
        return dict(id=identity(name), name=name, displayName=display_name, description='完整示例技能')
