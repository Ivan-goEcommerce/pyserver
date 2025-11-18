# n8n Deployment Anleitung

## Voraussetzungen
- Ubuntu Server mit Docker und Docker Compose installiert
- DNS-Eintrag: `n8n-ivan.go-ecommerce.de` → `46.62.214.109`
- Zugriff auf den Server über SSH/Putty

## Installation auf dem Server

### 1. Dateien auf den Server kopieren

Über Putty/SSH verbinden und folgende Befehle ausführen:

```bash
# Verzeichnis erstellen
mkdir -p ~/n8n-deployment
cd ~/n8n-deployment

# Dateien hochladen (mit SCP oder WinSCP):
# - docker-compose.yml
# - nginx/nginx.conf
# - nginx/conf.d/n8n.conf
```

### 2. Docker Compose starten

```bash
# Im Verzeichnis ~/n8n-deployment
docker-compose up -d
```

### 3. Status prüfen

```bash
# Container-Status prüfen
docker-compose ps

# Logs anzeigen
docker-compose logs -f n8n
docker-compose logs -f nginx
```

### 4. Firewall konfigurieren (falls nötig)

```bash
# Port 80 und 443 öffnen
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

## Zugriff

Nach dem Start sollte n8n erreichbar sein unter:
- **http://n8n-ivan.go-ecommerce.de/**

## Wichtige Befehle

```bash
# Container stoppen
docker-compose down

# Container neu starten
docker-compose restart

# Logs anzeigen
docker-compose logs -f

# Container-Status
docker-compose ps

# n8n-Daten sichern (Volume)
docker run --rm -v n8n-deployment_n8n_data:/data -v $(pwd):/backup alpine tar czf /backup/n8n-backup.tar.gz -C /data .
```

## SSL/HTTPS einrichten (optional)

1. SSL-Zertifikat in `nginx/ssl/` ablegen:
   - `cert.pem`
   - `key.pem`

2. In `nginx/conf.d/n8n.conf` den HTTPS-Block aktivieren (Zeilen auskommentieren)

3. HTTP zu HTTPS Redirect aktivieren

4. Container neu starten:
   ```bash
   docker-compose restart nginx
   ```

## Troubleshooting

### Container startet nicht
```bash
docker-compose logs
```

### nginx-Fehler
```bash
# nginx-Konfiguration testen
docker exec nginx-proxy nginx -t
```

### Port bereits belegt
```bash
# Prüfen, was Port 80 verwendet
sudo netstat -tulpn | grep :80
# Oder
sudo lsof -i :80
```

### DNS funktioniert nicht
```bash
# DNS-Auflösung testen
nslookup n8n-ivan.go-ecommerce.de
dig n8n-ivan.go-ecommerce.de
```

