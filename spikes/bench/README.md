# Banc de mesure commun (B09)

Outils partagés par les preuves d'É0. Bibliothèque standard Python seulement, pour tourner sur la machine de mesure sans installation.

| Fichier | Rôle |
|---|---|
| `bench.py` | Exécute des charges nommées avec N clients concurrents, après une chauffe, et produit pour chacune min, p50, p95, p99, max et moyenne, en JSON. Mode `http` en ligne de commande |
| `memwatch.py` | Relève chaque seconde la mémoire de chaque conteneur d'un projet Compose (cgroup v2, comme `docker stats`, sans le cache de pages) et donne le maximum de leur somme : la « mémoire de la pile ». À lancer en `root`, arrêté par `kill -INT` |
| `run-remote.sh` | Copie le banc et le dossier d'une preuve sur la machine de mesure, y lance une commande, puis rapatrie son dossier `results/` |

Exemple, la mesure de `/health` sur la VM de mesure (critère « fini quand » de B09) :

```sh
OTLET_SSH_OPTS="-i ~/.ssh/otlet_nas" sh spikes/bench/run-remote.sh otlet@192.168.129.249 bench \
  'sudo python3 memwatch.py --project otlet --out results/health-mem.json > /dev/null & w=$!; sleep 3;
   python3 bench.py http https://192.168.129.249/health --insecure --name health; sudo kill -INT $w; wait $w'
```

Les centiles sont calculés au rang le plus proche. Un échec d'exécution est compté dans `errors` et n'entre pas dans les latences.
