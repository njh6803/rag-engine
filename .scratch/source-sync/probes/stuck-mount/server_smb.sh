#!/bin/sh
# SMB 서버 컨테이너의 주 프로세스다. `probe.sh` 가 `alpine:3.22` 컨테이너에 복사해 `sh /server.sh` 로
# 띄운다. Alpine 공식 저장소의 samba 를 깔고, 한 번도 읽지 않은 대상으로 쓸 폴더와 파일을 만든 뒤
# smbd 를 앞에서 돌린다. 컨테이너를 죽였다가 `docker start` 로 다시 띄워도 같은 내용으로 뜬다(패키지와
# 파일은 컨테이너의 파일 시스템에 남는다).
#
# 공유 이름은 `share`, 읽기 전용, 손님 접속이다(비밀번호를 스크립트에 적지 않으려는 것이다).
# 내용은 다음과 같다(`server_nfs.sh` 와 같다).
# - warm/ok.txt: 붙인 직후에 읽어 마운트가 사는지 보는 파일.
# - big1.bin, big2.bin(8MiB): 서버가 살아 있을 때 열어 두고 끊긴 뒤에 읽는 파일.
# - t001 ~ t250: 폴더마다 a.txt(64KiB), b.txt, sub/ 아래 파일 셋. 측정마다 새 번호를 쓴다.
set -eu

if ! command -v smbd >/dev/null 2>&1; then
    apk add --no-cache samba >/dev/null
fi

if [ ! -f /share/.ready ]; then
    mkdir -p /share/warm
    echo ok > /share/warm/ok.txt
    dd if=/dev/urandom of=/share/big1.bin bs=1024k count=8 2>/dev/null
    dd if=/dev/urandom of=/share/big2.bin bs=1024k count=8 2>/dev/null
    dd if=/dev/urandom of=/tmp/seed bs=1k count=64 2>/dev/null
    i=1
    while [ "$i" -le 250 ]; do
        d=$(printf '/share/t%03d' "$i")
        mkdir -p "$d/sub"
        cp /tmp/seed "$d/a.txt"
        echo b > "$d/b.txt"
        echo x > "$d/sub/x.txt"
        echo y > "$d/sub/y.txt"
        echo z > "$d/sub/z.txt"
        i=$((i + 1))
    done
    rm -f /tmp/seed
    : > /share/.ready
fi

cat > /etc/samba/smb.conf <<'EOF'
[global]
    server role = standalone server
    map to guest = Bad User
    guest account = nobody
    disable netbios = yes
    smb ports = 445
    load printers = no
    printing = bsd
    printcap name = /dev/null
    disable spoolss = yes
    log level = 1

[share]
    path = /share
    read only = yes
    guest ok = yes
EOF

exec smbd --foreground --no-process-group --debug-stdout
