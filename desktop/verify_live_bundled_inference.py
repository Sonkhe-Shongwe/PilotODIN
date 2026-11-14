"""Run the pinned Windows llama.cpp/Qwen3 runtime over localhost.

Run after staging the verified runtime and model. This check validates the
localhost API, session authentication, model load and a real chat completion.
The optional memory profile describes this worker on this host. Physical 8 GB
coexistence and long-session use require their own verification.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from offline_analytics_cases import (
    CANDIDATES, CASES, SYSTEM, WORDING_SCENARIOS, WORDING_SYSTEM, score_answer,
    verified_candidate, wording_result,
)
from verify_inference_assets import verify


def port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def send(url: str, token: str | None = None, body: dict | None = None, timeout: float = 5):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    payload = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=payload, headers=headers,
                                     method='POST' if body is not None else 'GET')
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return response.status, json.loads(response.read(4 * 1024 * 1024))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read(256 * 1024))


def worker_memory(pid: int) -> dict[str, float | int]:
    """Read Windows' cumulative peak and current resident RAM for one worker."""
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('page_fault_count', wintypes.DWORD),
            ('peak_working_set', ctypes.c_size_t),
            ('working_set', ctypes.c_size_t),
            ('peak_paged_pool', ctypes.c_size_t),
            ('paged_pool', ctypes.c_size_t),
            ('peak_nonpaged_pool', ctypes.c_size_t),
            ('nonpaged_pool', ctypes.c_size_t),
            ('commit', ctypes.c_size_t),
            ('peak_commit', ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.K32GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD,
    )
    kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    query_limited_information = 0x1000
    handle = kernel.OpenProcess(query_limited_information, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    counters = ProcessMemoryCounters(cb=ctypes.sizeof(ProcessMemoryCounters))
    try:
        if not kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)

    mib = 1024 ** 2
    return {
        'working_set_mib': round(counters.working_set / mib, 1),
        'cumulative_peak_working_set_mib': round(counters.peak_working_set / mib, 1),
        'commit_mib': round(counters.commit / mib, 1),
        'cumulative_peak_commit_mib': round(counters.peak_commit / mib, 1),
    }


