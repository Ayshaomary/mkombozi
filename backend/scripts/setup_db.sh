#!/usr/bin/env bash
# Creates the PostgreSQL user and database for MUKOMBOZI, using values from backend/.env
# Run once:  bash backend/scripts/setup_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."

get_env() { grep "^$1=" .env | cut -d= -f2-; }
DB_NAME=$(get_env DB_NAME)
DB_USER=$(get_env DB_USER)
DB_PASSWORD=$(get_env DB_PASSWORD)

# CREATEDB lets Django create a temporary database when running tests
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v db_user="$DB_USER" -v db_pass="$DB_PASSWORD" -v db_name="$DB_NAME" <<'SQL'
CREATE ROLE :"db_user" WITH LOGIN CREATEDB PASSWORD :'db_pass';
CREATE DATABASE :"db_name" OWNER :"db_user";
SQL

echo "Done: database '$DB_NAME' owned by '$DB_USER' is ready."
