#!/bin/sh
# FRED droplet home. Same director. Not the trading checkout.
set -eu

id agent >/dev/null 2>&1 || sudo useradd --system --create-home --home-dir /home/agent --shell /usr/sbin/nologin agent
sudo -u agent mkdir -p /home/agent/harness /home/agent/inbox /home/agent/work/tasks /home/agent/work/memory /home/agent/work/skills /home/agent/.secrets
sudo chmod 700 /home/agent /home/agent/.secrets
sudo -u agent tee /home/agent/work/memory/INDEX.md >/dev/null << 'EOF'
# Memory
Lessons from finished tasks. Newest at the bottom.
EOF
sudo -u agent tee /home/agent/work/memory/corrections.md >/dev/null << 'EOF'
# Corrections
Human corrections. The next task sees this. Be specific.
EOF
sudo -u agent tee /home/agent/work/skills/README.md >/dev/null << 'EOF'
# Skills
Empty until a human copies a procedure here after it actually worked.
EOF

sudo apt-get install -y acl
sudo setfacl -R -m u:agent:rX /home/botuser/AI-Trading-Bot-Suite
sudo setfacl -R -d -m u:agent:rX /home/botuser/AI-Trading-Bot-Suite
sudo find /home/botuser/AI-Trading-Bot-Suite \( -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa' \) -exec setfacl -m u:agent:--- {} \;
sudo usermod -aG systemd-journal agent
