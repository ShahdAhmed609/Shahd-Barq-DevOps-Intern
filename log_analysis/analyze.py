import json
from collections import Counter, defaultdict

def load_jsonl(path):
    records = []
    bad_lines = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                bad_lines.append((i, line, str(e)))
    if bad_lines:
        print(f"WARNING: {len(bad_lines)} malformed line(s) in {path}:")
        for lineno, content, err in bad_lines:
            print(f"  Line {lineno}: {content[:100]} -- {err}")
    return records

access = load_jsonl("logs/access.log")
app = load_jsonl("logs/application.log")

print(f"access.log entries: {len(access)}")
print(f"application.log entries: {len(app)}")

print("\n--- access.log status code counts ---")
status_counts = Counter(r["status"] for r in access)
for status, count in sorted(status_counts.items()):
    print(f"{status}: {count}")

print("\n--- access.log requests per path ---")
path_counts = Counter(r["path"] for r in access)
for path, count in sorted(path_counts.items(), key=lambda x: -x[1]):
    print(f"{path}: {count}")

print("\n--- application.log event types ---")
event_counts = Counter(r.get("event") for r in app)
for event, count in event_counts.items():
    print(f"{event}: {count}")

print("\n--- application.log level counts ---")
level_counts = Counter(r.get("level") for r in app)
for level, count in level_counts.items():
    print(f"{level}: {count}")


print("\n--- Non-200 access.log entries, chronological ---")
for r in access:
    if r["status"] != 200 and r["path"] != "/missing":
        print(f'{r["timestamp"]}  {r["status"]}  {r["path"]:12s}  upstream={r["upstream"]}  req_id={r["request_id"]}')

print("\n--- dependency_error events, chronological ---")
for r in app:
    if r.get("event") == "dependency_error":
        print(f'{r["timestamp"]}  dependency={r.get("dependency")}  instance={r.get("instance_id")}  req_id={r.get("request_id")}')


print("\n--- Q1: duplicate request_ids in access.log ---")
from collections import Counter
ids = [r["request_id"] for r in access]
id_counts = Counter(ids)
dupes = {k: v for k, v in id_counts.items() if v > 1}
print(f"Total access.log entries: {len(access)}")
print(f"Distinct request_ids: {len(id_counts)}")
print(f"Duplicate request_ids: {len(dupes)}")
if dupes:
    print(dupes)

print("\n--- Q2: distinct client requests (dedup) ---")
# Each distinct request_id = one real client request, even if nginx tried
# multiple upstreams (comma-separated upstream field) for that same id.
print(f"Distinct client requests (access.log): {len(id_counts)}")

print("\n--- Q3: final client status counts + error rate ---")
total = len(access)
status_counts = Counter(r["status"] for r in access)
non_200 = total - status_counts.get(200, 0)
print(f"Denominator (total valid access.log entries): {total}")
for status, count in sorted(status_counts.items()):
    print(f"{status}: {count} ({100*count/total:.2f}%)")
print(f"Error rate (non-200 / total): {non_200}/{total} = {100*non_200/total:.2f}%")

print("\n--- Q5: latency percentiles (request_time, seconds) ---")
import statistics
times = sorted(r["request_time"] for r in access)
n = len(times)
median = statistics.median(times)
p95_index = int(0.95 * n)
p95 = times[min(p95_index, n-1)]
print(f"n={n}")
print(f"median request_time: {median:.3f}s")
print(f"p95 request_time (nearest-rank method): {p95:.3f}s")

print("\n--- Q6: retried requests ---")
retried = [r for r in access if "," in r.get("upstream", "")]
retried_succeeded = [r for r in retried if r["status"] == 200]
print(f"Requests that hit multiple upstreams (retried): {len(retried)}")
print(f"Of those, succeeded (status 200): {len(retried_succeeded)}")



print("\n--- Q1b: duplicate line details ---")
seen = {}
for r in access:
    key = r["request_id"]
    seen.setdefault(key, []).append(r)
for rid, lines in seen.items():
    if len(lines) > 1:
        print(f"{rid}: {len(lines)} identical lines, timestamp={lines[0]['timestamp']}, path={lines[0]['path']}")

print("\n--- Q3b: deduplicated status counts (720 distinct requests) ---")
dedup = {r["request_id"]: r for r in access}.values()
total_dedup = len(dedup)
status_counts_dedup = Counter(r["status"] for r in dedup)
non_200_dedup = total_dedup - status_counts_dedup.get(200, 0)
print(f"Denominator (distinct request_ids): {total_dedup}")
for status, count in sorted(status_counts_dedup.items()):
    print(f"{status}: {count} ({100*count/total_dedup:.2f}%)")
print(f"Error rate (deduplicated): {non_200_dedup}/{total_dedup} = {100*non_200_dedup/total_dedup:.2f}%")
