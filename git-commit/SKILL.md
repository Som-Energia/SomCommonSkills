---
name: git-commit
description: >
  Prepare a reviewable commit using Som Energia's shared message format, explicit
  staging, and repository checks. Use when saving completed work.
---

# Preparar un commit

El format compartit de Som Energia és **`<emoji> <descripció>`**: descripció en
anglès, imperativa i de 72 caràcters com a màxim. L'emoji ja expressa el tipus;
no hi afegeixis `feat:`, `fix:` ni cap altre prefix textual. Tria l'emoji segons
[gitmoji.dev](https://gitmoji.dev/) i les convencions locals documentades.

```text
✨ add user authentication flow
🐛 resolve null pointer in invoice calculation
📝 update API endpoint documentation
```

## Excepció de format local

El format local només pot substituir el compartit mitjançant la interfície
documentada a `agent-toolkit.yml`:

```yaml
skill_config:
  git-commit:
    format: emoji-type-description
    reason: Explain the established repository convention.
```

Valors admesos per `format`: `emoji-description` (per defecte) i
`emoji-type-description`. Qualsevol valor no compartit requereix una justificació
no buida. Llegeix aquesta configuració abans de decidir el missatge; no dedueixis
una excepció només dels commits antics.

## Flux compartit

1. Llegeix l'`AGENTS.md` del repositori i revisa `git status --short`,
   `git diff` i els commits recents pertinents.
2. Confirma que els fitxers modificats formen part de la feina acordada. No
   descartis canvis aliens.
3. Prepara només les rutes revisades explícitament:

   ```bash
   git add <ruta> [<ruta> ...]
   ```

   No utilitzis `git add -A` ni preparis tot el directori per defecte.
4. Revisa `git diff --cached --check` i el diff complet preparat.
5. Executa els tests i hooks aplicables documentats pel repositori; indica els
   que no has executat.
6. Crea el commit amb el format compartit o amb l'excepció local declarada.
7. Verifica'l amb `git show --stat --oneline HEAD` i `git status --short`.

Les eines, entorns i comprovacions específiques del repositori es documenten a
les instruccions locals o en una skill local, no com a excepcions implícites.
