#!/usr/bin/env bash
# Oracle Always Free ARM VM(Ubuntu 22.04/24.04) 처음 설치(2026-10-17).
# 사용: VM에 SSH로 들어가서
#   curl -fsSL https://raw.githubusercontent.com/bat1120/maple-optimizer/main/deploy/setup-vm.sh -o setup-vm.sh
#   bash setup-vm.sh
# 하는 일: Docker·compose 설치(Ubuntu 저장소), 80·443 열기(Oracle Ubuntu 이미지는 iptables가 막아 둔다),
#         저장소 내려받기, .env 틀 만들기(권한 600). 키 값은 넣지 않는다 — 직접 채운다.
set -euo pipefail
# 패키지 설치 중 질문 창(iptables-persistent의 "규칙 저장?" 등)이 뜨면 멈추므로 묻지 않게 한다
export DEBIAN_FRONTEND=noninteractive
echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections
echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections

REPO="https://github.com/bat1120/maple-optimizer.git"
DIR="$HOME/maple-optimizer"

echo "== 1/4 Docker 설치"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io git
if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-v2 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-compose-plugin
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "== 2/4 방화벽 80·443 열기(VM 안 iptables — Oracle 콘솔의 Security List도 따로 열어야 한다)"
for port in 80 443; do
  if ! sudo iptables -C INPUT -m state --state NEW -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    # 막는 규칙(REJECT) 바로 앞에 넣는다 — 없으면 맨 뒤에
    pos=$(sudo iptables -L INPUT --line-numbers | awk '/REJECT/{print $1; exit}')
    if [ -n "$pos" ]; then
      sudo iptables -I INPUT "$pos" -m state --state NEW -p tcp --dport "$port" -j ACCEPT
    else
      sudo iptables -A INPUT -m state --state NEW -p tcp --dport "$port" -j ACCEPT
    fi
  fi
done
if command -v netfilter-persistent >/dev/null; then
  sudo netfilter-persistent save
else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent && sudo netfilter-persistent save
fi

echo "== 3/4 저장소"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi

echo "== 4/4 .env 틀"
if [ ! -f "$DIR/.env" ]; then
  umask 077
  cat > "$DIR/.env" <<'ENV'
# 값을 채운 뒤 저장한다. 이 파일은 GitHub에 올리지 않는다(.gitignore).
NEXON_API_KEY=
OPENAI_API_KEY=
ADMIN_PASSWORD_HASH=
SESSION_SECRET=
DATABASE_URL=
AGENT_DAILY_TOKEN_BUDGET=200000
AGENT_PUBLIC_DAILY=5
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=
ENV
  echo ".env 틀을 만들었다: $DIR/.env (권한 600) — 값을 채워 주세요"
else
  echo ".env가 이미 있다 — 그대로 둔다"
fi

IP=$(curl -4 -fsS https://ifconfig.me || true)  # IPv4로 — 듀얼스택이면 IPv6가 나와 sslip 주소가 틀렸다(2026-10-17 Lightsail)
cat <<DONE

설치 끝. 다음 순서:
  1) 로그아웃했다가 다시 SSH로 들어온다(docker 그룹 적용)
  2) nano $DIR/.env 로 키를 채운다(Render 환경 변수와 같은 값)
  3) 도메인이 없으면 IP로 만든 주소를 쓴다: ${IP:+${IP//./-}.sslip.io}
     cd $DIR && DOMAIN=<도메인> docker compose up -d --build
  4) 브라우저에서 https://<도메인> 이 열리면 성공
DONE
