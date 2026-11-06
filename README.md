# Skills i toolkit d'agents de Som Energia

Skills i instruccions compartides breus per als repositoris de Som Energia. La
font és independent de l'agent de programació; cada consumidor versiona
`AGENTS.md` i `.agents/skills/` generats per poder treballar sense xarxa després
d'un clon normal.

El format portable és compatible amb OpenCode, Pi i Codex. Tots tres llegeixen
`AGENTS.md` com a instruccions del repositori i descobreixen skills de projecte
a `.agents/skills/<skill>/SKILL.md`. Les metadades segueixen el format Agent
Skills (`name` i `description` al frontmatter). Altres agents poden reutilitzar
les mateixes fonts Markdown amb els seus adaptadors.

El repositori central es diu `SomCommonSkills` (abans `opencode-skills`).

Referències oficials consultades:

- [Codex: AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md)
  documenta la càrrega jeràrquica d'instruccions de projecte.
- [Codex: Skills](https://developers.openai.com/codex/build-skills) documenta
  `SKILL.md`, el frontmatter obligatori i la descoberta a `.agents/skills`.
- [OpenCode: Agent Skills](https://opencode.ai/docs/skills/) documenta
  `.agents/skills/<name>/SKILL.md` i `name`/`description`.
- [Pi: Skills](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md)
  documenta el format Agent Skills i la ubicació de projecte `.agents/skills`.

## Estructura de les fonts

Es conserven les carpetes de skills actuals a l'arrel per no trencar les
instal·lacions existents d'aquest repositori. Són les fonts canòniques; el
sincronitzador identifica cada skill pel camp `name` del seu `SKILL.md`, no pel
nom del directori.

| Ruta | Funció |
|---|---|
| `AGENTS.md` | Instruccions per contribuir a aquest repositori |
| `instructions/base.md` | Instruccions compartides breus distribuïdes als consumidors |
| `<skill>/SKILL.md` | Skills compartides i els seus recursos |
| `scripts/sync_agents.py` | Sincronitzador validat i determinista |
| `tests/` | Proves del sincronitzador |
| `requirements-toolkit.txt` | Dependència necessària només per executar el sincronitzador i les proves |

## Configuració d'un consumidor

Cada consumidor té un manifest `agent-toolkit.yml`. El SHA complet del commit
fixa la font independentment de la resta de repositoris. Exemple:

```yaml
source:
  repository: https://github.com/Som-Energia/SomCommonSkills.git
  revision: 0123456789abcdef0123456789abcdef01234567
  skill_root: .
local_instructions: AGENTS.local.md
local_skills: .agents/local-skills
common_skills:
  - git-branch
  - git-commit
  - git-pr
skill_config: {}
overrides:
  git-pr:
    path: .agents/local-skills/git-pr
    reason: "Aquest repositori té requisits addicionals de PR als workflows de GitHub."
```

### Convencions organitzatives per defecte

| Àmbit | Norma compartida |
|---|---|
| Branques | `main`; format `<PREFIX>_<descripcio>`; prefixos `ADD_`, `IMP_`, `FIX_`, `MOD_`, `REF_`, `TEST_`, `DOCS_`, `CI_`; descripció en anglès, minúscules, 2–3 paraules, `_`, màxim 50 caràcters |
| Commits | `<emoji> <descripció>`; anglès, imperatiu, màxim 72 caràcters; no afegir prefix textual `feat:`/`fix:`; emoji segons `gitmoji.dev` |
| Pull requests | Descripció en català amb Objectiu, Targeta/incidència, Comportament antic, Comportament nou i Comprovacions |

Les convencions compartides són el **valor per defecte de l'organització**. Les
skills n'expliquen el procediment concret; les instruccions locals només afegeixen
context o excepcions justificades.

`skill_config` és la interfície documentada per a adaptacions petites:

| Skill | Opció | Valor per defecte | Valors documentats |
|---|---|---|---|
| `git-branch` | `base_branch` | `main` | Nom d'una branca base |
| `git-commit` | `format` | `emoji-description` | `emoji-description`, `emoji-type-description` |
| `git-pr` | `base_branch` | `main` | Nom d'una branca base |

Exemple d'una excepció de base per al repositori:

```yaml
skill_config:
  git-branch:
    base_branch: developer
    reason: "Aquest repositori integra canvis a la branca developer."
```

Qualsevol valor diferent del valor per defecte necessita un `reason` no buit.
Les skills han de llegir i aplicar les opcions declarades; les claus o opcions no
documentades provoquen un error, no s'ignoren.

`overrides` és per a divergències de flux que requereixen substituir una skill
sencera. Cada entrada associa un nom seleccionat amb un directori local i un
motiu no buit. El directori ha de ser dins de `local_skills`. La substitució
reemplaça tot el contingut de la skill, inclosos els recursos; el
sincronitzador no fusiona dos `SKILL.md`. Les altres skills de `local_skills`
s'afegeixen. Cada skill efectiva ha de tenir un `name` únic al frontmatter; els
duplicats sense resoldre aturen la sincronització.

Executa el sincronitzador del checkout de la font sobre el consumidor:

```bash
python3 -m pip install -r requirements-toolkit.txt
python3 scripts/sync_agents.py \
  --repo /ruta/al/consumidor \
  --toolkit-dir /ruta/al/SomCommonSkills-net-i-fixat
```

Per a la primera adopció, preserva l'`AGENTS.md` antic com a fitxer local
declarat al manifest i conserva les skills locals a `local_skills` o en una
substitució explícita. Després, executa `--adopt` una vegada per autoritzar la
substitució de sortides existents encara no gestionades:

```bash
python3 scripts/sync_agents.py --repo /ruta/al/consumidor \
  --toolkit-dir /ruta/al/SomCommonSkills-net-i-fixat --adopt
```

L'eina comprova que el checkout del toolkit és net i coincideix exactament amb
el SHA fixat abans de llegir-ne les fonts. Si no s'indica `--toolkit-dir`, obté
el commit des del repositori del manifest. Les tasques normals dels agents no
executen aquesta ordre ni necessiten connexió de xarxa.

### Fitxers generats i fonts canòniques

El sincronitzador només gestiona:

- `AGENTS.md`: primer `instructions/base.md`, després el fitxer local declarat
  a `local_instructions`.
- `.agents/skills/<name>/`: skills comunes seleccionades, addicions locals i
  substitucions locals completes.
- `.agent-toolkit-state.json`: hashes de tots els fitxers generats i commit de
  la font utilitzada.

Edita el contingut compartit en aquest repositori. Edita les instruccions
específiques al fitxer local del manifest i les skills locals a `local_skills`.
No editis les sortides generades. Abans d'escriure, l'eina compara els fitxers
amb els hashes registrats i es nega a sobreescriure canvis manuals. Valida rutes,
referències, identitats de skills i col·lisions abans de modificar cap fitxer.
Elimina els fitxers gestionats obsolets individualment i no toca fitxers aliens.

Utilitza `--check` a CI. És de només lectura i falla si les sortides, els hashes
o la revisió fixada no coincideixen:

```bash
python3 scripts/sync_agents.py --repo . \
  --toolkit-dir /ruta/al/toolkit-fixat --check
```

## Actualitzar un consumidor

1. Obre una PR en aquest repositori per al canvi compartit i revisa'n les skills
   i els recursos.
2. Quan el commit de la font estigui disponible, obre una PR separada per a
   cada consumidor. Canvia només `source.revision` pel SHA complet revisat i
   executa el sincronitzador.
3. Revisa `AGENTS.md`, `.agents/skills/` i `.agent-toolkit-state.json` al diff
   del consumidor. Confirma que les regles específiques continuen sent locals i
   que cap substitució s'ha convertit accidentalment en una fusió.
4. Executa les comprovacions del consumidor i el job de CI `--check` abans de
   fusionar.

Cada consumidor s'actualitza independentment: un canvi central no hi arriba fins
que el seu manifest canvia en una PR revisada. Per tornar enrere, restaura el
valor anterior de `source.revision`, torna a sincronitzar i revisa el diff.

## Criteris per compartir contingut

- Comparteix només fluxos verificats en més d'un repositori.
- Codifica les convencions organitzatives a les skills compartides amb exemples
  i comandes concretes; l'`AGENTS.md` base es manté breu.
- Mantén locals els detalls de runtime i framework. Una convenció Git diferent
  necessita una justificació local explícita.
- Utilitza `skill_config` només per a opcions que una skill documenti. Per a un
  flux materialment diferent, utilitza una substitució completa amb motiu.
- Revisa les excepcions periòdicament: una diferència que es repeteix en diversos
  repositoris pot indicar que cal actualitzar la norma compartida.
- No incloguis credencials, rutes personals ni dades privades a les fonts
  compartides.

## Instal·lació individual de skills

Per a una instal·lació personal compatible amb OpenCode, Pi i Codex:

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/Som-Energia/SomCommonSkills.git \
  ~/.cache/somenergia-agent-skills
cp -R ~/.cache/somenergia-agent-skills/git-* ~/.agents/skills/
```

La còpia posa cada skill directament a l'arrel de descoberta compartida pels
tres agents. Repeteix-la després d'actualitzar el clon per actualitzar les
skills personals. Per a instruccions de projecte i versions fixades, segueix el
flux de manifest del consumidor.
