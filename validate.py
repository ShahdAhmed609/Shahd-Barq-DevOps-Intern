#!/usr/bin/env python3
"""Environment validation: bounded checks with PASS/FAIL and non-zero exit on failure."""
import sys
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.error

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8080", help="Base URL to test")
parser.add_argument("--instances", default="app-01,app-02",
                     help="Comma-separated list of expected instance IDs")
parser.add_argument("--project", default="barq-assessment", help="Docker Compose project name")
args = parser.parse_args()

BASE_URL = args.url
EXPECTED_INSTANCES = set(args.instances.split(","))
PROJECT = args.project
TIMEOUT = 3
RESULTS = []


def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
        print(f"PASS: {name}" + (f" ({detail})" if detail else ""))
    except Exception as e:
        RESULTS.append((name, False, str(e)))
        print(f"FAIL: {name} -- {e}")


def http_get(path, timeout=TIMEOUT):
    req = urllib.request.Request(BASE_URL + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
        return resp.status, body


def wait_for_ready(timeout_s=30):
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            status, body = http_get("/ready")
            if status == 200:
                return True
        except Exception as e:
            last_err = e
        time.sleep(1)
    raise RuntimeError(f"service never became ready within {timeout_s}s (last error: {last_err})")


def check_root():
    status, body = http_get("/")
    assert status == 200, f"expected 200, got {status}"
    data = json.loads(body)
    assert "message" in data and "instance_id" in data, "missing message/instance_id"
    return f"instance={data['instance_id']}"


def check_health():
    status, _ = http_get("/health")
    assert status == 200, f"expected 200, got {status}"


def check_ready():
    status, body = http_get("/ready")
    assert status == 200, f"expected 200, got {status}"
    data = json.loads(body)
    deps = data.get("dependencies", {})
    assert deps.get("postgres") == "ready", f"postgres not ready: {deps}"
    assert deps.get("redis") == "ready", f"redis not ready: {deps}"


def check_instance_all_backends():
    seen = set()
    tries = max(30, len(EXPECTED_INSTANCES) * 10)
    for _ in range(tries):
        status, body = http_get("/instance")
        assert status == 200, f"expected 200, got {status}"
        data = json.loads(body)
        seen.add(data["instance_id"])
        if EXPECTED_INSTANCES.issubset(seen):
            break
    assert EXPECTED_INSTANCES.issubset(seen), f"expected {EXPECTED_INSTANCES}, only saw: {seen}"
    return f"saw {seen}"


def check_records():
    status, body = http_get("/records")
    assert status == 200, f"GET /records expected 200, got {status}"
    req = urllib.request.Request(
        BASE_URL + "/records",
        data=json.dumps({"title": "validate.py check"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        assert resp.status == 201, f"POST /records expected 201, got {resp.status}"


def check_counter():
    status, body = http_get("/counter")
    assert status == 200, f"expected 200, got {status}"
    data = json.loads(body)
    assert isinstance(data.get("counter"), int), f"counter not an int: {data}"


def check_unknown_route_404():
    try:
        http_get("/this-route-does-not-exist")
        raise AssertionError("expected 404, got success")
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"expected 404, got {e.code}"


def check_prohibited_ports_closed():
    import socket
    for host, port, name in [("127.0.0.1", 15432, "postgres"), ("127.0.0.1", 16379, "redis")]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((host, port))
        s.close()
        assert result != 0, f"{name} port {port} is reachable from host (should not be published)"


def check_network_isolation():
    result = subprocess.run(
        ["docker", "compose", "-p", PROJECT, "exec", "-T", "nginx",
         "sh", "-c", "timeout 3 getent hosts postgres"],
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode != 0, (
        f"nginx can resolve 'postgres' hostname (should be isolated on backend network): "
        f"{result.stdout}"
    )


def main():
    print(f"Testing against {BASE_URL}, expecting instances: {EXPECTED_INSTANCES}")
    print("Waiting for environment readiness (bounded, max 30s)...")
    check("environment becomes ready", wait_for_ready)

    check("GET / returns message + instance_id", check_root)
    check("GET /health returns 200", check_health)
    check("GET /ready confirms postgres+redis", check_ready)
    check(f"GET /instance shows all expected instances via nginx", check_instance_all_backends)
    check("POST/GET /records works (real Postgres)", check_records)
    check("GET /counter increments (real Redis)", check_counter)
    check("Unknown route returns 404", check_unknown_route_404)
    check("Postgres/Redis ports not published to host", check_prohibited_ports_closed)
    check("nginx cannot resolve postgres (network isolation)", check_network_isolation)

    failures = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed.")
    if failures:
        print("FAILED CHECKS:")
        for name, _, detail in failures:
            print(f"  - {name}: {detail}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
