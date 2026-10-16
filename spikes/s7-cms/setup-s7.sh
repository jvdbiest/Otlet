#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S7 on the measurement machine, after spikes/s3-document/cms/setup.sh: adds W3 (WordPress
# with Wordfence) and the Author and Editor accounts used by V3. Credentials are appended to
# ~/otlet-cms.env (mode 600). Idempotent. Run from spikes/s7-cms.
set -eu

env_file="$HOME/otlet-cms.env"
set -a; . "$env_file"; set +a
secret() { head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
add() { grep -q "^$1=" "$env_file" || echo "$1=$2" >> "$env_file"; }

sudo docker exec otlet-cms-mariadb-1 mariadb -uroot -p"$CMS_DB_PASSWORD" -e \
    "CREATE DATABASE IF NOT EXISTS wp_secured CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
sudo -E docker compose -f compose.yaml up -d

wp() { # project volume, database, url, args…
    volume=$1; database=$2; url=$3; shift 3
    sudo docker run --rm --network otlet-cms_default -v "$volume:/var/www/html" \
        -e WORDPRESS_DB_HOST=mariadb -e WORDPRESS_DB_USER=root \
        -e WORDPRESS_DB_PASSWORD="$CMS_DB_PASSWORD" -e WORDPRESS_DB_NAME="$database" \
        --user 33:33 wordpress:cli-php8.4 wp --url="$url" "$@"
}
secured() { wp otlet-s7_wp_secured wp_secured http://wordpress-secured "$@"; }
current() { wp otlet-cms_wp_current wp_current http://wordpress "$@"; }

if ! grep -q '^WP_SECURED_APP_PASSWORD=' "$env_file"; then
    for _ in $(seq 1 60); do secured core version >/dev/null 2>&1 && break; sleep 2; done
    secured config set WP_ENVIRONMENT_TYPE local >/dev/null
    secured core install --title=S7 --admin_user=admin --admin_password="$WP_ADMIN_PASSWORD" \
        --admin_email=s7@example.org --skip-email >/dev/null
    secured plugin install wordfence --activate >/dev/null
    add WP_SECURED_APP_PASSWORD "$(secured user application-password create admin otlet-s7 --porcelain)"
fi
echo "W3: WordPress $(secured core version), Wordfence $(secured plugin get wordfence --field=version)"

# V3: an Author and an Editor on W1, each with an application password.
for role in author editor; do
    variable=$(echo "WP_${role}_APP_PASSWORD" | tr 'a-z' 'A-Z')
    grep -q "^$variable=" "$env_file" && continue
    current user create "s7-$role" "s7-$role@example.org" --role="$role" --user_pass="$(secret)" >/dev/null
    add "$variable" "$(current user application-password create "s7-$role" otlet-s7 --porcelain)"
done
echo "S7 CMS ready; credentials in $env_file"
