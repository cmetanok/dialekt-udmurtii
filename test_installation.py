# test_installation.py
import sys
import subprocess
import importlib.metadata

print("=" * 60)
print("🐍 ПРОВЕРКА УСТАНОВКИ PYTHON ПАКЕТОВ")
print("=" * 60)

# Информация о Python
print(f"\n📌 Python version: {sys.version}")
print(f"📌 Python executable: {sys.executable}")
print(f"📌 Virtual env: {'venv' in sys.prefix}")

# Список пакетов для проверки
packages = [
    'streamlit',
    'pandas',
    'gspread',
    'folium',
    'streamlit_folium',
    'plotly',
    'google.auth',
    'requests'
]

print("\n📦 ПРОВЕРКА ПАКЕТОВ:")
print("-" * 60)

# Способ 1: Проверка через importlib (Python 3.8+)
for package in packages:
    try:
        # Специальная обработка для пакетов с точками
        if package == 'streamlit_folium':
            import_name = 'streamlit_folium'
            package_name = 'streamlit-folium'
        elif package == 'google.auth':
            import_name = 'google.auth'
            package_name = 'google-auth'
        else:
            import_name = package
            package_name = package

        # Пытаемся импортировать
        __import__(import_name)

        # Пытаемся получить версию
        try:
            version = importlib.metadata.version(package_name)
            print(f"✅ {package:20} версия {version}")
        except:
            try:
                # Альтернативный способ для некоторых пакетов
                if package == 'streamlit':
                    import streamlit

                    version = streamlit.__version__
                elif package == 'pandas':
                    import pandas

                    version = pandas.__version__
                elif package == 'folium':
                    import folium

                    version = folium.__version__
                elif package == 'plotly':
                    import plotly

                    version = plotly.__version__
                else:
                    version = "установлен"
                print(f"✅ {package:20} версия {version}")
            except:
                print(f"✅ {package:20} установлен (версия неизвестна)")

    except ImportError as e:
        print(f"❌ {package:20} НЕ УСТАНОВЛЕН")
        print(f"   Ошибка: {e}")

print("-" * 60)

# Проверка pip и установленных пакетов
print("\n🔍 ВСЕ УСТАНОВЛЕННЫЕ ПАКЕТЫ (через pip):")
print("-" * 60)

try:
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'list'],
        capture_output=True,
        text=True
    )
    lines = result.stdout.split('\n')
    for line in lines[:15]:  # Первые 15 строк
        print(f"  {line}")
    if len(lines) > 15:
        print(f"  ... и еще {len(lines) - 15} пакетов")
except Exception as e:
    print(f"  Не удалось получить список: {e}")

print("\n" + "=" * 60)
print("🎉 ПРОВЕРКА ЗАВЕРШЕНА!")
print("=" * 60)

# Простой тест импорта всех пакетов
print("\n🔄 ФИНАЛЬНЫЙ ТЕСТ ИМПОРТА:")
try:
    import streamlit as st

    print("✅ streamlit - OK")

    import pandas as pd

    print("✅ pandas - OK")

    import gspread

    print("✅ gspread - OK")

    import folium

    print("✅ folium - OK")

    import streamlit_folium

    print("✅ streamlit_folium - OK")

    import plotly.express as px

    print("✅ plotly - OK")

    from google.oauth2 import service_account

    print("✅ google.auth - OK")

    import requests

    print("✅ requests - OK")

    print("\n✨ ВСЕ ПАКЕТЫ УСПЕШНО ИМПОРТИРУЮТСЯ!")

except Exception as e:
    print(f"\n❌ Ошибка при импорте: {e}")