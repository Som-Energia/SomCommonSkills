---
name: git-branch
description: >
  Prepara una branca de Git acotada seguint les convencions del repositori.
  Utilitza-la quan comencis una feina que necessiti una branca pròpia.
---

# Flux de treball de branques

Utilitza aquesta skill abans de començar codi, documentació o CI que requereixi
una branca separada.

1. Identifica el repositori amb `git rev-parse --show-toplevel` i revisa
   `git status --short --branch`.
2. Preserva els canvis existents. No els desis amb `stash`, descartis ni
   incloguis sense indicacions explícites de qui n'és responsable.
3. Llegeix l'`AGENTS.md` del repositori i segueix-ne el format de branca i la
   branca base. Si la convenció no està documentada, revisa branques i commits
   recents; pregunta si la base correcta continua sent ambigua.
4. Comprova que el nom proposat no existeix i crea la branca des de la base
   documentada. No actualitzis ni canviïs la branca base si això pot afectar
   canvis locals aliens.
5. Confirma la branca resultant i l'estat del directori de treball.

No assumeixis que altres repositoris del mateix workspace comparteixen prefixes,
branca per defecte o flux de sincronització.
