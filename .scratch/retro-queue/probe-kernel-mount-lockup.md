# probe-kernel-mount-lockup: 끊긴 SMB 공유 폴더 여섯 칸을 한 Docker Desktop 가상 기계에서 함께 돌린 프로브가 커널을 17분 넘게 헛돌게 해 Docker 명령 일부가 돌아오지 않았다

**상태:** 열림
**어디로:** `docs/agents/issue-tracker.md` 프로브와 근거 절에 한 줄(커널에 공유 폴더를 붙이는 프로브는 서버가 사라져도 커널이 다시 잇기를 되풀이하는 옵션(SMB의 `hard` 등)의 칸을 다른 칸과 함께 끊지 않고 홀로 돌리며, 다른 세션이 Docker를 쓰는 시간을 피한다)
**승인:** 자체 승인 2026-11-22, 1회차(더하는 것이라 다섯 번째에 반영한다. 잃은 작업이 없고 다른 세션의 Docker 명령이 막혔는지는 보지 못해 손상으로 세지 않았다), 일지 2026-11-21-2139-source-sync-stuck-calls-design.md, ADR 불필요

source-sync의 막힌 호출 설계 세션이 `.scratch/source-sync/probes/stuck-mount/`의 첫 실행에서 SMB 여섯 칸(기본값 셋, `hard` 셋)을 함께 끊어 두었다. 커널의 작업 스레드 하나가 CPU 하나를 17분 37초 쥐었고, 그동안 Docker의 `start`, `network connect`, `unpause`, `inspect`와 공유 폴더 떼기가 돌아오지 않았다(`lockup_seen.txt`). `hard` 칸의 서버로 가는 연결을 살아 있는 서버로 돌리는 규칙을 손으로 넣자 풀렸다. `hard` 칸 탓으로 보는 근거는 시각이 맞은 것 하나다. 그 뒤 CIFS 칸은 나눠 다시 돌렸고 `hard`의 떼기·죽이기 두 칸은 다시 돌리지 않았다.
