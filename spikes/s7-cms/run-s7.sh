#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# S7.5 on the measurement machine, detached (nohup), from a copy of spikes/ (s7-cms and
# s3-document side by side): starts the fault proxy, then one series of 100 publications per
# configuration. W3 runs first with the Wordfence defaults, then, outside the protocol, with
# application passwords allowed (the one setting a user would change). Progress: run-s7.log
set -eu
cd "$(dirname "$0")"
mkdir -p results && chmod 777 results
set -a; . "$HOME/otlet-cms.env"; set +a

py() { # container name, args…
    name=$1; shift
    sudo docker run --rm --name "$name" --network otlet-cms_default --env-file "$HOME/otlet-cms.env" \
        -v "$(cd .. && pwd):/spikes" -w /spikes/s7-cms otlet-s5 "$@"
}
wordfence_app_passwords() { # 0 = allowed, 1 = disabled (Wordfence default)
    sudo docker exec otlet-cms-mariadb-1 mariadb -uroot -p"$CMS_DB_PASSWORD" wp_secured -e \
        "UPDATE wp_wfconfig SET val='$1' WHERE name='loginSec_disableApplicationPasswords'"
}
cleanup() { sudo docker rm -f s7-proxy > /dev/null 2>&1 || true; wordfence_app_passwords 1; }
trap cleanup EXIT

cleanup
sudo docker run -d --name s7-proxy --network otlet-cms_default -v "$(pwd):/work" -w /work otlet-s5 -u proxy.py > /dev/null
sleep 3
for config in W1 W2 G1 W3; do
    echo "### $(date -u +%H:%M:%S) $config"
    py "s7-run-$config" run_s7.py "$config" || echo "FAILED $config"
done
echo "### $(date -u +%H:%M:%S) W3-apppw (outside the protocol)"
wordfence_app_passwords 0
py s7-run-W3b run_s7.py W3 --label W3-apppw || echo "FAILED W3-apppw"
wordfence_app_passwords 1
sudo docker logs s7-proxy > results/proxy.log 2>&1
echo "### $(date -u +%H:%M:%S) done"
