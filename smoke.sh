#!/bin/sh
# Transient smoke run. Not a standing service. Not the trading bots.
set -eu

sudo systemd-run --uid=agent --gid=agent --unit=agent-smoke --collect --wait \
  --property=CPUQuota=25% --property=MemoryMax=512M \
  --working-directory=/home/agent \
  /usr/bin/python3 /home/agent/harness/run.py --smoke
sudo cat /home/agent/work/latest/report.md
