#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S3.6 on the measurement machine: starts WordPress (current, previous) and Ghost, installs
# them, creates the API credentials, and writes them to ~/otlet-cms.env (mode 600), reused by
# S7. Run from spikes/s3-document/cms. Idempotent: an existing ~/otlet-cms.env is kept.
set -eu

env_file="$HOME/otlet-cms.env"
secret() { head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
if [ ! -f "$env_file" ]; then
    umask 077
    {
        echo "CMS_DB_PASSWORD=$(secret)"
        echo "WP_ADMIN_PASSWORD=$(secret)"
        echo "GHOST_PASSWORD=Gh-$(secret)"
    } > "$env_file"
fi
set -a; . "$env_file"; set +a

compose() { sudo -E docker compose -f compose.yaml "$@"; }
compose up -d --wait --wait-timeout 300 mariadb
compose up -d wordpress wordpress-previous ghost

wp() { # volume, url, args…
    volume=$1; url=$2; shift 2
    sudo docker run --rm --network otlet-cms_default -v "otlet-cms_$volume:/var/www/html" \
        -e WORDPRESS_DB_HOST=mariadb -e WORDPRESS_DB_USER=root \
        -e WORDPRESS_DB_PASSWORD="$CMS_DB_PASSWORD" -e WORDPRESS_DB_NAME="$volume" \
        --user 33:33 wordpress:cli-php8.4 \
        wp --url="$url" "$@"
}
for pair in "wp_current http://wordpress WP_APP_PASSWORD" "wp_previous http://wordpress-previous WP_PREVIOUS_APP_PASSWORD"; do
    set -- $pair
    if grep -q "^$3=" "$env_file"; then continue; fi
    for _ in $(seq 1 60); do wp "$1" "$2" core version >/dev/null 2>&1 && break; sleep 2; done
    wp "$1" "$2" config set WP_ENVIRONMENT_TYPE local >/dev/null
    wp "$1" "$2" core install --title=S3 --admin_user=admin --admin_password="$WP_ADMIN_PASSWORD" \
        --admin_email=s3@example.org --skip-email >/dev/null
    echo "$3=$(wp "$1" "$2" user application-password create admin otlet-s3 --porcelain)" >> "$env_file"
    echo "$1: $(wp "$1" "$2" core version)"
done

if ! grep -q '^GHOST_ADMIN_KEY=' "$env_file"; then
    for _ in $(seq 1 60); do
        curl -fs http://localhost:2368/ghost/api/admin/site/ >/dev/null 2>&1 && break; sleep 3
    done
    key=$(sudo docker run --rm --network otlet-cms_default -v "$(cd .. && pwd):/work" \
        -e GHOST_URL=http://ghost:2368 -e GHOST_EMAIL=s3@example.org -e GHOST_PASSWORD="$GHOST_PASSWORD" \
        -w /work/cms --entrypoint python otlet:dev roundtrip.py setup-ghost)
    echo "GHOST_ADMIN_KEY=$key" >> "$env_file"
fi
echo "CMS ready; credentials in $env_file"
