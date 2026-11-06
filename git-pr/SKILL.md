---
name: git-pr
description: >
  Prepare a Som Energia pull request with the shared description structure and
  repository-specific checks. Use when completed work is ready for review.
---

# Preparar una pull request

Segueix aquest flux compartit. Les regles de GitHub del repositori poden afegir
requisits locals, però només una excepció documentada pot substituir la
convenció organitzativa.

## Descripció compartida

Escriu la descripció en català i omple totes aquestes seccions:

```markdown
## Objectiu

## Targeta on es demana o Incidència

## Comportament antic

## Comportament nou

## Comprovacions

- [ ] Hi ha tests
- [ ] Reiniciar serveis
- [ ] Actualitzar mòdul
- [ ] Script de migració
- [ ] Modifica traduccions
```

Marca només les comprovacions que apliquen. Si el repositori té una plantilla
versionada, utilitza-la com a font de veritat i conserva aquestes seccions que hi
siguin aplicables.

## Flux

1. Confirma el repositori, la branca actual i la branca base declarada a
   `skill_config.git-pr.base_branch` (per defecte, `main`). Revisa `git status --short`,
   `git diff --check`, el diff complet i els commits de la branca.
2. Llegeix les instruccions locals, la plantilla i els workflows de CI. Comprova
   si exigeixen issue, etiquetes, assignació, checks o un procediment específic.
   No assumeixis requisits que no estiguin documentats.
3. Executa les comprovacions aplicables i anota'n els resultats reals. No
   declaris superades les que no s'han executat.
4. Publica només la branca prevista i crea la pull request amb el títol clar i
   les seccions anteriors. Utilitza un fitxer per al cos:

   ```bash
   gh pr create --base main --title "<títol>" --body-file <fitxer>
   ```

   Afegeix les etiquetes locals que exigeixin els workflows del repositori.
5. Verifica la base, el títol, el cos, les etiquetes i els checks de la PR.

Una divergència de plantilla o de procés s'ha de documentar a les instruccions
locals. Si canvia la skill sencera, el consumidor ha d'indicar a
`agent-toolkit.yml` la substitució completa i el motiu; no fusiones fragments de
dos `SKILL.md`.
