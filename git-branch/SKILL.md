---
name: git-branch
description: >
  Create a Som Energia work branch with the organization naming convention and
  preserve unrelated changes. Use when starting work that needs a branch.
---

# Crear una branca de treball

Aquest és el flux per defecte de Som Energia. Només segueix una excepció local
si el repositori la declara explícitament a les instruccions locals i n'explica
la necessitat.

## Convenció compartida

- Branca base: `main`, tret que `skill_config.git-branch.base_branch` declari
  una excepció local amb `reason` no buit.
- Format: `<PREFIX>_<descripcio>`.
- Prefixos: `ADD_`, `IMP_`, `FIX_`, `MOD_`, `REF_`, `TEST_`, `DOCS_` i `CI_`.
- Descripció en anglès, minúscules, de 2 o 3 paraules, separades amb `_`, fins
  a 50 caràcters.
- Exemple: `IMP_invoice_payment_type_views`.

## Flux

1. Identifica el repositori amb `git rev-parse --show-toplevel` i revisa
   `git status --short --branch`.
2. Preserva els canvis locals: no els descartis, desis amb `stash` ni incloguis
   a la branca nova sense autorització.
3. Llegeix l'`AGENTS.md` i `agent-toolkit.yml`. Aplica una excepció local només
   si el manifest declara el valor i un motiu no buit.
4. Comprova que el nom de branca no existeix i actualitza la referència remota:

   ```bash
   git fetch origin
   ```

5. Crea la branca directament des de la base remota, sense canviar la branca
   actual ni arriscar-ne els canvis locals:

   ```bash
   git switch -c <PREFIX>_<descripcio> origin/main
   ```

6. Verifica `git status --short --branch` abans de començar a editar.

Si l'`AGENTS.md` local exigeix sincronitzar workspaces, triar un worktree o
utilitzar un wrapper abans de crear la branca, segueix primer aquell procediment.
