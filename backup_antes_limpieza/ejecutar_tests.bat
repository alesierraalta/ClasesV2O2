@echo off
start cmd.exe /k "cd /d %~dp0 && python -m pytest --cov=notifications --cov-report=term-missing tests/test_notifications.py -v"
