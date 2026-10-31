#!/usr/bin/env bash
# Copies all data from the Render database to a new, empty Neon database, then checks
# that every table has the same number of rows in both. The Render database is only read.
#
#   bash backend/scripts/copy_db_to_neon.sh
#
# It asks for the two database addresses (hidden while you paste them, so they don't stay on screen):
#   Render: dashboard.render.com > mukombozi-db > Connect > External > "External Database URL"
#   Neon:   console.neon.tech > your project > Connect > untick "Connection pooling" > copy the URL
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

# Never write over data: the Neon database must still be empty
existing=$(psql "$NEW_URL" -tAc "select count(*) from pg_tables where schemaname = 'public'")
if [ "$existing" -ne 0 ]; then
  echo "The Neon database already has $existing tables. Nothing was copied."
  echo "Use a new, empty Neon database (or ask for help if you copied before)."
  exit 1
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
tables=$(psql "$OLD_URL" -tAc "select tablename from pg_tables where schemaname = 'public' order by tablename")
problems=0
total=0
for table in $tables; do
  old=$(psql "$OLD_URL" -tAc "select count(*) from public.\"$table\"")
  new=$(psql "$NEW_URL" -tAc "select count(*) from public.\"$table\"")
  total=$((total + old))
  if [ "$old" != "$new" ]; then
    echo "  DIFFERENT: $table has $old rows on Render but $new on Neon"
    problems=$((problems + 1))
  fi
done

if [ "$problems" -ne 0 ]; then
  echo "Something went wrong: $problems tables differ. Don't switch to Neon yet."
  exit 1
fi
echo "Done: $(echo "$tables" | wc -w) tables and $total rows copied, and they all match."
echo "Next: put the Neon URL in Render > mukombozi-api > Environment > DATABASE_URL."
