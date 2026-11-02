"""CAD client timeout behavior with local synthetic workers, no network or CAD build."""
import json
import subprocess
import sys
import time
import pytest
import cad_client


def process(code):
    return subprocess.Popen([sys.executable, '-u', '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)


def test_response_received_with_timeout(monkeypatch):
    cad_client.stop_quietly()
    p = process('import sys,json; r=json.loads(sys.stdin.readline()); print(json.dumps({"id":r["id"],"ok":True,"result":{"answer":42}}),flush=True)')
    monkeypatch.setattr(cad_client, '_proc', p)
    try:
        assert cad_client.call('ping', timeout=3)['answer'] == 42
    finally:
        cad_client.stop_quietly(); p.wait(timeout=5)


def test_timeout_stops_unresponsive_worker(monkeypatch):
    cad_client.stop_quietly()
    p = process('import sys,time; sys.stdin.readline(); time.sleep(30)')
    monkeypatch.setattr(cad_client, '_proc', p)
    started = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match='timed out'):
            cad_client.call('ping', timeout=0.3)
        assert time.monotonic() - started < 5
        assert p.poll() is not None and cad_client._proc is None
    finally:
        if p.poll() is None: p.kill(); p.wait(timeout=5)
        cad_client.stop_quietly()


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf'), True, 'fast'])
def test_bad_timeout_rejected(timeout):
    with pytest.raises(ValueError, match='positive'):
        cad_client.call('ping', timeout=timeout)
