#!/bin/sh
# Interactive. Run on the droplet. Do not put the key in git.
set -eu

sudo -u agent bash -c 'umask 077; printf "paste key then enter: "; IFS= read -rs KEY; printf "%s" "$KEY" > /home/agent/.secrets/xai_api_key; echo; echo saved'
sudo chmod 600 /home/agent/.secrets/xai_api_key
sudo -u agent python3 /home/agent/harness/run.py --check
