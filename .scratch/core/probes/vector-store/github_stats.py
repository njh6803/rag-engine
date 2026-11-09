"""GitHub REST API(gh api, 인증은 gh CLI)로 저장소 채택도 수치를 적는다: stars, forks, 열린 이슈,
생성일, 기여자 수(anon 포함, Link last 페이지), 최근 90일 커밋 수(Link last 페이지, per_page=1),
첫 릴리스 날짜(releases 마지막 페이지), LICENSE 파일의 커밋 이력(날짜·제목).

실행: uv run --no-project python -I -X utf8 .scratch/core/probes/vector-store/github_stats.py \\
    <dl2-dir> <since-ISO>
→ 표준출력에 표, <dl2-dir>/gh_<owner>_<repo>.json 에 원문. gh CLI 가 로그인되어 있어야 한다.

2026-11-09에 since=2026-08-11T00:00:00Z 로 돌려 출력을 같은 폴더의 `github_stats.txt`로 남겼다(비교
문서 N-1 표). 원문 JSON(dl2/)은 옮기지 않았다.
"""

import json
import pathlib
import re
import subprocess
import sys

out = pathlib.Path(sys.argv[1])
since = sys.argv[2]
REPOS = [
    "pgvector/pgvector",
    "pgroonga/pgroonga",
    "paradedb/paradedb",
    "bab2min/Kiwi",
    "bab2min/kiwipiepy",
    "weaviate/weaviate",
    "qdrant/qdrant",
    "milvus-io/milvus",
    "chroma-core/chroma",
    "opensearch-project/OpenSearch",
    "meilisearch/meilisearch",
    "elastic/elasticsearch",
    "groonga/groonga",
]
LICENSE_HISTORY = [
    "bab2min/Kiwi",
    "meilisearch/meilisearch",
    "weaviate/weaviate",
    "paradedb/paradedb",
    "elastic/elasticsearch",
    "tensorchord/pgvecto.rs",
    "tensorchord/VectorChord",
    "qdrant/qdrant",
    "milvus-io/milvus",
    "chroma-core/chroma",
]


def api(path: str, *, include: bool = False):
    cmd = ["gh", "api", path] + (["--include"] if include else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None, r.stderr.strip()[:120]
    if include:
        head, _, body = r.stdout.partition("\n\n")
        if "\r\n\r\n" in r.stdout:
            head, _, body = r.stdout.partition("\r\n\r\n")
        return (head, body), None
    return json.loads(r.stdout), None


def last_page(headers):
    m = re.search(r'[?&]page=(\d+)>; rel="last"', headers)
    return int(m.group(1)) if m else None


print(f"# since={since}")
print(
    "repo\tstars\tforks\topen_issues\tcreated\tcontributors(anon)\tcommits_90d\tfirst_release\tlast_release\tlicense(api)"
)
for repo in REPOS:
    row = {"repo": repo}
    d, err = api(f"repos/{repo}")
    if d is None:
        print(f"{repo}\tERROR {err}")
        continue
    row.update(
        stars=d["stargazers_count"],
        forks=d["forks_count"],
        open_issues=d["open_issues_count"],
        created=d["created_at"][:10],
        license=(d.get("license") or {}).get("spdx_id"),
    )
    h, err = api(f"repos/{repo}/contributors?per_page=1&anon=1", include=True)
    row["contributors"] = last_page(h[0]) if h else f"ERR {err}"
    h, err = api(f"repos/{repo}/commits?since={since}&per_page=1", include=True)
    if h:
        lp = last_page(h[0])
        row["commits_90d"] = lp if lp else (len(json.loads(h[1])) if h[1].strip() else 0)
    else:
        row["commits_90d"] = f"ERR {err}"
    h, err = api(f"repos/{repo}/releases?per_page=1", include=True)
    first = last = None
    if h:
        body = json.loads(h[1]) if h[1].strip() else []
        last = body[0]["published_at"][:10] if body else None
        lp = last_page(h[0])
        if lp:
            d2, _ = api(f"repos/{repo}/releases?per_page=1&page={lp}")
            first = d2[0]["published_at"][:10] if d2 else None
        elif body:
            first = last
    row["first_release"], row["last_release"] = first, last
    (out / f"gh_{repo.replace('/', '_')}.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        "\t".join(
            str(row.get(k))
            for k in [
                "repo",
                "stars",
                "forks",
                "open_issues",
                "created",
                "contributors",
                "commits_90d",
                "first_release",
                "last_release",
                "license",
            ]
        )
    )

print("\n# LICENSE file commit history (date  message)")
for repo in LICENSE_HISTORY:
    d, err = api(f"repos/{repo}/commits?path=LICENSE&per_page=100")
    if d is None:
        print(f"## {repo}: ERROR {err}")
        continue
    (out / f"gh_license_commits_{repo.replace('/', '_')}.json").write_text(
        json.dumps(d, ensure_ascii=False), encoding="utf-8"
    )
    print(f"## {repo} ({len(d)} commits touching LICENSE)")
    for c in d[:12]:
        msg = c["commit"]["message"].splitlines()[0][:90]
        print(f"  {c['commit']['committer']['date'][:10]}  {msg}")
