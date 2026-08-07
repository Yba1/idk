#!/usr/bin/env bash
# Pre-commit ownership tripwire. Installed by each operator as
# .git/hooks/pre-commit. Blocks a commit that stages a path outside the
# current lane's bucket in scripts/ownership.txt. See
# plan-v2/00-SHARED-CONTRACTS.md section 5.
set -euo pipefail
LANE="${NEULIT_LANE:?set NEULIT_LANE to c1, c2a, or c2b}"

bad=0
while IFS= read -r path; do
  [ -z "$path" ] && continue
  allowed=0
  while IFS=' ' read -r lane glob; do
    case "$lane" in ""|\#*) continue ;; esac
    [ "$lane" = "$LANE" ] || continue
    case "$path" in
      $glob) allowed=1 ;;
    esac
  done < scripts/ownership.txt
  if [ "$allowed" -eq 0 ]; then
    echo "OWNERSHIP VIOLATION: $LANE may not edit $path"
    bad=1
  fi
done < <(git diff --cached --name-only)

exit $bad
