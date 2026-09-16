"""WSL keeper identity and ownership-scoped lifecycle for the local controller."""
import ctypes
import json
import os
from pathlib import Path
import subprocess

KEEPER_FILE = Path(__file__).resolve().parents[2] / 'output/playwright/local-codex/wsl-keeper.json'


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def keeper_identity(pid, run):
    require(type(pid) is int and pid > 0, 'Invalid keeper PID')
    # Only an integer enters this fixed PowerShell query; no paths or shell text are interpolated.
    raw = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
               f'Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" | '
               'Select-Object ProcessId,ExecutablePath,CommandLine,CreationDate | ConvertTo-Json -Compress'])
    if not raw:
        return None
    value = json.loads(raw)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW(value['CommandLine'], ctypes.byref(count))
    require(bool(argv), 'Cannot inspect keeper command')
    try:
        value['argv'] = [argv[i] for i in range(count.value)]
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(argv, ctypes.c_void_p))
    return value


def valid_keeper(value):
    if not value or not value.get('ExecutablePath'):
        return False
    expected = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/wsl.exe'
    args = value.get('argv', [])[1:]
    args = [{'--distribution': '-d', '--user': '-u', '--exec': '--'}.get(a, a) for a in args]
    return (Path(value['ExecutablePath']) == expected and args ==
            ['-d', 'Ubuntu-24.04', '-u', 'hengxin', '--', 'sleep', 'infinity'])


def manage_keeper(project, infra, run, stop=False):
    owner = {'project': project, 'infra': str(infra)}
    record = json.loads(KEEPER_FILE.read_text()) if KEEPER_FILE.exists() else None
    if record:
        current = keeper_identity(record['identity']['ProcessId'], run)
        if valid_keeper(current) and current == record['identity']:
            if stop and record.get('owner') == owner:
                # Hold a process handle before the second identity check: PID reuse cannot
                # redirect TerminateProcess to a different process after this check.
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = kernel.OpenProcess(0x1001, False, current['ProcessId'])
                require(bool(handle), 'Cannot open owned keeper')
                try:
                    require(keeper_identity(current['ProcessId'], run) == current, 'Keeper identity changed')
                    require(kernel.TerminateProcess(handle, 0), 'Cannot stop owned keeper')
                finally:
                    kernel.CloseHandle(handle)
                KEEPER_FILE.unlink()
            return
    if stop:
        return  # Missing/reused PID: never kill or delete another process's record.
    legacy_pid = KEEPER_FILE.with_suffix('.pid')
    value = keeper_identity(int(legacy_pid.read_text().strip()), run) if legacy_pid.exists() else None
    owned = None
    if not valid_keeper(value):
        process = subprocess.Popen([str(Path(os.environ['SystemRoot']) / 'System32/wsl.exe'), '-d',
                                    'Ubuntu-24.04', '-u', 'hengxin', '--', 'sleep', 'infinity'],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        value = keeper_identity(process.pid, run)
        require(valid_keeper(value), 'Keeper failed identity check; inspect WSL keeper before retrying')
        owned = owner
    KEEPER_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = KEEPER_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps({'owner': owned, 'identity': value}), encoding='utf-8')
    temp.replace(KEEPER_FILE)
