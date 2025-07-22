#!/bin/bash

# This script sets up SSL certificates for the Audio Enhancer

echo "Setting up SSL certificates for Audio Enhancer..."

# Create ssl directory if it doesn't exist
mkdir -p ssl

# Check if Let's Encrypt certificates exist for the domain
DOMAIN="tools.janbahmann.de"
LE_PATH="/etc/letsencrypt/live/$DOMAIN"

if [ -d "$LE_PATH" ]; then
    echo "Found Let's Encrypt certificates for $DOMAIN"
    cp "$LE_PATH/fullchain.pem" ssl/cert.pem
    cp "$LE_PATH/privkey.pem" ssl/key.pem
    echo "SSL certificates copied successfully!"
else
    echo "No Let's Encrypt certificates found for $DOMAIN"
    echo "Generating self-signed certificate for development..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem -out ssl/cert.pem \
        -subj "/C=DE/ST=State/L=City/O=Organization/CN=$DOMAIN"
    echo "Self-signed certificate generated!"
fi

# Set proper permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem

echo "SSL setup complete!"