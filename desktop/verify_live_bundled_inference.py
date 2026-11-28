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
import http.client
import re

from offline_analytics_cases import (
    CANDIDATES, CASES, SYSTEM, WORDING_SCENARIOS, WORDING_SYSTEM, score_answer,
    verified_candidate, wording_result,
)
from verify_inference_assets import verify


IDLE_SLEEP_SECONDS = 30
MEMORY_PROFILES = {'baseline': 512, 'reduced': 128}
CONTEXT_TOKENS = 2048
ANALYTICS_RESPONSE_TOKENS = 128


def port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def send(url: str, token: str | None = None, body: dict | None = None, timeout: float = 5):
    # This diagnostic may address only its own fixed loopback worker routes.
    match = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{3,4})(/health|/props|/v1/chat/completions)', url) if isinstance(url, str) else None
    if match is None or not 1024 <= int(match[1]) <= 65535:
        raise ValueError('Invalid local inference diagnostic destination')
    port_number, path = int(match[1]), match[2]
    if (path == '/v1/chat/completions') != isinstance(body, dict) or (body is not None and not isinstance(body, dict)):
        raise ValueError('Invalid local inference diagnostic method')
    # Preserve the deliberate unauthenticated generation refusal probe.
    if token is None:
        if path != '/v1/chat/completions':
            raise ValueError('Inference diagnostic session required')
    elif not isinstance(token, str) or re.fullmatch(r'[0-9a-f]{64}', token) is None:
        raise ValueError('Invalid inference diagnostic session')
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['Authorization'] = f'Bearer {token}'
    payload = json.dumps(body).encode('utf-8') if body is not None else None
    conn = http.client.HTTPConnection('127.0.0.1', port_number, timeout=timeout)
    try:
        conn.request('POST' if body is not None else 'GET', path, body=payload, headers=headers)
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise RuntimeError('Local inference diagnostic returned a redirect')
        limit = 4 * 1024 * 1024 if response.status < 400 else 256 * 1024
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise RuntimeError('Local inference diagnostic response exceeds safety limit')
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError('Invalid local inference diagnostic JSON') from None
        return response.status, result
    except http.client.RemoteDisconnected:
        raise
    except http.client.HTTPException:
        raise RuntimeError('Invalid local inference diagnostic HTTP') from None
    finally:
        conn.close()


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


def verify_idle_release(base: str, token: str, pid: int, model_alias: str, active_memory: dict) -> dict:
    deadline = time.monotonic() + IDLE_SLEEP_SECONDS + 20
    while time.monotonic() < deadline:
        status, props = send(base + '/props', token, timeout=3)
        if status == 200 and isinstance(props, dict) and props.get('is_sleeping') is True:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('Local worker did not sleep after the idle interval')

    sleeping_memory = worker_memory(pid)
    released = round(active_memory['working_set_mib'] - sleeping_memory['working_set_mib'], 1)
    if released <= 0:
        raise RuntimeError('Local worker sleep did not reduce its observed resident memory')

    started = time.monotonic()
    verify_idle_probe_completion(base, token, model_alias, phase='after waking')
    return {'before_sleep': active_memory, 'asleep': sleeping_memory,
            'resident_mib_released': released,
            'after_wake': {'request_seconds': round(time.monotonic() - started, 3), **worker_memory(pid)}}


