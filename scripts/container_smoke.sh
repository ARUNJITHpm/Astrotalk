#!/usr/bin/env bash
# Boot the built image and check the operator console end to end.
#
#   docker build -t nithara:local .        # never pipe this into a pager:
#   bash scripts/container_smoke.sh        # the exit code would come from it
#
# Runs against a SCRATCH SQLite database inside the container, never Neon.
# .dockerignore excludes .env, so the container carries no credentials of its
# own and sees only what -e passes in — that is what makes this safe to run
# against a machine whose .env points at production.
#
# The four phases build to the question that actually matters at deploy time:
# what does the console do when ADMIN_TOKEN is missing? Since the `chargemod`
# fallback was removed in console plan Part 4 that is the live Space's state,
# and getting it wrong either locks the owner out or leaves a hole open.
#
#   1. token set          — every console route answers
#   2. nothing configured — every console route 401s, app still serves
#   3. password but no token — the owner gets a diagnostic, still no token
#   4. fully configured   — the owner signs in and the token works
#
# Phase 3 is the subtle one. Credentials are checked BEFORE the config state
# (app/modules/admin/router.py), so an anonymous prober sees a plain 401 and
# learns nothing about the deployment, while the owner who proves who they are
# gets told exactly which variable is missing.

set -u
export PATH="/c/Users/arunj/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"

NAME=nithara-test
TOKEN=test-admin-token-9f3c
PORT=3999
pass=0; fail=0

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then
    echo "  PASS  $1"
    pass=$((pass+1))
  else
    echo "  FAIL  $1 — expected [$2] got [$3]"
    fail=$((fail+1))
  fi
}

code() { # code <path> [header...]
  curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT$1" "${@:2}"
}

body() { curl -s "http://localhost:$PORT$1" "${@:2}"; }

# One response header, lowercased, so a check reads the same on any curl build.
header() { # header <path> <header-name>
  curl -s -D - -o /dev/null "http://localhost:$PORT$1" \
    | tr -d '\r' | grep -i "^$2:" | cut -d' ' -f2- | tr 'A-Z' 'a-z'
}

start() { # start <extra env flags...>
  cleanup
  docker run -d --name "$NAME" -p "$PORT:3000" \
    -e "DATABASE_URL=sqlite+aiosqlite:////tmp/nithara.db" \
    -e "APP_ENV=test" \
    "$@" nithara:local >/dev/null
  for _ in $(seq 1 60); do
    if [ "$(code /health)" = "200" ]; then return 0; fi
    sleep 2
  done
  echo "  container never became healthy; last 40 log lines:"
  docker logs "$NAME" 2>&1 | tail -40
  return 1
}

echo "=== 1. boot with ADMIN_TOKEN set ==="
if ! start -e "ADMIN_TOKEN=$TOKEN"; then exit 1; fi
echo "  container healthy"

echo
echo "--- migrations ran at boot (Dockerfile entrypoint) ---"
docker logs "$NAME" 2>&1 | grep -iE "alembic|running upgrade|directory loaded|feed" | tail -12

AUTH=(-H "X-Admin-Token: $TOKEN")

echo
echo "--- public surfaces ---"
check "GET /health"                200 "$(code /health)"
check "GET / serves the SPA"       200 "$(code /)"
check "GET /prototype"             200 "$(code /prototype)"
check "SPA and prototype differ"   "different" \
  "$( [ "$(body / | md5sum)" = "$(body /prototype | md5sum)" ] && echo same || echo different )"
check "GET /feed → 3 seeded cards" 3   "$(body /feed | grep -o '"id"' | wc -l | tr -d ' ')"
check "GET /temples → 53"          53  "$(body '/temples?limit=200' | grep -o '"id"' | wc -l | tr -d ' ')"
check "GET /astrologers → 28"      28  "$(body /astrologers | grep -o '"id":' | wc -l | tr -d ' ')"

