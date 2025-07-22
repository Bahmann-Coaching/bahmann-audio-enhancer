#!/bin/bash

# Einfaches Deployment Check Skript

echo "Audio Enhancer Deployment Check"
echo "==============================="
echo ""

cd /opt/audio-enhancer

echo "1. Docker Container Status:"
docker ps -a | grep bahmann-audio-enhancer

echo ""
echo "2. Container Logs (letzte 30 Zeilen):"
docker logs --tail 30 bahmann-audio-enhancer 2>&1

echo ""
echo "3. SSL Zertifikate:"
ls -la ssl/

echo ""
echo "4. Port Check:"
netstat -tlnp | grep -E "8002|8443" || ss -tlnp | grep -E "8002|8443"

echo ""
echo "5. Docker Compose Status:"
docker compose ps

echo ""
echo "6. Versuche Container neu zu starten:"
docker compose down
docker compose up -d --build

echo ""
echo "Warte 10 Sekunden..."
sleep 10

echo ""
echo "7. Neue Container Logs:"
docker logs --tail 20 bahmann-audio-enhancer 2>&1

echo ""
echo "Fertig!"