#!/usr/bin/env python3
"""Run CubeMX interactive commands one at a time, stopping on ambiguous or failed replies."""
import argparse, json, os, queue, re, subprocess, sys, threading, time
from pathlib import Path

PROMPT = b'MX>'
STATUS = re.compile(r'(?m)^\s*(?:\d+\s+)?(OK|KO)\s*$')

class GuardError(Exception):
    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch', required=True, help='JSON with argv, cwd, optional env')
    parser.add_argument('--plan', required=True, help='JSON array of command objects')
    parser.add_argument('--events', required=True, help='JSON result path')
    parser.add_argument('--transcript', required=True, help='raw combined output path')
    parser.add_argument('--startup-timeout', type=float, default=60)
    parser.add_argument('--step-timeout', type=float, default=60)
    opt = parser.parse_args()
    launch = json.loads(Path(opt.launch).read_text(encoding='utf-8'))
    plan = json.loads(Path(opt.plan).read_text(encoding='utf-8'))
    if (not isinstance(launch, dict) or not isinstance(launch.get('argv'), list)
            or not launch['argv'] or not all(isinstance(x, str) and x for x in launch['argv'])
            or not isinstance(launch.get('env', {}), dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in launch.get('env', {}).items())
            or not isinstance(plan, list) or not plan):
        raise GuardError('invalid launch or empty plan')
    if opt.startup_timeout <= 0 or opt.step_timeout <= 0:
        raise GuardError('timeouts must be positive')
    for step in plan:
        if not isinstance(step, dict) or not isinstance(step.get('command'), str):
            raise GuardError('each step needs a command string')
        cmd = step['command'].strip()
        first = cmd.split(None, 1)[0].lower() if cmd else ''
        if not cmd or any(c in cmd for c in ('\n', '\r', '\x00')) or first in ('exit', 'exit_mx', 'script'):
            raise GuardError('each command must be one line; exit and nested scripts are forbidden')
        if (not isinstance(step.get('expect', []), list) or not isinstance(step.get('reject', []), list)
                or not all(isinstance(x, str) and x for x in step.get('expect', []) + step.get('reject', []))):
            raise GuardError('expect and reject must contain nonempty strings')
        if 'timeout' in step and (not isinstance(step['timeout'], (int, float)) or step['timeout'] <= 0):
            raise GuardError('step timeout must be positive')
    env = os.environ.copy()
    env.update(launch.get('env', {}))
    events = {'result': 'running', 'steps': []}
    out_path = Path(opt.events)
    transcript_path = Path(opt.transcript)
    if out_path.resolve() == transcript_path.resolve() or out_path.exists() or transcript_path.exists():
        raise GuardError('events and transcript must be distinct new files')
    q = queue.Queue()
    pending = bytearray()
    proc = None
    thread = None
    at_prompt = False
    transcript = transcript_path.open('xb')

    def pump():
        try:
            while True:
                chunk = proc.stdout.read1(8192)
                if not chunk:
                    break
                transcript.write(chunk)
                transcript.flush()
                q.put(chunk)
        finally:
            q.put(None)

    def wait_prompt(seconds, rejected=()):
        deadline = time.monotonic() + seconds
        while True:
            for text in rejected:
                if not isinstance(text, str):
                    raise GuardError('reject entries must be strings')
                if text.encode('utf-8') in pending:
                    raise GuardError(f'rejected output while waiting for prompt: {text!r}')
            if len(pending) > 16 * 1024 * 1024:
                raise GuardError('too much output while waiting for prompt')
            match = re.search(rb'(?m)^MX>', pending)
            if match:
                result = bytes(pending[:match.start()])
                del pending[:match.end()]
                return result.decode('utf-8', errors='replace')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GuardError('timeout waiting for MX>')
            try:
                chunk = q.get(timeout=remaining)
            except queue.Empty as exc:
                raise GuardError('timeout waiting for MX>') from exc
            if chunk is None:
                raise GuardError(f'process exited before prompt: {proc.poll()}')
            pending.extend(chunk)

    try:
        proc = subprocess.Popen(launch['argv'], cwd=launch.get('cwd'), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        wait_prompt(opt.startup_timeout)
        at_prompt = True
        for step in plan:
            cmd = step['command'].strip()
            event = {'command': cmd, 'result': 'sent'}
            events['steps'].append(event)
            proc.stdin.write((cmd + '\n').encode('utf-8'))
            proc.stdin.flush()
            at_prompt = False
            response = wait_prompt(float(step.get('timeout', opt.step_timeout)), step.get('reject', []))
            at_prompt = True
            statuses = STATUS.findall(response)
            event['statuses'] = statuses
            event['response_tail'] = response[-2000:]
            if len(statuses) != 1 or statuses[0] != 'OK':
                raise GuardError(f'command failed or response ambiguous: {cmd!r}, statuses={statuses!r}')
            for expected in step.get('expect', []):
                if not isinstance(expected, str) or expected not in response:
                    raise GuardError(f'expected output not found after {cmd!r}: {expected!r}')
            for rejected in step.get('reject', []):
                if not isinstance(rejected, str) or rejected in response:
                    raise GuardError(f'rejected output found after {cmd!r}: {rejected!r}')
            event['result'] = 'passed'
            print('PASS', cmd, flush=True)
        events['result'] = 'passed'
    except (GuardError, OSError, ValueError) as exc:
        events['result'] = 'failed'
        events['error'] = str(exc)
        print('STOP', exc, flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            if at_prompt:
                try:
                    proc.stdin.write(b'exit\n'); proc.stdin.flush()
                    proc.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
        if thread:
            thread.join(timeout=5)
        transcript.close()
        if proc is not None:
            events['process_exit'] = proc.poll()
            if events['result'] == 'passed' and proc.returncode != 0:
                events['result'] = 'failed'
                events['error'] = f'process exit code {proc.returncode}'
        if thread and thread.is_alive():
            events['result'] = 'failed'
            events['error'] = 'output reader did not terminate'
        with out_path.open('x', encoding='utf-8') as event_file:
            json.dump(events, event_file, ensure_ascii=False, indent=2)
    return 0 if events['result'] == 'passed' else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (GuardError, OSError, ValueError, json.JSONDecodeError) as exc:
        print('STOP', exc, file=sys.stderr)
        sys.exit(2)