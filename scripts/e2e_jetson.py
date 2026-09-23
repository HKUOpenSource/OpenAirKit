"""Run the four-page browser checks with isolated simulator state."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/jetson-console/backend'))
from aoc_jetson.api import password_record
from aoc_jetson.config import validate
from aoc_jetson.store import Store


def main():
    with tempfile.TemporaryDirectory(prefix='aoc-je-', dir='/tmp') as directory:
        root = Path(directory)
        config = json.loads((ROOT / 'config/jetson.example.json').read_text())
        config.update(state_dir=str(root / 'state'), web_state_dir=str(root / 'web'),
                      agent_socket=str(root / 'device.sock'), commissioned=True,
                      management_verified=True, sim_sha256='0' * 64, simulation=True)
        config = validate(config)
        Store(root / 'state/device.db').set('maintenance', False)
        device = root / 'device.json'
        device.write_text(json.dumps(config))
        web = {**config, 'frontend_dir': str(ROOT / 'apps/jetson-console/frontend/dist'),
               'password_hash': password_record('Jetson-Local-Preview-2026')}
        web_path = root / 'web.json'
        web_path.write_text(json.dumps(web))
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'apps/jetson-console/backend')}
        processes = []
        with socket.socket() as listener, (root / 'server.log').open('w+') as log:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            base = 'http://127.0.0.1:' + str(listener.getsockname()[1])
            try:
                processes.append(subprocess.Popen([sys.executable, '-m', 'aoc_jetson.agent', '--config', str(device)],
                                                  env=env, stdout=log, stderr=log))
                code = ('import json,sys,uvicorn; from aoc_jetson.api import create_app; '
                        'uvicorn.run(create_app(json.load(open(sys.argv[1]))),fd=int(sys.argv[2]),'
                        'access_log=False,timeout_graceful_shutdown=2)')
                processes.append(subprocess.Popen([sys.executable, '-c', code, str(web_path), str(listener.fileno())],
                    pass_fds=(listener.fileno(),), env=env, stdout=log, stderr=log))
                http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                deadline = time.monotonic() + 20
                while True:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError('Simulator exited before readiness')
                    try:
                        with http.open(base + '/api/v1/health', timeout=1) as response:
                            if json.load(response).get('device') == 'ok':
                                break
                    except OSError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError('Simulator readiness timed out')
                    time.sleep(.1)
                subprocess.run(['node', 'apps/jetson-console/frontend/check-browser.mjs', base],
                               cwd=ROOT, env=env, check=True, timeout=180)
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                for process in reversed(processes):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    main()
