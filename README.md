# Planning IA pour les SHS — Bloc SWITCH ODYSSEE S3 (14–18 sept. 2026)

Calendrier des séances de l'UE **HMUBIA3 – Intelligence artificielle pour les SHS : Modélisation par Système Multi-agents**,
extrait automatiquement de l'emploi du temps ADE de l'Université Côte d'Azur.

## S'abonner (mise à jour automatique)

Ajoute cette URL comme **calendrier par abonnement** (pas en import de fichier, sinon il ne se mettra pas à jour) :

```
https://raw.githubusercontent.com/2h5hhj6kjn-star/edt-ia-shs/main/ADECal-IA-seul.ics
```

- **Google Agenda** (sur ordinateur) : `+` à côté de « Autres agendas » → **À partir de l'URL** → coller l'URL.
- **iPhone / Mac** : Réglages → Calendrier → Comptes → Ajouter un compte → Autre → **Abonnement à un calendrier** → coller l'URL.
- **Outlook** : Ajouter un calendrier → **S'abonner à partir du web** → coller l'URL.

Le planning est re-téléchargé depuis ADE **chaque matin vers 6h** jusqu'au 18/09 ; les changements de salle apparaissent
dans [CHANGELOG.md](CHANGELOG.md). Les agendas rafraîchissent ensuite à leur rythme (Google : quelques heures ; Apple : réglable).

## Fonctionnement

- `update_planning.py` : télécharge l'ICS complet du bloc (URL secrète `ADE_ICS_URL`), garde les séances dont le titre
  contient `EDT_FILTER` (« Intelligence artificielle »), écrit `ADECal-IA-seul.ics` uniquement si quelque chose a changé.
- `.github/workflows/update.yml` : exécution planifiée sur GitHub Actions + bouton *Run workflow* pour forcer une mise à jour.