echo
echo "--- the React operator console at /console-app (Part 9) ---"
check "GET /console-app"              200 "$(code /console-app)"
check "trailing slash"                200 "$(code /console-app/)"
# react-router owns everything under the prefix: a bookmarked section is the
# normal way an operator returns to work, so a deep link must reach the shell.
check "deep link /console-app/people/users" 200 "$(code /console-app/people/users)"
check "deep link /console-app/bookings"     200 "$(code /console-app/bookings)"
check "the shell is the console, not the PWA" "yes" \
  "$(body /console-app | grep -qi 'Nithara Console' && echo yes || echo no)"
check "console and consumer app are different pages" "different" \
  "$( [ "$(body / | md5sum)" = "$(body /console-app | md5sum)" ] && echo same || echo different )"
# Exact-matching "/console-app" would leave deep links cacheable — how an
# operator ends up on yesterday's build after a deploy.
check "shell is no-store"             "no-store" "$(header /console-app 'cache-control')"
check "deep link is no-store too"     "no-store" \
  "$(header /console-app/bookings/payments 'cache-control')"
# Vite content-hashes these, and they live under the console's own base — the
# consumer app's bare /assets/ prefix would miss them entirely.
CONSOLE_JS=$(body /console-app | grep -oE '/console-app/assets/[^"]+\.js' | head -1)
check "shell references a hashed bundle" "yes" \
  "$( [ -n "$CONSOLE_JS" ] && echo yes || echo no )"
check "that bundle is served"         200 "$(code "$CONSOLE_JS")"
check "and cached immutably"          "yes" \
  "$(header "$CONSOLE_JS" 'cache-control' | grep -q immutable && echo yes || echo no)"
# The mount is scoped to a subpath precisely so a catch-all cannot turn a
# typo'd API call into an HTML 200.
check "the console did not swallow the API" "no" \
  "$(curl -s -D - -o /dev/null "http://localhost:$PORT/admin/users" \
      | grep -qi 'content-type: text/html' && echo yes || echo no)"
check "the old /console still works"  200 "$(code /console)"

echo
echo "--- console routes WITH the token ---"
check "GET /admin/users"           200 "$(code /admin/users "${AUTH[@]}")"
check "GET /admin/payments"        200 "$(code /admin/payments "${AUTH[@]}")"
check "GET /bookings/queue"        200 "$(code /bookings/queue "${AUTH[@]}")"
check "GET /bookings/queue/worklist" 200 "$(code /bookings/queue/worklist "${AUTH[@]}")"
check "GET /temples/manage"        200 "$(code /temples/manage "${AUTH[@]}")"
check "GET /temples/poojas"        200 "$(code /temples/poojas "${AUTH[@]}")"
check "GET /astrologers/manage"    200 "$(code /astrologers/manage "${AUTH[@]}")"
check "GET /content/feed/manage"   200 "$(code /content/feed/manage "${AUTH[@]}")"
check "GET /admin/operators"       200 "$(code /admin/operators "${AUTH[@]}")"
# The console's first call after sign-in. An X-Admin-Token caller is a
# credential rather than a row, so it is an owner with a null operator_id.
check "GET /admin/operators/me"    200 "$(code /admin/operators/me "${AUTH[@]}")"
check "…reports owner"             "yes" \
  "$(body /admin/operators/me "${AUTH[@]}" | grep -q '"is_owner":true' && echo yes || echo no)"
check "GET /admin/overview"        200 "$(code /admin/overview "${AUTH[@]}")"
check "/temples/manage → 53 rows"  53 \
  "$(body /temples/manage "${AUTH[@]}" | grep -o '"reviewed"' | wc -l | tr -d ' ')"

echo
echo "--- console routes WITHOUT a token ---"
check "GET /admin/users"           401 "$(code /admin/users)"
check "GET /bookings/queue"        401 "$(code /bookings/queue)"
check "GET /temples/manage"        401 "$(code /temples/manage)"
check "GET /astrologers/manage"    401 "$(code /astrologers/manage)"
check "GET /content/feed/manage"   401 "$(code /content/feed/manage)"
check "GET /admin/operators/me"    401 "$(code /admin/operators/me)"

