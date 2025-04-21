#!/bin/bash
echo "Ejecutando pruebas..."
cd "$(dirname "$0")"
cd tests
python run_tests.py
cd ..
