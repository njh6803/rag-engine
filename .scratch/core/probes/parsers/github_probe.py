"""GitHub REST API로 저장소의 라이선스(감지된 SPDX + LICENSE 파일 머리), 마지막 push, 마지막 커밋
날짜, archived 여부, 별 수를 받는다. 토큰은 환경변수 GITHUB_TOKEN(있으면).

사용: uv run python -I .scratch/core/probes/parsers/github_probe.py <out_json> owner/repo ...
(저장소 루트에서. 표준 라이브러리만 쓴다. GitHub API 를 부른다.)

2026-11-09에 파서 후보 저장소로 두 번 돌렸다. 출력은 같은 폴더의 `out/github_probe.json`과
`out/github_probe2.json`(저장소 목록은 그 파일의 키). 수치는 그날의 스냅숏이다.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

out = Path(sys.argv[1])
repos = sys.argv[2:]
token = os.environ.get("GITHUB_TOKEN")


def get(url):
    headers = {"User-Agent": "rag-engine-probe/0.1", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, repr(e)


results = {}
for repo in repos:
    rec = {"repo": repo}
    meta, err = get(f"https://api.github.com/repos/{repo}")
    if meta is None:
        rec["error"] = err
        results[repo] = rec
        print(repo, "ERROR", err, flush=True)
        continue
    rec["pushed_at"] = meta.get("pushed_at")
    rec["archived"] = meta.get("archived")
    rec["stars"] = meta.get("stargazers_count")
    rec["default_branch"] = meta.get("default_branch")
    rec["description"] = meta.get("description")
    rec["language"] = meta.get("language")
    lic = meta.get("license") or {}
    rec["license_spdx_detected"] = lic.get("spdx_id")
    lic_doc, err2 = get(f"https://api.github.com/repos/{repo}/license")
    if lic_doc:
        rec["license_path"] = lic_doc.get("path")
        rec["license_html_url"] = lic_doc.get("html_url")
        rec["license_download_url"] = lic_doc.get("download_url")
        content = base64.b64decode(lic_doc.get("content", "")).decode("utf-8", "replace")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        rec["license_head"] = lines[:8]
        rec["license_chars"] = len(content)
    else:
        rec["license_error"] = err2
    commits, err3 = get(f"https://api.github.com/repos/{repo}/commits?per_page=1")
    if commits:
        c = commits[0]
        rec["last_commit_date"] = c["commit"]["committer"]["date"]
        rec["last_commit_sha"] = c["sha"][:10]
        rec["last_commit_msg"] = c["commit"]["message"].splitlines()[0][:100]
    else:
        rec["commit_error"] = err3
    results[repo] = rec
    print(
        repo,
        "| spdx:",
        rec["license_spdx_detected"],
        "| pushed:",
        rec["pushed_at"],
        "| last commit:",
        rec.get("last_commit_date"),
        "| archived:",
        rec["archived"],
        "| stars:",
        rec["stars"],
        flush=True,
    )

out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("written", out)