echo
echo "--- a WRONG token is refused ---"
check "GET /admin/users"  401 "$(code /admin/users -H 'X-Admin-Token: chargemod')"
check "POST /admin/login (legacy pair)" 401 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://localhost:$PORT/admin/login" \
      -H 'Content-Type: application/json' -d '{"username":"admin","password":"chargemod"}')"

echo
echo "=== 2. reboot with NO ADMIN_TOKEN (the live Space's current state) ==="
if ! start; then exit 1; fi
echo "  container healthy"
check "GET /health still fine"     200 "$(code /health)"
check "GET / still fine"           200 "$(code /)"
# Locked, not bricked: the console must still LOAD so an operator can read the
# sign-in error, rather than 404ing and looking like a broken deploy.
check "the console still loads"    200 "$(code /console-app)"
check "an empty token authenticates nobody" 401 "$(code /admin/users -H 'X-Admin-Token: ')"
check "no token → 401"             401 "$(code /admin/users)"
check "old backdoor → 401"         401 "$(code /admin/users -H 'X-Admin-Token: chargemod')"
# Credentials are checked BEFORE the config state, so an anonymous prober
# cannot learn whether this deployment is configured — it just looks like a
# wrong password.
check "unknown caller → 401, not a config hint" 401 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://localhost:$PORT/admin/login" \
      -H 'Content-Type: application/json' \
      -d '{"username":"arunjith@nithara.app","password":"whatever"}')"

echo
echo "=== 3. owner password set, ADMIN_TOKEN still missing (the real lockout) ==="
if ! start -e "ADMIN_EMAIL=owner@nithara.app" -e "ADMIN_PASSWORD=correct-horse-battery"; then exit 1; fi
LOGIN='http://localhost:'$PORT'/admin/login'
check "wrong password still 401" 401 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$LOGIN" -H 'Content-Type: application/json' \
      -d '{"username":"owner@nithara.app","password":"wrong"}')"
# Only once the owner has proved who they are do they get the actionable
# message — and still no token, because there is none to hand out.
check "right password → 503 with a diagnostic" 503 \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$LOGIN" -H 'Content-Type: application/json' \
      -d '{"username":"owner@nithara.app","password":"correct-horse-battery"}')"
check "503 body names ADMIN_TOKEN" "yes" \
  "$(curl -s -X POST "$LOGIN" -H 'Content-Type: application/json' \
      -d '{"username":"owner@nithara.app","password":"correct-horse-battery"}' \
      | grep -q 'ADMIN_TOKEN is not configured' && echo yes || echo no)"
check "and hands out no token" "no token" \
  "$(curl -s -X POST "$LOGIN" -H 'Content-Type: application/json' \
      -d '{"username":"owner@nithara.app","password":"correct-horse-battery"}' \
      | grep -q '"token"' && echo "LEAKED A TOKEN" || echo "no token")"

echo
echo "=== 4. fully configured: the owner can actually sign in ==="
if ! start -e "ADMIN_EMAIL=owner@nithara.app" -e "ADMIN_PASSWORD=correct-horse-battery" \
           -e "ADMIN_TOKEN=$TOKEN"; then exit 1; fi
OWNER_TOKEN=$(curl -s -X POST "http://localhost:$PORT/admin/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"owner@nithara.app","password":"correct-horse-battery"}' \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
check "login returns a token"   "$TOKEN" "$OWNER_TOKEN"
check "that token opens /admin/users" 200 \
  "$(code /admin/users -H "X-Admin-Token: $OWNER_TOKEN")"
check "and the booking queue"   200 "$(code /bookings/queue -H "X-Admin-Token: $OWNER_TOKEN")"

echo
echo "================================"
echo "passed: $pass   failed: $fail"
[ "$fail" -eq 0 ]
