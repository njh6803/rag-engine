#!/bin/sh
# NFS 서버 컨테이너의 주 프로세스다. `probe.sh` 가 특권 `alpine:3.22` 컨테이너에 복사해
# `sh /server.sh` 로 띄운다. Alpine 공식 저장소의 nfs-utils 를 깔고 커널의 NFS 서버(nfsd)를 NFSv4 만
# 받게 켠다. 커널 모듈 nfsd 는 `mount -t nfsd` 가 스스로 올린다(따로 modprobe 하지 않는다).
#
# 내보내는 폴더 `/export` 는 Docker 볼륨이다. 컨테이너의 겹침 파일 시스템(overlay)은 NFS 로 내보낼 수
# 없고, 볼륨이면 컨테이너를 죽였다가 `docker start` 로 다시 띄워도 파일 핸들이 그대로다(디스크가 있는
# 서버가 다시 켜진 것과 같다).
#
# 커널의 NFS 서버는 커널 스레드라서 `docker pause` 로 얼지 않는다. 그래서 NFS 칸은 서버를 네트워크에서
# 떼거나(disconnect) 죽여서(kill) 끊는다.
#
# 내용은 `server_smb.sh` 와 같다(warm/ok.txt, big1.bin, big2.bin, t001 ~ t250).
set -eu

if ! command -v exportfs >/dev/null 2>&1; then
    apk add --no-cache nfs-utils >/dev/null
fi

if [ ! -f /export/.ready ]; then
    mkdir -p /export/warm
    echo ok > /export/warm/ok.txt
    dd if=/dev/urandom of=/export/big1.bin bs=1024k count=8 2>/dev/null
    dd if=/dev/urandom of=/export/big2.bin bs=1024k count=8 2>/dev/null
    dd if=/dev/urandom of=/tmp/seed bs=1k count=64 2>/dev/null
    i=1
    while [ "$i" -le 250 ]; do
        d=$(printf '/export/t%03d' "$i")
        mkdir -p "$d/sub"
        cp /tmp/seed "$d/a.txt"
        echo b > "$d/b.txt"
        echo x > "$d/sub/x.txt"
        echo y > "$d/sub/y.txt"
        echo z > "$d/sub/z.txt"
        i=$((i + 1))
    done
    rm -f /tmp/seed
    : > /export/.ready
fi

stop() {
    # 커널 스레드를 내리고 끝난다. `docker stop` 이 보내는 SIGTERM 에서 돈다.
    rpc.nfsd 0
    exportfs -ua
    exit 0
}
trap stop TERM INT

mkdir -p /var/lib/nfs/rpc_pipefs /var/lib/nfs/v4recovery /var/lib/nfs/nfsdcld
if ! grep -q ' /proc/fs/nfsd ' /proc/mounts; then
    mount -t nfsd nfsd /proc/fs/nfsd
fi
if ! grep -q ' /var/lib/nfs/rpc_pipefs ' /proc/mounts; then
    mount -t rpc_pipefs rpc_pipefs /var/lib/nfs/rpc_pipefs
fi
# fsid=0 은 이 폴더를 NFSv4 의 뿌리로 내보낸다. 클라이언트는 `<서버>:/` 를 붙인다. 컨테이너의 `/` 는
# 내보낼 수 없는 파일 시스템이라, 뿌리를 따로 두지 않으면 `<서버>:/export` 를 찾지 못한다.
echo '/export *(ro,fsid=0,no_subtree_check,no_root_squash,insecure)' > /etc/exports
exportfs -ra
# nfsdcld 는 서버가 다시 켜졌을 때 되찾을 클라이언트를 적어 두는 데몬이다. 없으면 커널이 켤 때마다
# 유예 90초를 통째로 기다린다. 커널은 nfsd 를 켤 때 이 데몬을 1초만 기다리므로, 데몬이 자리를 잡을
# 틈을 준다(틈 없이 켰더니 커널이 데몬을 찾지 못했다).
if command -v nfsdcld >/dev/null 2>&1; then
    nfsdcld
    sleep 1
fi
rpc.mountd -N 2 -N 3
rpc.nfsd -N 3 -V 4 8
echo "nfsd 스레드 수: $(cat /proc/fs/nfsd/threads), 버전: $(cat /proc/fs/nfsd/versions)"

while :; do
    sleep 1
done
