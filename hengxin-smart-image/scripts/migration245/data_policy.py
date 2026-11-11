"""Reviewed Skill audit projection. No business values leave the source database.
Only skill.reclaim may drop the explicitly inventoried top-level fields below.
The source guard rejects schema drift before projection; the target never projects.
"""
import re

POLICY = 'skill-reclaim-metadata-v2'
NORMAL_KEYS = set('enabled version platforms release checksum transferId deleted '
                  'cleanupComplete reclaimedBytes afterBytes libraryAfterBytes'.split())
RECLAIM_KEEP = set('release centralBytes libraryBytes libraryAfterBytes afterBytes '
                   'reclaimedBytes cleanupComplete dryRun'.split())
RECLAIM_RAW = {
    'before': set('jobs skills release centralBytes frozenInputs libraryBytes '
                  'historyContents existingHistoryContents'.split()),
    'after': set('jobs dryRun skills release targets afterBytes centralBytes frozenInputs '
                 'historyBytes libraryBytes reclaimedBytes cleanupComplete historyContents '
                 'libraryAfterBytes existingHistoryContents'.split()),
}

# Frozen from migrations overseas_0020 / overseas_0023, never future app code.
INSTALLED_SKILL_INITIAL = {
    'amazon-main-image-product-swap-1600': ['Amazon'],
    'amazon-main-image-product-swap-1250': ['Amazon'],
    'amazon-aplus-product-swap': ['Amazon'],
    'wayfair-new-product-image-set-main': ['Wayfair'],
    'wayfair-new-product-image-set-main-aplus': ['Wayfair'],
    'overseas-product-image-swap': [],
    'walmart-new-product-image-set-original': ['Walmart'],
    'walmart-new-product-image-set-revised-0927': ['Walmart'],
    'beleev-amazon-image-set': ['Amazon'],
    'beleev-amazon-aplus': ['Amazon'],
    'outonlife-amazon-image-set': ['Amazon'],
    'amazon-outonlife-new-product-aplus': ['Amazon'],
    'amazon-new-product-image-set': ['Amazon'],
    'amazon-new-product-aplus': ['Amazon'],
    'outon-brand-image-design-version-1023-night': ['Amazon'],
}
INSTALLED_SKILL_SEEDS = [dict(id=name, enabled=name in {
    'amazon-new-product-image-set', 'amazon-new-product-aplus'}, version=1, platforms=platforms)
    for name, platforms in sorted(INSTALLED_SKILL_INITIAL.items())]


def sql_keys(keys):
    # Every key comes from the reviewed constants, never from the export payload.
    return 'ARRAY[' + ','.join("'" + k + "'" for k in sorted(keys)) + ']::text[]'


def source_guard(db):
    if db != 'hengxin_overseas':
        return ''
    checks = []
    for field in ('before', 'after'):
        value = f'"{field}"::jsonb'
        allowed = (f"CASE WHEN action='skill.reclaim' THEN {sql_keys(RECLAIM_RAW[field])} "
                   f'ELSE {sql_keys(NORMAL_KEYS)} END')
        keys = f"jsonb_object_keys(CASE WHEN jsonb_typeof({value})='object' THEN {value} ELSE '{{}}'::jsonb END)"
        checks += [f"jsonb_typeof({value}) IS DISTINCT FROM 'object' OR EXISTS "
                   f'(SELECT FROM {keys} k WHERE NOT k=ANY({allowed}))']
    return ("DO $policy$ BEGIN IF EXISTS (SELECT FROM public.overseas_management_audit "
            "WHERE action LIKE 'skill.%' AND (" + ' OR '.join(checks) + ")) THEN "
            "RAISE EXCEPTION 'audit source JSON field policy mismatch'; END IF; END $policy$;\n")


def project_column(column):
    if column not in ('before', 'after'):
        return '"' + column + '"'
    return ("CASE WHEN action='skill.reclaim' THEN (SELECT COALESCE(jsonb_object_agg(key,value),"
            f"'{{}}'::jsonb) FROM jsonb_each(\"{column}\"::jsonb) WHERE key=ANY({sql_keys(RECLAIM_KEEP)})) "
            f'ELSE "{column}"::jsonb END AS "{column}"')


def report_sql(db):
    if db != 'hengxin_overseas':
        return "jsonb_build_object('reclaim_rows',0,'before','{}'::jsonb,'after','{}'::jsonb)"
    pairs = ["'reclaim_rows',(SELECT count(*) FROM public.overseas_management_audit WHERE action='skill.reclaim')"]
    for field in ('before', 'after'):
        pairs += [f"'{field}',(SELECT COALESCE(jsonb_object_agg(k,n),'{{}}'::jsonb) FROM "
                  f'(SELECT k,count(*) n FROM public.overseas_management_audit a CROSS JOIN LATERAL '
                  f'jsonb_object_keys(a."{field}"::jsonb) k WHERE action=\'skill.reclaim\' '
                  f'AND NOT k=ANY({sql_keys(RECLAIM_KEEP)}) GROUP BY k) counts)']
    return 'jsonb_build_object(' + ','.join(pairs) + ')'


def validate_report(report, rows):
    if not isinstance(report, dict) or set(report) != {'reclaim_rows', 'before', 'after'}:
        raise ValueError('audit transformation report missing')
    count = report['reclaim_rows']
    if type(count) is not int or count != sum(r['action'] == 'skill.reclaim' for r in rows):
        raise ValueError('audit transformation row count mismatch')
    for field in ('before', 'after'):
        excluded = report[field]
        if (not isinstance(excluded, dict) or set(excluded) - (RECLAIM_RAW[field] - RECLAIM_KEEP)
                or any(type(n) is not int or not 0 < n <= count for n in excluded.values())):
            raise ValueError('audit transformation excluded-field counts invalid')


def validate_row(row):
    if not isinstance(row['action'], str) or not row['action'].startswith('skill.'):
        raise ValueError('business audit rejected')
    for field in ('before', 'after'):
        value = row[field]
        keys = RECLAIM_KEEP & RECLAIM_RAW[field] if row['action'] == 'skill.reclaim' else NORMAL_KEYS
        if not isinstance(value, dict) or set(value) - keys:
            raise ValueError('audit JSON requires reviewed field policy: ' + field)
        for key, item in value.items():
            if key in ('release', 'checksum', 'transferId'):
                pattern = r'[a-f0-9]{64}' if key != 'transferId' else r'[a-f0-9-]{36}'
                valid = item is None or (isinstance(item, str) and re.fullmatch(pattern, item))
            elif key == 'platforms':
                allowed = {'Amazon', 'Wayfair', 'Mercado Libre', 'Walmart', 'The Home Depot', 'Shopee'}
                valid = isinstance(item, list) and all(isinstance(v, str) and v in allowed for v in item)
            elif key in ('enabled', 'deleted', 'cleanupComplete', 'dryRun'):
                valid = type(item) is bool
            else:
                valid = type(item) is int and item >= 0
            if not valid:
                raise ValueError('audit value requires reviewed field policy: ' + key)
