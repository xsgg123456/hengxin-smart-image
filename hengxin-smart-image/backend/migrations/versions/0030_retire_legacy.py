"""Retire domestic image-processing modules, preserving all API and shared state."""
from alembic import op
import sqlalchemy as sa

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

# Pure JSON-compatible literals: release tooling reads this without importing app code.
RETIREMENT_CONTRACT = {
    'version': 1,
    'drop_tables': ['archive_requests', 'archive_images', 'archives', 'task_requests',
        'execution_usage', 'execution_attempts', 'execution_sessions', 'task_sources',
        'image_versions', 'result_slots', 'execution_rounds', 'task_records',
        'template_images', 'template_versions', 'templates', 'module_skill_bindings',
        'skill_versions', 'skills', 'skill_audits', 'files', 'deletion_records', 'cleanup_objects'],
    'retired_job_kinds': ['generation', 'skill_install', 'skill_check', 'skill_sync'],
    'row_filters': {
        'job_records': "kind NOT IN ('generation','skill_install','skill_check','skill_sync')",
        'job_outbox': "id IN (SELECT id FROM job_records WHERE kind NOT IN ('generation','skill_install','skill_check','skill_sync'))",
        'image_variants': "domain <> 'originals'",
        'cli_retention': "domain <> 'legacy_cli'",
    },
    'drop_columns': {},
    'json_remove': {'system_settings': {'values': ['defaultSkillIds']}},
}
SKILL_TABLES = {'skills', 'skill_versions', 'module_skill_bindings', 'skill_audits'}


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        raise RuntimeError('0030 retirement requires PostgreSQL transactional DDL')
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    retired = set(RETIREMENT_CONTRACT['drop_tables'])
    if not retired.issubset(tables):
        raise RuntimeError('Retirement schema incomplete; restore the expected 0029 baseline')
    # Freeze writers until the entire validation and DDL transaction has committed.
    quoted = ', '.join(bind.dialect.identifier_preparer.quote(t) for t in sorted(tables))
    bind.execute(sa.text('LOCK TABLE ' + quoted + ' IN ACCESS EXCLUSIVE MODE'))
    for name in sorted(tables - retired):
        for fk in inspector.get_foreign_keys(name):
            if fk['referred_table'] in retired:
                raise RuntimeError('Unknown retained foreign key references retired table: ' + name)
    for name in sorted(retired - SKILL_TABLES):
        if bind.scalar(sa.text('SELECT EXISTS (SELECT 1 FROM "' + name + '")')):
            raise RuntimeError('Retirement refused: nonempty old business table ' + name)
    old = "kind IN ('generation','skill_install','skill_check','skill_sync')"
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM job_records WHERE " + old +
            " AND status NOT IN ('succeeded','partial','failed','cancelled'))")):
        raise RuntimeError('Retirement refused: unfinished legacy job')
    # Shared tables may refer to jobs independently of the old business tables.
    for name in sorted(tables - retired - {'job_outbox'}):
        for fk in inspector.get_foreign_keys(name):
            if fk['referred_table'] != 'job_records':
                continue
            if fk['referred_columns'] != ['id'] or len(fk['constrained_columns']) != 1:
                raise RuntimeError('Unknown job reference: ' + name)
            column = bind.dialect.identifier_preparer.quote(fk['constrained_columns'][0])
            table = bind.dialect.identifier_preparer.quote(name)
            if bind.scalar(sa.text('SELECT EXISTS (SELECT 1 FROM ' + table + ' WHERE ' +
                    column + ' IN (SELECT id FROM job_records WHERE ' + old + '))')):
                raise RuntimeError('Retained row references legacy job: ' + name)
    variants = bind.execute(sa.text("SELECT outputs, lease_until, token FROM image_variants WHERE domain='originals'"))
    if any(row.outputs or row.lease_until or row.token for row in variants):
        raise RuntimeError('Retirement refused: legacy thumbnails have objects or unresolved ownership')
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM cli_retention WHERE domain='legacy_cli' AND status <> 'expired')")):
        raise RuntimeError('Retirement refused: legacy retention is unfinished')
    # API aliases must not silently lose their documented owner/retention protection.
    if bind.scalar(sa.text('SELECT EXISTS (SELECT 1 FROM skill_versions s JOIN api_image_files f '
            'ON s.bucket=f.bucket AND s.object_key=f.object_key)')):
        raise RuntimeError('Retirement refused: API object aliases legacy Skill package')
    bind.execute(sa.text('DELETE FROM job_outbox WHERE id IN (SELECT id FROM job_records WHERE ' + old + ')'))
    bind.execute(sa.text('DELETE FROM job_records WHERE ' + old))
    bind.execute(sa.text("DELETE FROM image_variants WHERE domain='originals'"))
    bind.execute(sa.text("DELETE FROM cli_retention WHERE domain='legacy_cli'"))
    bind.execute(sa.text('UPDATE system_settings SET "values" = ("values"::jsonb - :key)::json '
                        'WHERE "values"::jsonb ? :key'), {'key': 'defaultSkillIds'})
    for fk in inspector.get_foreign_keys('execution_rounds'):
        if fk['referred_table'] == 'image_versions':
            op.drop_constraint(fk['name'], 'execution_rounds', type_='foreignkey')
    for name in RETIREMENT_CONTRACT['drop_tables']:
        op.drop_table(name)


def downgrade():
    raise RuntimeError('0030 deletes retired business schema; lossless downgrade is unavailable. '
                       'Use the verified full backup and explicit recovery procedure.')
