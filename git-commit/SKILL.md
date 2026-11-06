---
name: git-commit
description: >
  Prepara un commit de Git acotat i revisable que segueixi les convencions de
  missatge i validació del repositori. Utilitza-la per desar feina acabada.
---

# Flux de treball de commits

1. Llegeix l'`AGENTS.md` del repositori i revisa `git status --short`,
   `git diff` i els missatges dels commits recents pertinents.
2. Confirma que cada fitxer modificat forma part de la feina demanada. No
   descartis mai canvis aliens.
3. Prepara només les rutes revisades explícitament amb `git add <ruta>`. No
   utilitzis `git add -A` ni preparis tot el directori per defecte.
4. Revisa `git diff --cached --check` i el diff complet preparat.
5. Executa les comprovacions aplicables documentades pel repositori. Indica les
   que no has executat; no afirmis que han passat.
6. Utilitza el format de commit documentat pel repositori. Si no és clar,
   pregunta abans d'inventar-ne un.
7. Crea el commit i verifica'l amb `git show --stat --oneline HEAD` i
   `git status --short`.

Els formats, hooks, requisits de signatura i àmbits específics del repositori
pertanyen a les instruccions locals, no a aquest flux compartit.