def verify_idle_probe_completion(base: str, token: str, model_alias: str, *, phase: str) -> None:
    status, response = send(base + '/v1/chat/completions', token, {
        'model': model_alias, 'messages': [{'role': 'user', 'content': 'Respond with READY.'}],
        'max_tokens': 24, 'temperature': 0, 'stream': False,
        'chat_template_kwargs': {'enable_thinking': False},
    }, timeout=110)
    choices = response.get('choices') if isinstance(response, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    if status != 200 or not isinstance(content, str) or not content.strip() or choice.get('finish_reason') != 'stop':
        raise RuntimeError(f'Local worker failed to return a complete answer {phase}: HTTP {status}')


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


def evaluate_analytics(base: str, token: str, model_alias: str, pid: int,
                       *, include_long_prompt: bool = False) -> list[dict]:
    cases = [(name, facts, question, expected, '') for name, facts, question, expected in CASES]
    if include_long_prompt:
        _, facts, question, expected = CASES[0]
        padding = 'Synthetic context for the batch-size check.\n' * 100
        cases.append(('long_context_overview', facts, question, expected, padding))
    results = []
    for name, facts, question, expected, padding in cases:
        request_begin = time.monotonic()
        status, result = send(base + '/v1/chat/completions', token, {
            'model': model_alias,
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': padding + json.dumps({'verified_facts': facts, 'question': question})},
            ],
            'max_tokens': ANALYTICS_RESPONSE_TOKENS, 'temperature': 0, 'stream': False,
            'chat_template_kwargs': {'enable_thinking': False},
        }, timeout=60)
        if status != 200 or not isinstance(result, dict) or not result.get('choices'):
            raise RuntimeError(f'{name}: completion failed (HTTP {status})')
        request_seconds = round(time.monotonic() - request_begin, 3)
        choice = result['choices'][0]
        content = choice.get('message', {}).get('content')
        complete = choice.get('finish_reason') == 'stop'
        record = {'case': name, 'passed': complete and isinstance(content, str) and score_answer(content, expected),
                  'finish_reason': choice.get('finish_reason'), 'seconds': request_seconds, **worker_memory(pid)}
        if include_long_prompt:
            record['prompt_tokens'] = result.get('usage', {}).get('prompt_tokens')
        else:
            record['answer'] = content[:512] if isinstance(content, str) else None
        results.append(record)
    return results


def compare_worker_profiles(baseline: dict, reduced: dict) -> dict:
    """Recommend only an eligible candidate for physical testing."""
    resident_key = 'cumulative_peak_working_set_mib'
    commit_key = 'cumulative_peak_commit_mib'
    resident_saved = round(baseline['cases'][-1][resident_key] - reduced['cases'][-1][resident_key], 1)
    commit_saved = round(baseline['cases'][-1][commit_key] - reduced['cases'][-1][commit_key], 1)
    inputs_match = all(
        a['case'] == b['case'] and type(a['prompt_tokens']) is int
        and 0 < a['prompt_tokens'] <= CONTEXT_TOKENS - ANALYTICS_RESPONSE_TOKENS
        and a['prompt_tokens'] == b['prompt_tokens']
        for a, b in zip(baseline['cases'], reduced['cases'], strict=True)
    )
    long_prompt_exercises_both = (
        inputs_match and baseline['cases'][-1]['prompt_tokens'] > MEMORY_PROFILES['baseline']
    )
    quality_passed = all(case['passed'] for case in reduced['cases'])
    eligible = long_prompt_exercises_both and quality_passed and resident_saved > 0 and commit_saved >= 0
    return {
        'result': 'candidate_for_physical_retest' if eligible else 'retain_current_profile',
        'resident_mib_saved': resident_saved, 'commit_mib_saved': commit_saved,
        'matched_prompt_tokens': inputs_match, 'long_prompt_exercises_both_profiles': long_prompt_exercises_both,
        'answers_correct': {name: sum(case['passed'] for case in profile['cases'])
                            for name, profile in (('baseline', baseline), ('reduced', reduced))},
        'answer_count': len(reduced['cases']),
    }


