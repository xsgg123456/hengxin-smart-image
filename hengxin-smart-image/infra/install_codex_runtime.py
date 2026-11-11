"""Explicit additive Ubuntu runtime provisioning; no upgrade, removal or service restart."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess


def packages(path):
    values = [line.strip() for line in Path(path).read_text().splitlines()
              if line.strip() and not line.lstrip().startswith('#')]
    if not values or len(values) != len(set(values)) or any(
            re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', value) is None for value in values):
        raise ValueError('Invalid package manifest')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if socket.gethostname() != args.expected_host or os.geteuid() != 0:
        raise RuntimeError('Expected deployment host and root required')
    if 'VERSION_ID="24.04"' not in Path('/etc/os-release').read_text():
        raise RuntimeError('Only validated Ubuntu 24.04 is supported')
    names = packages(Path(__file__).with_name('codex-runtime-packages.txt'))
    env = dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive', NEEDRESTART_MODE='l')
    command = ['apt-get', '--no-install-recommends', '--no-upgrade', '--no-remove', 'install', *names]
    plan = subprocess.run([*command[:1], '-s', *command[1:]], env=env, capture_output=True,
                          text=True, check=True, timeout=90)
    # Refuse dependency upgrades too; --no-upgrade only protects explicit packages.
    if any(line.startswith('Remv ') or re.match(r'^Inst \S+ \[', line)
           for line in plan.stdout.splitlines()):
        raise RuntimeError('Plan would change an installed package; inspect separately')
    print(plan.stdout, flush=True)
    if args.apply:
        subprocess.run([*command[:1], '-y', *command[1:]], env=env, check=True, timeout=900)
        result = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Status}\t${Version}\n',
                                 *names], capture_output=True, text=True, check=True, timeout=30)
        if any('\tinstall ok installed\t' not in line for line in result.stdout.splitlines()):
            raise RuntimeError('Required packages not fully installed')
        print(json.dumps({'installed': result.stdout.splitlines()}))


if __name__ == '__main__':
    main()
