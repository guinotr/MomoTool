# Event Task Manager - MomoTool

Application simple de gestion de tâches par salon pour événements.

## Fonctionnalités

- Authentification simple par identifiant/mot de passe
- Création de tâches avec :
  - Nom du salon
  - Nom de la tâche
  - Description
  - URLs liées
  - Niveau de priorité (1, 2, 3)
- Filtrage par salon
- Suppression de tâches
- Stockage SQLite local

## Installation locale

1. Installer les dépendances :
```bash
pip install -r requirements.txt
```

2. Lancer le serveur :
```bash
cd server
python main.py
```

3. Ouvrir dans le navigateur : `http://localhost:8001`

## Déploiement sur VPS (Ubuntu)

### 1. Préparer le serveur

```bash
# Se connecter au VPS
ssh ubuntu@51.178.48.50

# Créer le dossier de l'application
mkdir -p ~/momotool
cd ~/momotool
```

### 2. Transférer les fichiers

Depuis ta machine locale :
```bash
cd C:\Users\ronan\Documents\Projects\MomoTool

# Transférer tous les fichiers
scp -r static server requirements.txt ubuntu@51.178.48.50:~/momotool/
```

### 3. Configuration sur le serveur

```bash
# Se connecter au VPS
ssh ubuntu@51.178.48.50
cd ~/momotool

# Créer et configurer le fichier .env
nano .env
```

Contenu du `.env` (à personnaliser) :
```env
APP_USERNAME=morgane
APP_PASSWORD=UN_MOT_DE_PASSE_SECURISE
JWT_SECRET=UN_SECRET_JWT_ALEATOIRE
DB_PATH=/home/ubuntu/momotool/tasks.db
```

### 4. Installer les dépendances

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
pip install python-dotenv
```

### 5. Créer un service systemd

```bash
sudo nano /etc/systemd/system/momotool.service
```

Contenu du fichier :
```ini
[Unit]
Description=MomoTool Event Task Manager
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/momotool/server
Environment="PATH=/home/ubuntu/momotool/venv/bin"
EnvironmentFile=/home/ubuntu/momotool/.env
ExecStart=/home/ubuntu/momotool/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Activer et démarrer le service
sudo systemctl daemon-reload
sudo systemctl enable momotool
sudo systemctl start momotool

# Vérifier le statut
sudo systemctl status momotool
```

### 6. Configuration Nginx (si tu utilises Nginx)

```bash
sudo nano /etc/nginx/sites-available/momotool
```

Contenu :
```nginx
server {
    listen 80;
    server_name momotool.tondomaine.com;  # Ou utiliser une sous-URL

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Activer le site
sudo ln -s /etc/nginx/sites-available/momotool /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Alternative : Servir sur un port différent

Si tu veux juste accéder via IP:port sans Nginx :

1. Ouvrir le port dans le firewall :
```bash
sudo ufw allow 8001/tcp
```

2. Accéder via : `http://51.178.48.50:8001`

## Commandes utiles

```bash
# Voir les logs de l'application
sudo journalctl -u momotool -f

# Redémarrer le service
sudo systemctl restart momotool

# Arrêter le service
sudo systemctl stop momotool

# Voir la base de données
sqlite3 /home/ubuntu/momotool/tasks.db "SELECT * FROM tasks;"

# Backup de la base de données
cp /home/ubuntu/momotool/tasks.db /home/ubuntu/momotool/tasks.db.backup
```

## Structure du projet

```
MomoTool/
├── server/
│   └── main.py           # Serveur FastAPI
├── static/
│   └── index.html        # Interface web
├── requirements.txt      # Dépendances Python
├── .env.example         # Exemple de configuration
└── README.md            # Documentation
```

## Sécurité

- Utilise HTTPS en production (Let's Encrypt avec Nginx)
- Change le mot de passe par défaut dans le `.env`
- Génère un JWT_SECRET aléatoire fort
- Sauvegarde régulièrement la base de données

## Support

Pour toute question ou problème, contacte Ronan.
