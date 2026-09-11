#!/usr/bin/env python3
#!/usr/bin/env python3
"""Failure/recovery test: stop one backend, measure traffic, restore it, verify recovery."""
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
PROJECT = "barq-assessment"
TARGET_SERVICE = "app-01"
TARGET_INSTANCE_ID = "app-01"
REQUEST_TIMEOUT = 5
BURST_COUNT = 20
RECOVERY_TIMEOUT_S = 30


def docker_compose(*args):
    result = subprocess.run(
        ["docker", "compose", "-p", PROJECT, *args],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_instance():
    """Returns instance_id on success, or None on failure."""
    try:
        req = urllib.request.Request(BASE_URL + "/instance", method="GET")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return data.get("instance_id")
    except Exception:
        return None


def send_burst(n):
    """Send n requests to /instance, return (success_count, fail_count, instances_seen)."""
    success = 0
    fail = 0
    seen = set()
    for _ in range(n):
        instance = get_instance()
        if instance:
            success += 1
            seen.add(instance)
        else:
            fail += 1
    return success, fail, seen


def wait_for_condition(description, condition_fn, timeout_s=RECOVERY_TIMEOUT_S):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(1)
    raise RuntimeError(f"{description} did not happen within {timeout_s}s")


def main():
    print(f"=== Failure/recovery test: stopping {TARGET_SERVICE} ===\n")

    # Step 1: baseline
    print("Step 1: confirming baseline — both instances reachable")
    baseline_success, baseline_fail, baseline_seen = send_burst(10)
    print(f"  baseline: {baseline_success}/10 succeeded, instances seen: {baseline_seen}")
    if TARGET_INSTANCE_ID not in baseline_seen:
        print(f"FAIL: {TARGET_INSTANCE_ID} not seen in baseline traffic, cannot proceed")
        sys.exit(1)

    # Step 2: stop the target backend
    print(f"\nStep 2: stopping {TARGET_SERVICE}")
    docker_compose("stop", TARGET_SERVICE)
    print(f"  {TARGET_SERVICE} stopped")

    # Step 3: measure traffic during the outage
    print(f"\nStep 3: sending {BURST_COUNT} requests during outage, measuring traffic/errors")
    outage_success, outage_fail, outage_seen = send_burst(BURST_COUNT)
    print(f"  during outage: {outage_success}/{BURST_COUNT} succeeded, "
          f"{outage_fail}/{BURST_COUNT} failed, instances seen: {outage_seen}")

    outage_ok = True
    if TARGET_INSTANCE_ID in outage_seen:
        print(f"  FAIL: {TARGET_INSTANCE_ID} still answered requests after being stopped")
        outage_ok = False
    if outage_success == 0:
        print(f"  FAIL: zero requests succeeded during outage — service was fully unavailable, "
              f"not just degraded")
        outage_ok = False
    else:
        print(f"  PASS: service remained available during outage "
              f"({outage_success}/{BURST_COUNT} requests succeeded via surviving backend)")

    # Step 4: restart the backend
    print(f"\nStep 4: restarting {TARGET_SERVICE}")
    docker_compose("start", TARGET_SERVICE)

    # Step 5: bounded wait for it to become healthy again
    print(f"\nStep 5: waiting (bounded, max {RECOVERY_TIMEOUT_S}s) for {TARGET_SERVICE} to recover")

    def target_is_back():
        _, _, seen = send_burst(5)
        return TARGET_INSTANCE_ID in seen

    try:
        wait_for_condition(f"{TARGET_SERVICE} recovery", target_is_back)
        print(f"  PASS: {TARGET_SERVICE} is serving requests again")
        recovery_ok = True
    except RuntimeError as e:
        print(f"  FAIL: {e}")
        recovery_ok = False

    # Step 6: final confirmation — both instances present again
    print("\nStep 6: confirming both instances serve traffic post-recovery")
    final_success, final_fail, final_seen = send_burst(10)
    print(f"  final: {final_success}/10 succeeded, instances seen: {final_seen}")
    final_ok = final_seen == {"app-01", "app-02"}
    if final_ok:
        print("  PASS: both app-01 and app-02 confirmed serving requests")
    else:
        print(f"  FAIL: expected both instances, saw {final_seen}")

    print("\n=== Summary ===")
    all_ok = outage_ok and recovery_ok and final_ok
    if all_ok:
        print("PASS: failure and recovery test succeeded")
        sys.exit(0)
    else:
        print("FAIL: failure and recovery test did not fully succeed")
        sys.exit(1)


if __name__ == "__main__":
    main()
