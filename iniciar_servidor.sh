#!/bin/bash
# Iniciar el servidor Django accesible desde la red local y Tailscale
cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
    echo "Error: El entorno virtual 'venv' no existe. Ejecuta primero ./instalar_dependencias.sh"
    exit 1
fi

source venv/bin/activate
echo "=========================================================="
echo "Iniciando Peluquería Lorena en http://0.0.0.0:8000/"
echo "Accesible en la red Tailscale vía: http://100.82.23.52:8000/"
echo "=========================================================="
python manage.py runserver 0.0.0.0:8000
