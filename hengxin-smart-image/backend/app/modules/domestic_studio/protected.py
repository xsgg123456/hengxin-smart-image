"""Require production filesystem protections independently of legacy app mode."""
import os


def enabled(settings):
    value = os.environ.get('DOMESTIC_STUDIO_PROTECTED', '')
    if value not in ('', '0', '1'):
        raise ValueError('Invalid domestic Studio protection setting')
    return getattr(settings, 'app_env', None) == 'production' or value == '1'
