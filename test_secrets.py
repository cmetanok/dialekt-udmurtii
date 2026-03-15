# test_secrets.py
import streamlit as st
from pathlib import Path
import json

print("🔐 Проверка Streamlit secrets")
print("=" * 50)

# Проверяем файл secrets.toml
secrets_path = Path(".streamlit/secrets.toml")
print(f"📁 Проверяем файл: {secrets_path.absolute()}")

if not secrets_path.exists():
    print(f"❌ Файл {secrets_path} не найден!")
    print("Создайте его позже, когда будете настраивать Streamlit")
else:
    print(f"✅ Файл найден, размер: {secrets_path.stat().st_size} байт")

    # Показываем содержимое (без sensitive данных)
    print("\n📄 Содержимое файла:")
    with open(secrets_path, 'r') as f:
        content = f.read()
        # Маскируем ключи для безопасности
        if 'private_key' in content:
            content = content.replace(
                content[content.find('private_key'):content.find('-----END') + 50],
                'private_key = "***скрыто***"'
            )
        print(content)