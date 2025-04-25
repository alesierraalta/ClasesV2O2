"""
Script para ejecutar todas las pruebas unitarias del proyecto.
"""
import os
import sys
import unittest
import argparse

def run_all_tests():
    """Ejecuta todas las pruebas unitarias."""
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

def run_specific_test(test_module):
    """Ejecuta un módulo de pruebas específico."""
    if not test_module.startswith('test_'):
        test_module = f'test_{test_module}'
    
    if not test_module.endswith('.py'):
        test_module = f'{test_module}.py'
    
    test_path = os.path.join('tests', test_module)
    
    if not os.path.exists(test_path):
        print(f"Error: No se encontró el módulo de prueba '{test_module}'")
        return False
    
    # Importar el módulo de prueba
    module_name = test_module[:-3]  # Quitar la extensión .py
    sys.path.insert(0, 'tests')
    __import__(module_name)
    
    # Cargar y ejecutar las pruebas
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromName(module_name)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

def main():
    """Función principal para ejecutar pruebas desde la línea de comandos."""
    parser = argparse.ArgumentParser(description='Ejecutar pruebas unitarias')
    parser.add_argument('--module', '-m', help='Módulo específico de prueba a ejecutar (sin "test_" ni ".py")')
    parser.add_argument('--list', '-l', action='store_true', help='Listar los módulos de prueba disponibles')
    
    args = parser.parse_args()
    
    if args.list:
        print("Módulos de prueba disponibles:")
        for file in os.listdir('tests'):
            if file.startswith('test_') and file.endswith('.py'):
                print(f"  - {file[5:-3]}")  # Mostrar sin "test_" ni ".py"
        return True
    
    if args.module:
        success = run_specific_test(args.module)
    else:
        success = run_all_tests()
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