def evaluate_wording(base: str, token: str, model_alias: str, pid: int) -> list[dict]:
    results = []
    for case_name, summary, follow_ups, questions in WORDING_SCENARIOS:
        for expected, question in zip(('A', 'B'), questions):
            started = time.monotonic()
            request = {
                'model': model_alias,
                'messages': [
                    {'role': 'system', 'content': WORDING_SYSTEM},
                    {'role': 'user', 'content': f'{question}\nA: {follow_ups[0]}\nB: {follow_ups[1]}'},
                ],
                'max_tokens': 8, 'temperature': 0, 'stream': False,
                'chat_template_kwargs': {'enable_thinking': False},
            }
            try:
                status, result = send(base + '/v1/chat/completions', token, request, timeout=60)
            except (OSError, ValueError):
                status, result = None, None
            elapsed = round(time.monotonic() - started, 3)
            choices = result.get('choices') if status == 200 and isinstance(result, dict) else None
            choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
            message = choice.get('message')
            content = message.get('content') if isinstance(message, dict) else None
            answer, selected = wording_result(summary, follow_ups, content, choice.get('finish_reason'))
            results.append({
                'case': case_name, 'expected': expected, 'selected': selected,
                'matched': selected == expected, 'fallback': selected is None,
                'http_status': status, 'finish_reason': choice.get('finish_reason'),
                'answer': answer, 'seconds': elapsed, **worker_memory(pid),
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-profile', action='store_true',
                        help='Report worker memory at model readiness and after completion.')
    evaluation = parser.add_mutually_exclusive_group()
    evaluation.add_argument('--analytics-eval', action='store_true',
                            help='Score four synthetic analytics questions and report worker memory.')
    evaluation.add_argument('--wording-eval', action='store_true',
                            help='Score follow-up selection while keeping verified summaries fixed.')
    parser.add_argument('--candidate', choices=CANDIDATES,
                        help='Use a pinned alternate GGUF for the analytics evaluation only.')
    parser.add_argument('--candidate-file', type=Path, help='Local path to the pinned alternate GGUF.')
    options = parser.parse_args()
    evaluating = options.analytics_eval or options.wording_eval
    if (options.memory_profile or evaluating) and os.name != 'nt':
        parser.error('Worker profiling requires Windows')
    if bool(options.candidate) != bool(options.candidate_file) or (options.candidate and not evaluating):
        parser.error('--candidate and --candidate-file must be used together in an evaluation mode')
    profile_memory = options.memory_profile or evaluating

    root = Path(__file__).resolve().parents[1]
    verify(root)
    tauri = root / 'frontend' / 'src-tauri'
    model = tauri / 'resources' / 'models' / 'qwen3-1.7b-q4_k_m.gguf'
    model_name = options.candidate or 'qwen3-1.7b-q4-k-m'
    model_alias = options.candidate or 'pilotodin-qwen3-1.7b'
    if options.candidate:
        model = verified_candidate(options.candidate, options.candidate_file)
    runtime = tauri / 'binaries' / 'pilotodin-inference-x86_64-pc-windows-msvc.exe'
    dlls = tauri / 'resources' / 'llama-runtime'
    listen_port = port()
    token = secrets.token_hex(32)
    env = os.environ.copy()
    env['LLAMA_API_KEY'] = token
    env['PATH'] = os.pathsep.join((str(dlls), env.get('PATH', '')))
    args = [str(runtime), '--model', str(model), '--alias', model_alias,
            '--host', '127.0.0.1', '--port', str(listen_port), '--ctx-size', '2048',
            '--threads', '2', '--parallel', '1', '--gpu-layers', '0',
            '--no-webui', '--no-agent']
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # Startup diagnostics identify missing vendor DLLs and unsupported flags.
    # Bound and redact output; no user documents are involved in this CI check.
    log_path = root / 'build' / 'offline-inference-startup.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('wb') as log:
        startup_begin = time.monotonic()
        proc = subprocess.Popen(args, cwd=dlls, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT,
                                creationflags=flags)
    base = f'http://127.0.0.1:{listen_port}'
    try:
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f'Local inference worker exited during model load ({proc.returncode})')
            try:
                code, result = send(base + '/health', token, timeout=3)
                if code == 200 and isinstance(result, dict) and result.get('status') == 'ok':
                    break
            except (OSError, TimeoutError, ValueError):
                pass
            time.sleep(0.6)
        else:
            raise RuntimeError('Local GGUF did not become healthy within 150 seconds')
        if profile_memory:
            load_seconds = round(time.monotonic() - startup_begin, 3)
            ready_memory = worker_memory(proc.pid)
        unauthenticated_probe = {
            'model': model_alias,
            'messages': [{'role': 'user', 'content': 'Ping'}],
            'max_tokens': 1, 'stream': False,
        }
        if send(base + '/v1/chat/completions', body=unauthenticated_probe, timeout=5)[0] != 401:
            raise RuntimeError('Local inference API failed to reject unauthenticated generation')
        if options.wording_eval:
            results = evaluate_wording(base, token, model_alias, proc.pid)
            print('OFFLINE WORDING EVALUATION: ' + json.dumps({
                'model': model_name,
                'model_ready': {'elapsed_seconds': load_seconds, **ready_memory},
                'matched': sum(case['matched'] for case in results),
                'fallbacks': sum(case['fallback'] for case in results),
                'cases': results,
            }, sort_keys=True))
            return 0
        if options.analytics_eval:
            results = []
            for case_name, facts, question, expected in CASES:
                request_begin = time.monotonic()
                status, result = send(base + '/v1/chat/completions', token, {
                    'model': model_alias,
                    'messages': [
                        {'role': 'system', 'content': SYSTEM},
                        {'role': 'user', 'content': json.dumps({'verified_facts': facts, 'question': question})},
                    ],
                    'max_tokens': 128, 'temperature': 0, 'stream': False,
                    'chat_template_kwargs': {'enable_thinking': False},
                }, timeout=60)
                request_seconds = round(time.monotonic() - request_begin, 3)
                if status != 200 or not isinstance(result, dict) or not result.get('choices'):
                    raise RuntimeError(f'{case_name}: completion failed (HTTP {status})')
                choice = result['choices'][0]
                content = choice.get('message', {}).get('content')
                complete = choice.get('finish_reason') == 'stop'
                results.append({
                    'case': case_name, 'passed': complete and isinstance(content, str) and score_answer(content, expected),
                    'finish_reason': choice.get('finish_reason'),
                    'answer': content[:512] if isinstance(content, str) else None,
                    'seconds': request_seconds,
                    **worker_memory(proc.pid),
                })
            print('OFFLINE ANALYTICS EVALUATION: ' + json.dumps({
                'model': model_name,
                'model_ready': {'elapsed_seconds': load_seconds, **ready_memory},
                'passed': sum(case['passed'] for case in results),
                'cases': results,
            }, sort_keys=True))
            return 0
        generation_begin = time.monotonic()
        status, result = send(base + '/v1/chat/completions', token,
                              {'model': model_alias,
                               'messages': [{'role': 'user', 'content': 'Respond with READY.'}],
                               'max_tokens': 24, 'temperature': 0, 'stream': False}, timeout=110)
        if status != 200 or not isinstance(result, dict) or not result.get('choices'):
            raise RuntimeError(f'Bundled Qwen3 failed authenticated text generation: HTTP {status}')
        if options.memory_profile:
            generation_seconds = round(time.monotonic() - generation_begin, 3)
            profile = {
                'scope': 'standalone_windows_worker_short_smoke',
                'model_ready': {'elapsed_seconds': load_seconds, **ready_memory},
                'after_completion': {
                    'request_seconds': generation_seconds, **worker_memory(proc.pid),
                },
            }
            print('OFFLINE AI WORKER MEMORY: ' + json.dumps(profile, sort_keys=True))
        print('LIVE OFFLINE AI CHECK PASSED: Qwen3 GGUF loaded, llama.cpp served locally, authentication enforced, completion returned')
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'LIVE OFFLINE AI CHECK FAILED: {exc}', file=sys.stderr)
        try:
            transcript = log_path.read_bytes()[-12_000:].decode('utf-8', errors='replace')
            transcript = transcript.replace(token, '[REDACTED]')
            for line in transcript.splitlines()[-45:]:
                print('LLAMA STARTUP DIAGNOSTIC: ' + line[:320], file=sys.stderr)
        except OSError:
            print('LLAMA STARTUP DIAGNOSTIC: startup log unavailable', file=sys.stderr)
        return 1
    finally:
        if os.name == 'nt' and proc.poll() is None:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=15, check=False)
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=8)
        log_path.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
