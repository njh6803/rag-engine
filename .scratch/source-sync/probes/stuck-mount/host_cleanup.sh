#!/bin/sh
# "서버 기계" 안에 남은 것을 치운다. `probe.sh` 가 끝에서 `sh /probe/host_cleanup.sh` 로 부른다.
# 칸이 제대로 끝났으면 치울 것이 없다. 칸이 도중에 죽었을 때를 위한 것이다. `probe.sh` 가 서버를 먼저
# 다시 답하게 한 뒤에 부른다. 안쪽 컨테이너를 지우고, 남은 CIFS 와 NFS 마운트를 뗀다.
set -u

left=$(docker ps -aq)
if [ -n "$left" ]; then
    echo "  서버 기계 안에 남은 컨테이너 $(echo "$left" | wc -l)개를 지운다"
    # shellcheck disable=SC2086
    docker rm -f $left >/dev/null 2>&1
fi
awk '$3 == "cifs" || $3 == "nfs" || $3 == "nfs4" { print $2 }' /proc/mounts > /tmp/left_mounts
while read -r mounted; do
    echo "  서버 기계 안에 남은 마운트를 뗀다: $mounted"
    umount "$mounted" 2>/dev/null || umount -f "$mounted" 2>/dev/null || umount -l "$mounted"
done < /tmp/left_mounts
echo "  서버 기계 안에 남은 컨테이너 $(docker ps -aq | wc -l)개," \
    "남은 CIFS·NFS 마운트 $(awk '$3 == "cifs" || $3 == "nfs" || $3 == "nfs4"' /proc/mounts | wc -l)개"
