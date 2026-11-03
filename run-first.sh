#!/bin/sh
# First FRED task. Read-only. No restarts. No orders.
set -eu

sudo -u agent tee /home/agent/inbox/first.md >/dev/null << 'EOF'
First task. The Memory and Corrections sections are already in your prompt.

CryptoBot lives under /home/botuser/AI-Trading-Bot-Suite/CryptoBot. It has been running a long time. The suspicion is a cancel loop: the process still thinks an order is live, the broker already killed or filled it, and the next cycle cancels again. clear_phantom_positions.py is a clue that position state drifted once. It is a clue, not the diagnosis.

Read the code. Read cryptobot.service journal lines. Write a report that names the file, the function, and the condition that decides to cancel. Say what you could not see. If you have a fix, write it with propose_patch and do not apply it.

Do not restart anything. Do not place or cancel an order. Do not read Kalshi. Do not read secrets.

Call remember with one lesson. Then finish. Stop when the report is specific. Do not keep going to use the clock.
EOF

UNIT=agent-$(date +%Y%m%d-%H%M%S)
sudo systemd-run --uid=agent --gid=agent --unit="$UNIT" \
  --property=CPUQuota=25% --property=MemoryMax=512M \
  --working-directory=/home/agent \
  /usr/bin/python3 /home/agent/harness/run.py \
  --hours 1 --budget 4 --turns 30 \
  --task-file /home/agent/inbox/first.md
echo "$UNIT"
