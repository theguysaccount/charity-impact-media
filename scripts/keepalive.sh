#!/usr/bin/env bash
# Keep this repository's scheduled workflows running. GitHub disables scheduled workflows in a
# public repository after 60 days without repository activity, so every scheduled workflow
# calls this:
#   1. re-enables the calling workflow through the API (resets its inactivity clock), and
#   2. when the last commit is 45 or more days old, commits a heartbeat file (repository activity).
# Needs permissions: actions: write, contents: write. GH_TOKEN must be set.
set -euo pipefail
workflow="${1:?workflow file name, e.g. refresh.yml}"
repo="${GITHUB_REPOSITORY:?}"
gh api -X PUT "repos/$repo/actions/workflows/$workflow/enable" >/dev/null && echo "keepalive: $workflow enabled"
last=$(git log -1 --format=%ct)
age=$(( ($(date +%s) - last) / 86400 ))
echo "keepalive: last commit $age days ago"
if [ "$age" -ge 45 ]; then
  date -u +%Y-%m-%dT%H:%M:%SZ > .github/heartbeat
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add .github/heartbeat
  git commit -m "Heartbeat: keep scheduled workflows enabled [skip ci]"
  git push
  echo "keepalive: heartbeat committed"
fi
