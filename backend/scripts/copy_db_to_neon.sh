#!/usr/bin/env bash
# Copies all data from the Render database to a new, empty Neon database, then checks
# that every table has the same number of rows in both. The Render database is only read.
#
#   bash backend/scripts/copy_db_to_neon.sh
#
# It asks for the two database addresses (hidden while you paste them, so they don't stay on screen):
#   Render: dashboard.render.com > mukombozi-db > Connect > External > "External Database URL"
#   Neon:   console.neon.tech > your project > Connect > untick "Connection pooling" > copy the URL
#
# If Neon already has tables, it checks whether the copy was already done, and if Neon only has
# empty tables (made when Render started the app on Neon), it offers to clear them first.
set -o errexit -o nounset -o pipefail

read -rsp "Paste the Render External Database URL, then press Enter: " OLD_URL
echo
read -rsp "Paste the Neon connection URL, then press Enter: " NEW_URL
echo

for url in "$OLD_URL" "$NEW_URL"; do
  if [[ "$url" != postgres://* && "$url" != postgresql://* ]]; then
    echo "That doesn't look like a database URL (it should start with postgresql://). Nothing was copied."
    exit 1
  fi
done

echo "Checking both databases can be reached..."
psql "$OLD_URL" -tAc 'select 1' >/dev/null
psql "$NEW_URL" -tAc 'select 1' >/dev/null

# The same database pasted twice would look "already copied"
where() { psql "$1" -tAc "select current_database() || ' on ' || coalesce(inet_server_addr()::text, 'local') || ':' || current_setting('port')"; }
if [ "$(where "$OLD_URL")" = "$(where "$NEW_URL")" ]; then
  echo "Both URLs point to the same database. Paste the Render URL first, then the Neon URL. Nothing was copied."
  exit 1
fi

tables_in() { psql "$1" -tAc "select tablename from pg_tables where schemaname = 'public' order by tablename"; }
count() { psql "$1" -tAc "select count(*) from public.\"$2\"" 2>/dev/null || echo "missing"; }

# Prints each table whose row count differs, and fails if any does
compare() {
  local differ=0 table old new
  for table in $(tables_in "$OLD_URL"); do
    old=$(count "$OLD_URL" "$table")
    new=$(count "$NEW_URL" "$table")
    if [ "$old" != "$new" ]; then
      [ "${1:-}" = quiet ] || echo "  DIFFERENT: $table has $old rows on Render but $new on Neon"
      differ=$((differ + 1))
    fi
  done
  [ "$differ" -eq 0 ]
}

summary() {
  echo "  shops: $(count "$1" accounts_business), users: $(count "$1" accounts_user)," \
    "products: $(count "$1" inventory_product), sales: $(count "$1" sales_sale)"
}

existing=$(tables_in "$NEW_URL" | wc -w)
if [ "$existing" -ne 0 ]; then
  if compare quiet; then
    echo "The copy was already done: every table on Neon matches Render."
    summary "$NEW_URL"
    echo "Next: put the Neon URL in Render > mukombozi-api > Environment > DATABASE_URL."
    exit 0
  fi

  echo "The Neon database already has $existing tables, but they don't match Render."
  echo "Render:"
  summary "$OLD_URL"
  echo "Neon:"
  summary "$NEW_URL"

  # Real shops on Neon (e.g. someone registered after Render switched to it) must never be cleared here
  if [ "$(count "$NEW_URL" accounts_business)" != 0 ]; then
    echo "Neon already has shops in it, so it was NOT cleared and nothing was copied. Ask for help."
    exit 1
  fi

  echo
  echo "Neon has no shops: its tables are empty, probably made when Render started the app on Neon."
  echo "They can be cleared, and then everything is copied from Render. Render is not changed."
  read -rp "Type CLEAR (in capitals) to clear Neon and copy, or just press Enter to stop: " answer
  if [ "$answer" != CLEAR ]; then
    echo "Stopped. Nothing was changed."
    exit 1
  fi
  echo "Clearing the empty Neon tables..."
  psql "$NEW_URL" -q -v ON_ERROR_STOP=1 -c 'set client_min_messages = warning' \
    -c 'drop schema public cascade' -c 'create schema public'
fi

# The copy holds your customers' data: keep it private and delete it at the end
workdir=$(mktemp -d)
chmod 700 "$workdir"
trap 'rm -rf "$workdir"' EXIT

echo "Copying from Render (this can take a minute)..."
pg_dump --format=custom --no-owner --no-privileges --file="$workdir/mukombozi.dump" "$OLD_URL"

echo "Saving into Neon..."
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$NEW_URL" "$workdir/mukombozi.dump"

echo "Checking every table..."
if ! compare; then
  echo "Something went wrong: some tables differ. Don't switch to Neon yet."
  exit 1
fi
echo "Done: $(tables_in "$OLD_URL" | wc -w) tables copied, and they all match."
summary "$NEW_URL"
echo "Next: put the Neon URL in Render > mukombozi-api > Environment > DATABASE_URL."
