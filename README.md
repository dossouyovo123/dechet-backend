# Tri-Gagnant — Backend

Backend Django REST pour **Tri-Gagnant**, une application de collecte de déchets triés (sacs verts, jaunes, noirs) via QR codes, avec un système de points convertibles en argent (retraits Mobile Money via Kkiapay), destinée à une application mobile Flutter avec trois profils : **citoyen**, **collecteur** et **administrateur**.

## Sommaire

- [Aperçu](#aperçu)
- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Modèle métier](#modèle-métier)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancer le projet](#lancer-le-projet)
- [Structure du projet](#structure-du-projet)
- [Routes API](#routes-api)
- [Sécurité — points d'attention](#sécurité--points-dattention)
- [Licence](#licence)

## Aperçu

Tri-Gagnant encourage le tri des déchets à la source : chaque citoyen reçoit des sacs de tri (vert/jaune/noir), identifiés par un code unique servant de QR code. Lorsqu'un collecteur récupère les sacs remplis chez un citoyen, il scanne chaque sac pour valider la collecte, ce qui crédite des points au citoyen et au collecteur. Ces points peuvent ensuite être convertis et retirés en argent réel via Mobile Money (intégration Kkiapay).

L'API est sécurisée par JWT (JSON Web Token) et gère trois types d'utilisateurs distincts avec des permissions dédiées : **citoyen**, **collecteur** et **administrateur**.

## Fonctionnalités

- **Authentification JWT** — inscription séparée citoyen/collecteur, connexion, gestion du profil utilisateur.
- **Gestion des sacs de tri (`SacTri`)** — création, modification, suppression, attribution aux citoyens (vert/jaune/noir), identifiant unique à 8 chiffres utilisé comme QR code.
- **Scan et validation des collectes** — un collecteur scanne l'ID du sac (`marquer-sac-utilise`) pour marquer une collecte comme effectuée.
- **Collectes (`Collecte`)** — cycle de vie complet (en attente → en cours → en cours de scan → terminé/annulé), attribution de points par couleur de sac, historique par citoyen et par collecteur.
- **Système de points** — comptage total des collectes et des points par citoyen/collecteur, incrémentation des points, classement/statistiques.
- **Planification des collectes** — création de tournées par ville/quartier/date/heure avec assignation de plusieurs collecteurs.
- **Notifications** — notifications géolocalisées (latitude/longitude) envoyées aux utilisateurs, statut lu/non lu.
- **Retraits Mobile Money (Kkiapay)** — demandes de retrait pour citoyens et collecteurs, suivi du statut (en attente, approuvé, rejeté, échec/succès Kkiapay), traçabilité de l'agent traitant.
- **Tableaux de bord / statistiques** — nombre total d'utilisateurs, de sacs, de collectes, de planifications.
- **Emails** — envoi d'e-mails via SMTP (Gmail) pour les échanges liés au compte.

## Stack technique

- **Python** 3 / **Django** 4.2
- **Django REST Framework** — construction de l'API REST
- **djangorestframework-simplejwt** — authentification par JWT (access/refresh tokens)
- **django-cors-headers** — gestion CORS pour la consommation par l'app mobile Flutter
- **MySQL** (`mysqlclient`) — base de données
- **python-decouple** / **python-dotenv** — gestion des variables d'environnement
- **qrcode**, **pillow** — génération de QR codes / traitement d'images
- **Kkiapay** — passerelle de paiement Mobile Money pour les retraits
- Hébergement pensé pour **PythonAnywhere** (paramètres MySQL par défaut orientés PythonAnywhere)

## Modèle métier

### Utilisateurs (`CustomUser`)

Utilisateur personnalisé (hérite de `AbstractUser`), identifié par un **ID formaté unique** (`id_formatte`, champ d'authentification principal) plutôt que par le nom d'utilisateur classique. Trois types :

| `user_type` | Rôle |
|---|---|
| `citoyen` | Reçoit des sacs, fait collecter ses déchets, gagne des points, demande des retraits |
| `collector` | Scanne les sacs, valide les collectes, gagne des points, demande des retraits |
| `admin` | Supervise planifications, collectes, utilisateurs et retraits |

### Sacs de tri

- **`SacTri`** — un sac physique (`idformatter_sac`, 8 chiffres, sert de QR code), de couleur `vert` / `jaune` / `noir`, avec un statut `Disponible` ou `Utilisé`.
- **`SacCitoyen`** — quantité de sacs (vert/jaune/noir) attribués à un citoyen donné.

### Collectes

- **`Collecte`** — une collecte reliant un citoyen et un collecteur, avec des points par couleur de sac (`point_vert`, `point_jaune`, `point_noir`) et un statut de cycle de vie (`en_attente` → `en_cours` → `en_cours_scan` → `termine` / `annule`).
- **`PlanificationCollecte`** — tournée de collecte planifiée par ville/quartier/date/heure, avec plusieurs collecteurs assignés.

### Retraits

- **`Retrait`** — demande de retrait d'argent (citoyen ou collecteur) traitée via Kkiapay, avec statuts `en_attente`, `approuve`, `rejete`, `echec_kkiapay`, `complete_kkiapay`, et traçabilité de l'agent qui a traité la demande.

### Notifications

- **`Notification`** — message adressé à un utilisateur, avec position géographique optionnelle (utile pour prévenir un citoyen du passage d'un collecteur à proximité) et statut lu/non lu.

## Prérequis

- Python 3.10+
- pip / virtualenv
- MySQL
- Un compte Kkiapay (sandbox pour les tests) pour les retraits Mobile Money
- Un compte Gmail (ou autre SMTP) pour l'envoi d'e-mails

## Installation

```bash
git clone https://github.com/dossouyovo123/dechet-backend.git
cd dechet-backend

python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

Le projet utilise `python-decouple` et `python-dotenv` : créez un fichier `.env` à la racine avec au minimum :

```env
SECRET_KEY=change-moi-en-production

# Base de données MySQL
MYSQL_DATABASE_NAME=dechet_app_db
MYSQL_DATABASE_USER=root
MYSQL_DATABASE_PASSWORD=
MYSQL_DATABASE_HOST=127.0.0.1
MYSQL_DATABASE_PORT=3306

DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Email (SMTP Gmail)
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=mot-de-passe-application

# Kkiapay (paiements Mobile Money)
KKIAPAY_API_BASE_URL=https://api-sandbox.kkiapay.me/api/v1
KKIAPAY_PUBLIC_KEY=
KKIAPAY_SECRET_KEY=
KKIAPAY_MERCHANT_ID=
```

Puis lancer les migrations et créer un compte administrateur :

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Lancer le projet

```bash
python manage.py runserver
```

L'API est alors accessible sur `http://localhost:8000/api/`, et l'admin Django sur `http://localhost:8000/admin/`.

## Structure du projet

```
dechet_backend/
├── settings.py          # Configuration Django (DB, JWT, CORS, email, Kkiapay)
├── urls.py               # Point d'entrée des routes (/admin, /api/)
├── wsgi.py / asgi.py

utilisateurs/
├── models.py             # CustomUser, SacTri, SacCitoyen, Collecte, PlanificationCollecte, Notification, Retrait
├── views.py               # Vues principales (auth, sacs, collectes, retraits, stats)
├── api_sacCitoyenView.py  # ViewSets Citoyen / Attribution des sacs / Collecte
├── serializers.py         # Sérialiseurs DRF
├── login_serializers.py   # Sérialiseur de connexion
├── urls.py                 # Routes de l'app (router DRF + endpoints personnalisés)
├── admin.py                # Configuration de l'admin Django
└── migrations/
```

## Routes API

Toutes les routes sont préfixées par `/api/`.

### Authentification

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/register/citizen/` | Inscription d'un citoyen |
| POST | `/register/collector/` | Inscription d'un collecteur |
| POST | `/login/` | Connexion (retourne les tokens JWT) |

### Utilisateurs

- `GET /users/count/` — nombre total d'utilisateurs
- `GET /collecteurs/{pk}/` — détail d'un collecteur
- Router DRF : `/users/`, `/citoyens/`, `/collector/` (CRUD selon les permissions)

### Sacs de tri

- `POST /ajouter_sacs/`, `PUT /modifier_sac/{id_sac}/`, `DELETE /supprimer_sac/{id_sac}/`
- `GET /sacs/`, `GET /sacs/count/`
- `POST /sacs/marquer-sac-utilise/` — scan et validation d'un sac
- Router DRF : `/attribution_sacs/` (attribution des sacs aux citoyens)

### Collectes

- `GET /collectes/by_citoyen/` — collectes d'un citoyen
- `PATCH /collectes/{pk}/incrementer-points/`
- `GET /collectes/total-collectes-par-citoyen/`
- `GET /collectes/total-collectes-collecteur/`
- `GET /collectes/count-all/`
- `GET /collectes/total-points/`
- `GET /collectes/points-citoyen/{citizen_id}/`
- Router DRF : `/collectes/`, `/admin/collectes/` (lecture seule, vue admin)

### Planifications & notifications

- `GET /planifications/count/`
- Router DRF : `/planifications/`, `/notifications/`

### Retraits (Mobile Money — Kkiapay)

- `POST /retraits/collecteur/` — demande de retrait d'un collecteur
- `POST /retraits/citoyen/` — demande de retrait d'un citoyen

## Sécurité — points d'attention

Avant un déploiement en production, il est recommandé de :

- **Retirer les valeurs de secours codées en dur** dans `settings.py` (clé secrète Django, mot de passe MySQL, clés Kkiapay) et de s'assurer que **toutes** proviennent uniquement des variables d'environnement (`.env`), sans valeur par défaut sensible dans le code.
- Régénérer une nouvelle `SECRET_KEY` Django ainsi que de nouvelles clés Kkiapay (les clés actuelles dans le code sont des clés de test/sandbox mais ne doivent pas rester en clair dans le dépôt).
- Vérifier `ALLOWED_HOSTS` et la configuration CORS en production (actuellement permissifs par défaut).
- Réactiver la protection CSRF pour les vues qui en ont besoin si des formulaires web sont utilisés (le middleware CSRF est commenté dans `settings.py`).

## Licence

Ce projet est un projet privé développé par [DOSSOU-YOVO José Mario](https://github.com/dossouyovo123). Sauf mention contraire, tous droits réservés.