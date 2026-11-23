"""Start the local-only standalone iSpeak bundle, keeping user data external."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
PYTHON = ROOT / 'python' / 'python.exe'
SIGNAL = ROOT / 'Extras' / 'PixelStreaming' / 'local_signalling.py'
GAME_DIR = ROOT / 'game' / 'Windows'
GAME_BIN = GAME_DIR / 'MetaHumanPreview' / 'Binaries' / 'Win64'
GAME_CHOICES = (GAME_BIN / 'MetaHumanPreview-Win64-Development.exe', GAME_BIN / 'MetaHumanPreview.exe')
USER_ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'iSpeakStandalone'
USER_UE = USER_ROOT / 'Unreal'
TOKEN = USER_UE / 'Saved' / 'ispeak-ue-token.txt'
CONSULTATION_MODE = os.environ.get('ISPEAK_CONSULTATION_WORKSPACE') == '1'
WEB_PORT = 18008 if CONSULTATION_MODE else 8008
WEB_URL = f'http://localhost:{WEB_PORT}/'
CONFIG = USER_ROOT / 'speaking.env'
WORKSPACE_CONFIG = ROOT.parent / 'PolySpeak_Merged_20261116' / 'PolySpeak' / 'speaking.env'
USE_WORKSPACE_CONFIG = (CONSULTATION_MODE and WORKSPACE_CONFIG.is_file()
                        and (not CONFIG.is_file() or not (dotenv_values(CONFIG).get('DASHSCOPE_API_KEY') or '').strip()))
if USE_WORKSPACE_CONFIG:
    CONFIG = WORKSPACE_CONFIG
PORTS = (WEB_PORT, 8088, 8888, 18711)
children: list[subprocess.Popen] = []


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD)]


class EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class ChildJob:
    """Windows closes this job's children even if the launcher window is closed."""
    def __init__(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, child):
        if not self.kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(child._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def ensure_ports_available():
    sockets = []
    try:
        for port in PORTS:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(sock)
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as exc:
                raise RuntimeError(f'Local port {port} is in use. Close the application using that port and start iSpeak again.') from exc
    finally:
        for sock in sockets:
            sock.close()


def token_digest():
    try:
        return hashlib.sha256(TOKEN.read_bytes()).digest()
    except FileNotFoundError:
        return None


def spawn(job, args, cwd, env, log):
    process = subprocess.Popen(args, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    children.append(process)
    job.assign(process)
    return process


def wait_for(label, predicate, processes, seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError(f'A component exited while starting {label}. Check the local logs.')
        if predicate():
            return
        time.sleep(.25)
    raise RuntimeError(f'Timed out while starting {label}. Check the local logs.')


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
            return True
    except OSError:
        return False


def app_ready():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{WEB_PORT}/api/speaking/status', timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def read_private_config():
    # Only the expected settings are inherited from the user's local file.
    values = dotenv_values(CONFIG) if CONFIG.is_file() else {}
    permitted = ('DASHSCOPE_API_KEY', 'AZURE_KEY', 'AZURE_SPEECH_KEY', 'AZURE_REGION')
    env = os.environ.copy()
    for key in list(env):
        if key in permitted or key.startswith('SPEAKING_') or key.startswith('ISPEAK_'):
            env.pop(key, None)
    for key, value in values.items():
        if value is not None and (key in permitted or key.startswith('SPEAKING_')):
            env[key] = value
    # Fixed endpoints and token path cannot be overridden by inherited settings.
    env['SPEAKING_PORT'] = str(WEB_PORT)
    env['ISPEAK_UE_TOKEN_FILE'] = str(TOKEN)
    env['ISPEAK_RUNTIME_DIR'] = str(USER_ROOT / 'data')
    return env


def main():
    if os.name != 'nt':
        raise RuntimeError('iSpeak requires Windows.')
    game = next((candidate for candidate in GAME_CHOICES if candidate.is_file()), None)
    if not (PYTHON.is_file() and SIGNAL.is_file() and (APP / 'run-speaking.py').is_file() and game):
        raise RuntimeError('Some application files are missing. Extract the full archive before starting iSpeak.')
    ensure_ports_available()
    USER_ROOT.mkdir(parents=True, exist_ok=True)
    USER_UE.mkdir(parents=True, exist_ok=True)
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    (USER_ROOT / 'logs').mkdir(exist_ok=True)
    if not CONFIG.exists():
        if USE_WORKSPACE_CONFIG:
            print('The workspace profile is missing. Run Start iSpeak to create a local profile.')
            return
        example = APP / 'speaking.env.example'
        with CONFIG.open('x', encoding='utf-8') as target:
            target.write(example.read_text(encoding='utf-8'))
        print(f'Created your local profile at {CONFIG}.')
        print('Enter your DashScope API key in that file, save it and restart iSpeak.')
        return
    env = read_private_config()
    if not env.get('DASHSCOPE_API_KEY', '').strip():
        print(f'Enter your DashScope API key in {CONFIG} before starting iSpeak.')
        return
    # Services that do not call speech providers do not receive the API keys.
    public_env = {k: v for k, v in env.items() if k not in ('DASHSCOPE_API_KEY', 'AZURE_KEY', 'AZURE_SPEECH_KEY')}
    old_token = token_digest()
    job = ChildJob()
    logs = []
    try:
        for name in ('signal', 'unreal', 'ispeak'):
            logs.append((USER_ROOT / 'logs' / f'{name}.log').open('a', encoding='utf-8'))
        print('Starting the character and practice room…', flush=True)
        signal_process = spawn(job, [str(PYTHON), '-I', '-X', 'utf8', str(SIGNAL)], ROOT, public_env, logs[0])
        wait_for('local streaming service', lambda: port_open(8088) and port_open(8888), [signal_process], 30)
        game_process = spawn(job, [str(game), '-PixelStreamingConnectionURL=ws://127.0.0.1:8888',
                                   '-UserDir=' + str(USER_UE), '-windowed', '-ResX=1280', '-ResY=720'],
                             GAME_DIR, public_env, logs[1])
        wait_for('character', lambda: TOKEN.is_file() and token_digest() != old_token and port_open(18711),
                 [signal_process, game_process], 180)
        app_process = spawn(job, [str(PYTHON), '-I', '-X', 'utf8', str(APP / 'run-speaking.py')],
                            APP, env, logs[2])
        wait_for('iSpeak', app_ready, [signal_process, game_process, app_process], 90)
        print(f'iSpeak is ready at {WEB_URL}', flush=True)
        print('Keep both windows open while practising. Save your work, then press Enter here to exit.', flush=True)
        webbrowser.open(WEB_URL)
        # Check children while the console remains interactive.
        import msvcrt
        while True:
            if any(child.poll() is not None for child in children):
                print('A component exited. Closing the remaining iSpeak processes.', flush=True)
                break
            if msvcrt.kbhit() and msvcrt.getwch() in ('\r', '\n'):
                break
            time.sleep(.25)
    finally:
        # This closes only this invocation's job and its assigned child processes.
        job.close()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.terminate()
        for log in logs:
            log.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nExiting iSpeak.')
    except Exception as exc:
        print(f'Could not start iSpeak. {exc}')
        print(f'Local logs are in {USER_ROOT / "logs"}')
    input('Press Enter to close this window.')
