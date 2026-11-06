# Instruccions per a aquest repositori d'eines d'agents

- Mantén `instructions/base.md` curt i portable entre agents de programació.
- Trasllada els procediments específics de repositori, runtime o proveïdor a
  skills concretes o a les instruccions locals del consumidor.
- Tracta el SHA complet del manifest consumidor com l'única versió de la font.
- Prova la sincronització en repositoris temporals abans de tocar un consumidor.
  El sincronitzador ha de validar totes les sortides abans d'escriure'n cap.
- No sobreescriguis canvis del consumidor si el sincronitzador no confirma que
  el fitxer està gestionat i que el hash registrat continua coincidint.
- Escriu la documentació en català, com la resta del projecte. Mantén estables i
  agnòstics a l'eina els noms de skills, les metadades i els identificadors.
