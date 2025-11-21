#!/bin/sh
# Script to create n8n owner account using CLI

echo "Waiting for n8n to be ready..."
max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if wget -q --spider http://n8n:5678/healthz 2>/dev/null; then
        echo "n8n is ready!"
        break
    fi
    attempt=$((attempt + 1))
    if [ $((attempt % 5)) -eq 0 ]; then
        echo "Waiting for n8n... (attempt $attempt/$max_attempts)"
    fi
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: n8n did not become ready in time"
    exit 1
fi

# Wait a bit more for n8n to fully initialize database
echo "Waiting for n8n database to initialize..."
sleep 15

echo "Creating owner account..."
export N8N_USER_FOLDER=/home/node/.n8n
n8n user:create \
    --email="${N8N_DEFAULT_EMAIL:-Ivan.Levshyn@go-ecommerce.de}" \
    --password="${N8N_DEFAULT_PASSWORD:-05012005 Ivan}" \
    --firstName="${N8N_DEFAULT_FIRST_NAME:-Ivan}" \
    --lastName="${N8N_DEFAULT_LAST_NAME:-Levshyn}"

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "✓ Owner account created successfully!"
    echo "  Email: ${N8N_DEFAULT_EMAIL:-Ivan.Levshyn@go-ecommerce.de}"
    echo "  Password: ${N8N_DEFAULT_PASSWORD:-05012005 Ivan}"
elif [ $exit_code -eq 1 ]; then
    echo "✓ Owner account already exists (this is OK)"
else
    echo "Note: Account creation returned exit code $exit_code"
fi
