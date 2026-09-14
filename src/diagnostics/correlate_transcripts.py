"""Read-only identifier correlation; print aggregates, never transcript content.

Run as a file with --container and --transcript (path inside the container).
No credentials, traffic fixtures, or exported transcripts are written to disk.
"""
import argparse
from collections import Counter, defaultdict
import json
import subprocess
import urllib.request
from urllib.parse import urlsplit


TRANSCRIPT_INDEX = r'''
import json,sys
from pathlib import Path
from collections import Counter
main=Path(sys.argv[1])
if not main.is_file(): raise SystemExit("Main transcript missing")
files=[main, *main.with_suffix("").joinpath("subagents").rglob("*.jsonl")]
rows=[]; foo=0; incomplete=0
for path in files:
    scope="main" if path==main else "subagent:"+path.stem
    for line in path.open():
        try: entry=json.loads(line)
        except ValueError: incomplete+=1; continue
        msg=entry.get("message") or {}
        content=msg.get("content",[])
        if isinstance(content,str): content=[{"text":content}]
        if isinstance(content,list):
            foo+=sum(isinstance(b,dict) and b.get("text")=="foo" for b in content)
        if entry.get("type")!="assistant": continue
        rows.append({"scope":scope,"message_id":msg.get("id"),"request_id":entry.get("requestId"),
                     "sidechain":entry.get("isSidechain"),"session_id":entry.get("sessionId")})
print(json.dumps({"files":len(files),"subagent_files":len(files)-1,"foo_blocks":foo,
                  "incomplete_records":incomplete,"rows":rows}))
'''


def identifier_index(rows, field):
    result = defaultdict(set)
    for row in rows:
        if row.get(field):
            result[row[field]].add(row["scope"])
    return result


def join_scope(message_scopes, request_scopes):
    scopes = message_scopes | request_scopes
    if message_scopes and request_scopes and message_scopes != request_scopes:
        return "conflicting_identifiers"
    if len(scopes) > 1:
        return "ambiguous_scope"
    if scopes:
        return "exact_" + ("main" if scopes == {"main"} else "subagent")
    return "unmatched"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    args = parser.parse_args()

    def get(path):
        with urllib.request.urlopen(args.server.rstrip("/") + path, timeout=30) as response:
            return json.load(response)

    active = get("/api/sessions/active")
    if not active or not active["alive"]:
        raise SystemExit("No active session")
    base = f'/api/sessions/{active["session_id"]}'
    # Freeze a request list before reading the concurrently growing transcript.
    events = []
    before = None
    while True:
        page = get(base + "/context-history?limit=100" + (f"&before={before}" if before else ""))
        events.extend(page["events"])
        before = page["next_before"]
        if before is None:
            break
    transcript = json.loads(subprocess.run(
        ["podman", "exec", "-i", args.container, "python3", "-", args.transcript],
        input=TRANSCRIPT_INDEX, text=True, capture_output=True, check=True,
    ).stdout)
    rows = transcript.pop("rows")
    mids, rids = identifier_index(rows, "message_id"), identifier_index(rows, "request_id")
    responses = {e["flow_id"]: e for e in events if e["kind"] == "context.response"}
    counts = Counter()
    header_matches = Counter()
    operations = defaultdict(Counter)
    matched_message_ids, matched_request_ids = set(), set()
    endpoint_suffixes = Counter()
    records = []
    for event in sorted((e for e in events if e["kind"] == "context.diff"), key=lambda e: e["request_number"]):
        counts["requests"] += 1
        request = get(event["detail_url"])
        suffix = urlsplit(request["exact_request"].get("url", "")).path.rsplit("/", 1)[-1]
        operation = "token_count" if suffix.startswith("count-tokens:") else suffix.split(":")[-1]
        endpoint_suffixes[suffix] += 1
        value = request["exact_request"].get("body", {}).get("decoded", {}).get("value", {})
        messages = value.get("messages", [])
        foo = any(block.get("text") == "foo" for message in messages
                  for block in (message.get("content") if isinstance(message.get("content"), list)
                                else [{"text": message.get("content")}]) if isinstance(block, dict))
        response = responses.get(event["flow_id"])
        mid_scopes, rid_scopes = set(), set()
        status = None
        if response:
            counts["with_context_response"] += 1
            mid_scopes = mids.get(response["response"].get("message_id"), set())
            if mid_scopes:
                matched_message_ids.add(response["response"]["message_id"])
            exact = get(response["detail_url"])["exact_response"]
            status = exact.get("status_code")
            for header, identifier in exact.get("headers", {}).items():
                if "request" in header.lower() and "id" in header.lower():
                    scopes = rids.get(identifier, set())
                    if scopes:
                        matched_request_ids.add(identifier)
                        header_matches[header.lower()] += 1
                        rid_scopes |= scopes
        if mid_scopes: counts["message_id_matches"] += 1
        if rid_scopes: counts["request_id_matches"] += 1
        result = join_scope(mid_scopes, rid_scopes)
        counts[result] += 1
        operations[operation][result] += 1
        if foo: counts["foo_requests"] += 1
        records.append({"request":event["request_number"],"flow":event["flow_id"],
                        "predecessor":request["predecessor_flow_id"],"join":result,
                        "message_id_match":bool(mid_scopes),"request_id_match":bool(rid_scopes),
                        "foo":foo,"messages":len(messages),"response_status":status,"operation":operation})
        records[-1]["purpose"] = (response or request).get("purpose", request.get("request_purpose", {})).get("classification")
    focus = [row for row in records if row["foo"] or row["request"] == 130]
    print(json.dumps({"session":active["session_id"],"transcripts":transcript,
                      "assistant_records":len(rows),"unique_message_ids":len(mids),
                      "unique_request_ids":len(rids),"sidechain_flags":dict(Counter(str(row['sidechain']) for row in rows)),
                      "counts":dict(counts),"matching_headers":dict(header_matches),"operations":dict(operations),
                      "endpoint_suffixes":dict(endpoint_suffixes),
                      "unmatched_transcript_message_ids":len(set(mids)-matched_message_ids),
                      "unmatched_transcript_request_ids":len(set(rids)-matched_request_ids),
                      "unmatched_with_context_response":[r for r in records if r['join']=='unmatched' and r['response_status'] is not None],
                      "unmatched_request_numbers":[r['request'] for r in records if r['join']=='unmatched'],
                      "focus":focus}, indent=2))


if __name__ == "__main__":
    main()