def run_memory_comparison(root: Path, options: argparse.Namespace) -> int:
    profiles = {}
    for name, batch in MEMORY_PROFILES.items():
        try:
            profiles[name] = run_worker(root, options, physical_batch=batch, check_idle=name == 'baseline')
        except (OSError, ValueError, RuntimeError) as exc:
            print(f'OFFLINE AI WORKER PROFILE FAILED ({name}): {exc}', file=sys.stderr)
            profiles[name] = {'physical_batch': batch, 'status': 'failed'}
    completed = all('cases' in profile for profile in profiles.values())
    comparison = (compare_worker_profiles(profiles['baseline'], profiles['reduced']) if completed
                  else {'result': 'comparison_incomplete'})
    print('OFFLINE AI WORKER COMPARISON: ' + json.dumps({**comparison, 'profiles': profiles}, sort_keys=True))
    return 0 if completed and profiles['baseline']['idle_release']['status'] == 'passed' else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-profile', action='store_true',
                        help='Report worker memory at model readiness and after completion.')
    evaluation = parser.add_mutually_exclusive_group()
    evaluation.add_argument('--analytics-eval', action='store_true',
                            help='Score four synthetic analytics questions and report worker memory.')
    evaluation.add_argument('--wording-eval', action='store_true',
                            help='Score follow-up selection while keeping verified summaries fixed.')
    evaluation.add_argument('--verify-idle-release', action='store_true',
                            help='Measure RAM after idle sleep and verify an authenticated completion after waking.')
    evaluation.add_argument('--compare-worker-memory', action='store_true',
                            help='Measure the current and reduced physical batches on fresh workers, including idle release.')
    parser.add_argument('--candidate', choices=CANDIDATES,
                        help='Use a pinned alternate GGUF for the analytics evaluation only.')
    parser.add_argument('--candidate-file', type=Path, help='Local path to the pinned alternate GGUF.')
    options = parser.parse_args()
    evaluating = options.analytics_eval or options.wording_eval
    if (options.memory_profile or evaluating or options.verify_idle_release or options.compare_worker_memory) and os.name != 'nt':
        parser.error('Worker profiling requires Windows')
    if bool(options.candidate) != bool(options.candidate_file) or (options.candidate and not evaluating):
        parser.error('--candidate and --candidate-file must be used together in an evaluation mode')
    root = Path(__file__).resolve().parents[1]
    verify(root)
    if options.compare_worker_memory:
        return run_memory_comparison(root, options)
    return run_worker(root, options, check_idle=options.verify_idle_release)


def run_worker(root: Path, options: argparse.Namespace, *, physical_batch: int | None = None, check_idle: bool = False):
    profile_memory = options.memory_profile or options.analytics_eval or options.wording_eval or physical_batch is not None
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
            '--host', '127.0.0.1', '--port', str(listen_port), '--ctx-size', str(CONTEXT_TOKENS),
            '--threads', '2', '--parallel', '1', '--gpu-layers', '0',
            '--no-webui', '--no-agent']
    if physical_batch is not None:
        args.extend(('--ubatch-size', str(physical_batch)))
    if check_idle or physical_batch is not None:
        args.extend(('--sleep-idle-seconds', str(IDLE_SLEEP_SECONDS)))
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
        if physical_batch is not None:
            profile = {'physical_batch': physical_batch, 'model_ready': {'elapsed_seconds': load_seconds, **ready_memory},
                       'cases': evaluate_analytics(base, token, model_alias, proc.pid, include_long_prompt=True)}
            if check_idle:
                try:
                    profile['idle_release'] = {'status': 'passed', **verify_idle_release(
                        base, token, proc.pid, model_alias, worker_memory(proc.pid))}
                except (OSError, ValueError, RuntimeError) as exc:
                    print(f'OFFLINE AI IDLE RELEASE FAILED: {exc}', file=sys.stderr)
                    profile['idle_release'] = {'status': 'failed'}
            return profile
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
            results = evaluate_analytics(base, token, model_alias, proc.pid)
            print('OFFLINE ANALYTICS EVALUATION: ' + json.dumps({
                'model': model_name,
                'model_ready': {'elapsed_seconds': load_seconds, **ready_memory},
                'passed': sum(case['passed'] for case in results),
                'cases': results,
            }, sort_keys=True))
            return 0
        if options.verify_idle_release:
            verify_idle_probe_completion(base, token, model_alias, phase='before sleeping')
            print('OFFLINE AI IDLE RELEASE: ' + json.dumps(
                verify_idle_release(base, token, proc.pid, model_alias, worker_memory(proc.pid)),
                sort_keys=True,
            ))
            print('LIVE OFFLINE AI IDLE RELEASE CHECK PASSED')
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
        if physical_batch is not None:
            raise RuntimeError(f'Worker comparison failed at physical batch {physical_batch}') from exc
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
