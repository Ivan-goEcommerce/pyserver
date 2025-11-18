#!/bin/bash

# n8n Deployment Script
# Führen Sie dieses Script auf dem Ubuntu-Server aus

echo "=== n8n Deployment Script ==="

# Prüfen ob Docker installiert ist
if ! command -v docker &> /dev/null; then
    echo "Docker ist nicht installiert. Bitte installieren Sie Docker zuerst."
    exit 1
fi

# Prüfen ob Docker Compose installiert ist
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose ist nicht installiert. Bitte installieren Sie Docker Compose zuerst."
    exit 1
fi

# Verzeichnis erstellen
echo "Erstelle Verzeichnisstruktur..."
mkdir -p nginx/conf.d nginx/ssl

# Prüfen ob Dateien existieren
if [ ! -f "docker-compose.yml" ]; then
    echo "FEHLER: docker-compose.yml nicht gefunden!"
    exit 1
fi

if [ ! -f "nginx/nginx.conf" ]; then
    echo "FEHLER: nginx/nginx.conf nicht gefunden!"
    exit 1
fi

if [ ! -f "nginx/conf.d/n8n.conf" ]; then
    echo "FEHLER: nginx/conf.d/n8n.conf nicht gefunden!"
    exit 1
fi

# Alte Container stoppen (falls vorhanden)
echo "Stoppe alte Container..."
docker-compose down 2>/dev/null

# Container starten
echo "Starte Container..."
docker-compose up -d

# Warten bis Container gestartet sind
echo "Warte auf Container-Start..."
sleep 5

# Status anzeigen
echo ""
echo "=== Container-Status ==="
docker-compose ps

echo ""
echo "=== Logs (letzte 20 Zeilen) ==="
docker-compose logs --tail=20

echo ""
echo "=== Deployment abgeschlossen ==="
echo "n8n sollte jetzt erreichbar sein unter: http://n8n-ivan.go-ecommerce.de/"
echo ""
echo "Nützliche Befehle:"
echo "  Logs anzeigen:    docker-compose logs -f"
echo "  Status prüfen:    docker-compose ps"
echo "  Container stoppen: docker-compose down"
echo "  Container neu starten: docker-compose restart"

