#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

echo "======================================"
echo "Iniciando la instalación de dependencias"
echo "======================================"

# 1. Dependencias del Backend (Python)
echo ""
echo "-> [1/2] Instalando dependencias del Backend (Python)..."
cd backend

# Crear un entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual (venv)..."
    python3 -m venv venv
fi

# Activar el entorno virtual e instalar los requerimientos
echo "Activando entorno virtual e instalando paquetes desde requirements.txt..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Volver a la raíz del proyecto
cd ..
echo "¡Dependencias del backend instaladas correctamente!"

# 2. Dependencias del Frontend (Node.js)
echo ""
echo "-> [2/2] Instalando dependencias del Frontend (Node.js)..."
cd frontend

# Instalar los paquetes con npm
echo "Ejecutando npm install..."
npm install

# Volver a la raíz del proyecto
cd ..
echo "¡Dependencias del frontend instaladas correctamente!"

echo ""
echo "======================================"
echo "Instalación completada exitosamente."
echo "======================================"
