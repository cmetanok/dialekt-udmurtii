# test_gsheet.py
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

print("🔌 Тестирование подключения к Google Sheets")
print("=" * 50)

# Путь к папке .streamlit
streamlit_dir = Path(".streamlit")
print(f"📁 Проверяем папку: {streamlit_dir.absolute()}")

# Проверяем, существует ли папка
if not streamlit_dir.exists():
    print(f"❌ Папка {streamlit_dir} не найдена!")
    print("Создайте папку .streamlit в корне проекта")
    exit(1)
else:
    print(f"✅ Папка .streamlit найдена")

# Ищем JSON файл с ключами
json_files = list(streamlit_dir.glob("*.json"))
print(f"\n📄 Найдено JSON файлов: {len(json_files)}")

if not json_files:
    print("❌ Нет JSON файлов в папке .streamlit!")
    print("Поместите туда скачанный JSON-ключ")
    print("\nОжидаемые файлы:")
    print("  - google-credentials.json")
    print("  - или любой другой .json файл")
    exit(1)

# Используем первый найденный JSON файл
cred_path = json_files[0]
print(f"✅ Используем файл: {cred_path.name}")

try:
    # Определяем права доступа
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    print(f"\n🔑 Загружаем credentials...")
    creds = Credentials.from_service_account_file(
        str(cred_path),
        scopes=scopes
    )
    print(f"✅ Credentials загружены")
    print(f"  • Client email: {creds.service_account_email}")

    # Авторизуемся
    print(f"\n🔌 Авторизация в Google Sheets...")
    client = gspread.authorize(creds)
    print(f"✅ Авторизация успешна")

    # ВАЖНО: ЗДЕСЬ НУЖНО ВСТАВИТЬ ID ВАШЕЙ ТАБЛИЦЫ!
    # ID таблицы берется из URL: https://docs.google.com/spreadsheets/d/***ЭТОТ_ТЕКСТ***/edit...
    SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"

    print(f"\n📊 Открываем таблицу с ID: {SHEET_ID}")
    sheet = client.open_by_key(SHEET_ID)
    print(f"✅ Таблица найдена: {sheet.title}")

    # Получаем первый лист
    worksheet = sheet.get_worksheet(0)
    print(f"✅ Открыт лист: {worksheet.title}")

    # Пробуем прочитать данные
    all_records = worksheet.get_all_records()
    print(f"📋 Найдено записей: {len(all_records)}")

    if all_records:
        print(f"\n🔍 Первые 3 записи:")
        for i, record in enumerate(all_records[:3]):
            print(f"\n  Запись {i + 1}:")
            for key, value in record.items():
                if value:  # Показываем только непустые поля
                    print(f"    {key}: {value}")
    else:
        print("📭 Таблица пуста")

    print("\n" + "=" * 50)
    print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
    print("=" * 50)

except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    print("\n🔍 Возможные причины:")
    print("1. Неправильный ID таблицы (скопируйте из URL)")
    print("2. Нет доступа у сервисного аккаунта к таблице")
    print("3. Не включены API (Sheets API и Drive API)")
    print("\n📝 Проверьте:")
    print(f"  • Client email: {creds.service_account_email if 'creds' in locals() else 'неизвестно'}")
    print(f"  • Этот email должен быть добавлен в таблицу как Редактор")