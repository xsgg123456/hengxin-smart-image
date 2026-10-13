"""Human review gate; preserve active legacy work and all material evidence."""
from alembic import op
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer,
                        JSON, MetaData, String, Table, Text, UniqueConstraint, Uuid, inspect)

revision = 'overseas_0010'
down_revision = 'overseas_0009'
branch_labels = depends_on = None


def upgrade():
    offline = op.get_context().as_sql
    bind = op.get_bind()
    columns = set() if offline else {c['name'] for c in inspect(bind).get_columns('overseas_tasks')}
    if 'requirements_approved' not in columns:
        op.add_column('overseas_tasks', Column('requirements_approved', Boolean, nullable=False,
                                             server_default='false'))
        # Only existing submitted/in-flight tasks retain their previously authorized flow.
        op.execute("UPDATE overseas_tasks SET requirements_approved = true WHERE status NOT IN "
                   "('created', 'pending_review', 'returned')")
    if 'material_ids' not in columns:
        op.add_column('overseas_tasks', Column('material_ids', JSON, nullable=True))
    # PostgreSQL's original unnamed unique constraint has the default generated name.
    if offline:
        op.drop_constraint('overseas_materials_task_id_kind_key', 'overseas_materials', type_='unique')
    else:
        for constraint in inspect(bind).get_unique_constraints('overseas_materials'):
            if constraint['column_names'] == ['task_id', 'kind']:
                op.drop_constraint(constraint['name'], 'overseas_materials', type_='unique')
    metadata = MetaData()
    for name in ('overseas_members', 'overseas_tasks'):
        Table(name, metadata, Column('id', Uuid, primary_key=True))
    reviews = Table('overseas_requirements_reviews', metadata,
        Column('id', Uuid, primary_key=True),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('updated_at', DateTime(timezone=True), nullable=False),
        Column('task_id', ForeignKey('overseas_tasks.id'), nullable=False, index=True),
        Column('actor_id', ForeignKey('overseas_members.id'), nullable=False),
        Column('actor_name', String(200), nullable=False),
        Column('decision', String(20), nullable=False), Column('comment', Text, nullable=False),
        Column('version', Integer, nullable=False), Column('submission', JSON, nullable=False),
        UniqueConstraint('task_id', 'version'), CheckConstraint("decision IN ('approve', 'reject')"))
    reviews.create(bind, checkfirst=not offline)


def downgrade():
    # Historical evidence cannot safely be collapsed back to one material per kind.
    raise RuntimeError('Requirements history migration is forward-only')
