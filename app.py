import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from datetime import datetime
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
import re

# Импорт из geocoder.py
from geocoder import LocationGeocoder, DARYA_QUESTIONS, QUESTION_TO_NUMBER


# -------------------------------
# ФУНКЦИЯ ДЛЯ ОБРАБОТКИ ВВОДА КООРДИНАТ
# -------------------------------
def process_coordinate_input(value):
    """Преобразует введенное значение координаты в число с точкой"""
    if value is None:
        return None

    # Преобразуем в строку
    value_str = str(value).strip()

    # Заменяем запятую на точку
    value_str = value_str.replace(',', '.')

    # Удаляем пробелы
    value_str = value_str.replace(' ', '')

    # Пробуем преобразовать в число
    try:
        return float(value_str)
    except ValueError:
        return None


# -------------------------------
# 1. НАСТРОЙКА СТРАНИЦЫ
# -------------------------------
st.set_page_config(
    page_title="Диалектологическая карта Удмуртии",
    page_icon="🗺️",
    layout="wide"
)

# Инициализация session state
if 'edit_mode' not in st.session_state:
    st.session_state['edit_mode'] = False
if 'new_lat' not in st.session_state:
    st.session_state['new_lat'] = 57.0
if 'new_lon' not in st.session_state:
    st.session_state['new_lon'] = 53.0
if 'show_isoglosses' not in st.session_state:
    st.session_state['show_isoglosses'] = True
if 'show_templates' not in st.session_state:
    st.session_state['show_templates'] = False
if 'selected_question_num' not in st.session_state:
    st.session_state['selected_question_num'] = None
if 'selected_question_text' not in st.session_state:
    st.session_state['selected_question_text'] = None
if 'template_question' not in st.session_state:
    st.session_state['template_question'] = None
if 'auto_lat' not in st.session_state:
    st.session_state['auto_lat'] = 57.0
if 'auto_lon' not in st.session_state:
    st.session_state['auto_lon'] = 53.0

# Заголовок
st.markdown("""
    <h1 style='text-align: center; color: #2e6b8c;'>
        🗺️ Интерактивная карта русских говоров Удмуртии
    </h1>
    <p style='text-align: center; font-style: italic; color: #666;'>
        Данные из программы ДАРЯ (Диалектологический атлас русского языка)
    </p>
    <hr>
""", unsafe_allow_html=True)


# -------------------------------
# 2. КЛАСС ДЛЯ УПРАВЛЕНИЯ ИЗОГЛОССАМИ
# -------------------------------
class IsoglossManager:
    def __init__(self):
        """Управление изоглоссами на карте"""
        pass

    def get_points_for_question(self, df, question, answer):
        """Получает все точки для определенного вопроса и ответа"""
        points = []
        for q_col in [c for c in df.columns if c.startswith('question_')]:
            mask = (df[q_col] == question)
            if mask.any():
                ans_col = q_col.replace('question_', 'answer_')
                if ans_col in df.columns:
                    answer_mask = (df[ans_col] == answer) if answer else mask
                    mask = mask & answer_mask

            for idx, row in df[mask].iterrows():
                if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                    points.append([row['latitude'], row['longitude']])

        return points

    def create_convex_hull(self, points):
        """Создает выпуклую оболочку для набора точек"""
        if len(points) < 3:
            return None

        points_array = np.array(points)
        try:
            hull = ConvexHull(points_array)
            hull_points = points_array[hull.vertices].tolist()
            hull_points.append(hull_points[0])
            return hull_points
        except:
            return None

    def add_isoglosses_to_map(self, m, df, selected_question):
        """Добавляет изоглоссы на карту для выбранного вопроса"""
        if not selected_question or selected_question == "Все вопросы":
            return m

        answers = set()
        for q_col in [c for c in df.columns if c.startswith('question_')]:
            mask = df[q_col] == selected_question
            if mask.any():
                ans_col = q_col.replace('question_', 'answer_')
                if ans_col in df.columns:
                    answers.update(df.loc[mask, ans_col].dropna().unique())

        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'darkred', 'darkblue']

        for i, answer in enumerate(answers):
            points = self.get_points_for_question(df, selected_question, answer)
            hull_points = self.create_convex_hull(points)

            if hull_points and len(hull_points) >= 3:
                color = colors[i % len(colors)]

                folium.Polygon(
                    locations=hull_points,
                    popup=f"Ареал: {answer}",
                    tooltip=f"Изоглосса: {answer}",
                    color=color,
                    weight=2,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.2,
                    dash_array='5, 5'
                ).add_to(m)

                folium.PolyLine(
                    locations=hull_points,
                    color=color,
                    weight=3,
                    opacity=0.9,
                    dash_array='5, 5'
                ).add_to(m)

        return m


# -------------------------------
# 3. ФУНКЦИИ ДЛЯ РАБОТЫ С ВОПРОСАМИ
# -------------------------------
def get_unique_questions(df):
    """Получает список всех вопросов из таблицы с номерами ДАРЯ"""
    questions = set()
    for col in df.columns:
        if col.startswith('question_'):
            for q in df[col].dropna().unique():
                if q in QUESTION_TO_NUMBER:
                    questions.add(f"[№{QUESTION_TO_NUMBER[q]}] {q}")
                else:
                    questions.add(q)
    return sorted(list(questions))


def get_original_question(display_question):
    """Извлекает оригинальный вопрос из отображаемого с номером"""
    if display_question.startswith("[№"):
        return display_question.split("] ", 1)[1]
    return display_question


def show_question_templates():
    """Показывает интерфейс для выбора шаблонов вопросов из ДАРЯ"""
    st.markdown("### 📋 Шаблоны вопросов из ДАРЯ")
    st.info("Выберите вопрос из списка, чтобы автоматически вставить его в поля ниже")

    search_q = st.text_input("🔍 Поиск вопроса", placeholder="например: произношение, лексика, синтаксис...")

    filtered_questions = DARYA_QUESTIONS.items()
    if search_q:
        filtered_questions = [(num, q) for num, q in filtered_questions
                              if search_q.lower() in q.lower()]

    cols = st.columns(3)
    for i, (num, question) in enumerate(filtered_questions):
        with cols[i % 3]:
            if st.button(f"📌 №{num}: {question[:40]}...", key=f"q_{num}"):
                st.session_state['selected_question_num'] = num
                st.session_state['selected_question_text'] = question
                st.success(f"✅ Выбран вопрос: №{num} - {question}")

    if st.session_state.get('selected_question_text'):
        st.markdown("---")
        st.markdown(
            f"**Выбранный вопрос:** №{st.session_state['selected_question_num']} - {st.session_state['selected_question_text']}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 Вставить в следующее поле вопроса", use_container_width=True):
                st.session_state['template_question'] = st.session_state['selected_question_text']
                st.rerun()


# -------------------------------
# 4. ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ
# -------------------------------
@st.cache_data(ttl=60)
def load_data_from_gsheet():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

        try:
            if "gcp" in st.secrets:
                creds_info = {
                    "type": st.secrets["gcp"]["type"],
                    "project_id": st.secrets["gcp"]["project_id"],
                    "private_key_id": st.secrets["gcp"]["private_key_id"],
                    "private_key": st.secrets["gcp"]["private_key"],
                    "client_email": st.secrets["gcp"]["client_email"],
                    "client_id": st.secrets["gcp"]["client_id"],
                    "auth_uri": st.secrets["gcp"]["auth_uri"],
                    "token_uri": st.secrets["gcp"]["token_uri"],
                    "auth_provider_x509_cert_url": st.secrets["gcp"]["auth_provider_x509_cert_url"],
                    "client_x509_cert_url": st.secrets["gcp"]["client_x509_cert_url"]
                }
                creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
                client = gspread.authorize(creds)
                SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"
                sheet = client.open_by_key(SHEET_ID)
                worksheet = sheet.get_worksheet(0)
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)

                if 'latitude' in df.columns:
                    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
                if 'longitude' in df.columns:
                    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
                return df
        except Exception as e:
            st.warning(f"Не удалось загрузить из секретов: {e}")

        cred_path = Path(".streamlit/google-credentials.json")
        if cred_path.exists():
            creds = Credentials.from_service_account_file(str(cred_path), scopes=scopes)
            client = gspread.authorize(creds)
            SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"
            sheet = client.open_by_key(SHEET_ID)
            worksheet = sheet.get_worksheet(0)
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            if 'latitude' in df.columns:
                df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
            if 'longitude' in df.columns:
                df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            return df
        else:
            return create_demo_data()

    except Exception as e:
        st.error(f"❌ Ошибка загрузки данных: {e}")
        return create_demo_data()


def create_demo_data():
    data = {
        'id': [1, 2, 3],
        'region': ['Удмуртская Республика', 'Удмуртская Республика', 'Кировская область'],
        'district': ['Завьяловский район', 'Игринский район', 'Слободской район'],
        'settlement': ['д. Русская Лоза', 'с. Зура', 'д. Бобино'],
        'settlement_type': ['деревня', 'село', 'деревня'],
        'latitude': [56.8165, 57.5269, 58.5589],
        'longitude': [53.3895, 53.0247, 50.3395],
        'question_1': ['Фонетика: произношение [г]', 'Фонетика: произношение [г]', 'Фонетика: произношение [г]'],
        'answer_1': ['[ɡ] взрывной', '[ɣ] фрикативный', '[ɡ] взрывной'],
    }
    return pd.DataFrame(data)


# -------------------------------
# 5. ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ
# -------------------------------
def get_answers_for_question(df, question):
    answers = set()
    for q_col in [c for c in df.columns if c.startswith('question_')]:
        mask = df[q_col] == question
        if mask.any():
            ans_col = q_col.replace('question_', 'answer_')
            if ans_col in df.columns:
                answers.update(df.loc[mask, ans_col].dropna().unique())
    return sorted(list(answers))


def filter_by_question(df, question, answer=None):
    if not question or question == "Все вопросы":
        return df

    mask = pd.Series(False, index=df.index)
    for q_col in [c for c in df.columns if c.startswith('question_')]:
        q_mask = df[q_col] == question
        if answer and answer != "Все ответы":
            ans_col = q_col.replace('question_', 'answer_')
            if ans_col in df.columns:
                q_mask = q_mask & (df[ans_col] == answer)
        mask = mask | q_mask
    return df[mask]


def search_by_linguistic_unit(df, search_term):
    if not search_term:
        return df

    search_term_lower = search_term.lower().strip()
    mask = pd.Series(False, index=df.index)

    for col in df.columns:
        if col.startswith('answer_'):
            col_str = df[col].astype(str).str.lower()
            mask = mask | col_str.str.contains(search_term_lower, na=False)

    return df[mask]


def get_unique_linguistic_units(df):
    units = set()
    for col in df.columns:
        if col.startswith('answer_'):
            for value in df[col].dropna().unique():
                units.add(str(value))
    return sorted(list(units))


def get_color_for_answer(question, answer):
    color_map = {
        '[ɡ] взрывной': 'red',
        '[ɣ] фрикативный': 'green',
        'твердое [ца]': 'orange',
        'мягкое [ц\'а]': 'purple',
        '-ут': 'blue',
        '-ат/-ят': 'darkblue',
        'изба': 'lightgreen',
        'хата': 'lightred',
        'у меня есть': 'cadetblue',
        'у мене є': 'pink',
    }
    return color_map.get(str(answer), 'gray')


# -------------------------------
# 6. ФУНКЦИЯ КОНВЕРТАЦИИ КООРДИНАТ
# -------------------------------
def convert_dms_to_decimal(dms_string):
    """Конвертирует строку с градусами в десятичные градусы"""
    if not dms_string:
        return None

    # Проверяем, может уже десятичные
    try:
        val = float(dms_string.replace(',', '.'))
        return val
    except:
        pass

    # Извлекаем числовые значения
    numbers = re.findall(r'(\d+(?:\.\d+)?)', dms_string)

    if not numbers:
        return None

    numbers = [float(n) for n in numbers]

    # Определяем формат
    if len(numbers) == 1:
        decimal = numbers[0]
    elif len(numbers) == 2:
        decimal = numbers[0] + numbers[1] / 60
    else:
        decimal = numbers[0] + numbers[1] / 60 + numbers[2] / 3600

    # Определяем направление
    is_south = 'ю.ш.' in dms_string or 'южн' in dms_string or 'S' in dms_string.upper()
    is_west = 'з.д.' in dms_string or 'зап' in dms_string or 'W' in dms_string.upper()

    if is_south or is_west:
        decimal = -decimal

    return round(decimal, 6)


# -------------------------------
# 7. ФУНКЦИЯ ДЛЯ ДОБАВЛЕНИЯ В GOOGLE SHEETS
# -------------------------------
def add_to_google_sheets(data_dict):
    """Добавляет новую запись в Google Sheets"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

        try:
            if "gcp" in st.secrets:
                creds_info = {
                    "type": st.secrets["gcp"]["type"],
                    "project_id": st.secrets["gcp"]["project_id"],
                    "private_key_id": st.secrets["gcp"]["private_key_id"],
                    "private_key": st.secrets["gcp"]["private_key"],
                    "client_email": st.secrets["gcp"]["client_email"],
                    "client_id": st.secrets["gcp"]["client_id"],
                    "auth_uri": st.secrets["gcp"]["auth_uri"],
                    "token_uri": st.secrets["gcp"]["token_uri"],
                    "auth_provider_x509_cert_url": st.secrets["gcp"]["auth_provider_x509_cert_url"],
                    "client_x509_cert_url": st.secrets["gcp"]["client_x509_cert_url"]
                }
                creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            else:
                cred_path = Path(".streamlit/google-credentials.json")
                if not cred_path.exists():
                    return False, "Файл с ключами не найден"
                creds = Credentials.from_service_account_file(str(cred_path), scopes=scopes)
        except Exception as e:
            cred_path = Path(".streamlit/google-credentials.json")
            if not cred_path.exists():
                return False, f"Ошибка авторизации: {e}"
            creds = Credentials.from_service_account_file(str(cred_path), scopes=scopes)

        client = gspread.authorize(creds)
        SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.get_worksheet(0)

        all_data = worksheet.get_all_values()

        if len(all_data) > 1:
            last_id = int(all_data[-1][0]) if all_data[-1][0].isdigit() else 0
            new_id = last_id + 1
        else:
            new_id = 1

        # Функция для форматирования координат (замена запятой на точку)
        def format_coordinate(value):
            if value is None or value == "":
                return ""
            # Преобразуем в строку
            value_str = str(value)
            # Заменяем запятую на точку
            value_str = value_str.replace(',', '.')
            # Пробуем преобразовать в число и обратно для чистоты формата
            try:
                return str(float(value_str))
            except:
                return value_str

        # Формируем новую строку с правильным форматированием координат
        new_row = [
            new_id,  # id
            data_dict.get('region', ''),  # region
            data_dict.get('district', ''),  # district
            data_dict.get('settlement', ''),  # settlement
            data_dict.get('type', ''),  # settlement_type
            format_coordinate(data_dict.get('latitude', '')),  # latitude (с точкой!)
            format_coordinate(data_dict.get('longitude', '')),  # longitude (с точкой!)
            data_dict.get('altitude', ''),  # altitude
            data_dict.get('question_1', ''),  # question_1
            data_dict.get('answer_1', ''),  # answer_1
            data_dict.get('question_2', ''),  # question_2
            data_dict.get('answer_2', ''),  # answer_2
            data_dict.get('question_3', ''),  # question_3
            data_dict.get('answer_3', ''),  # answer_3
            data_dict.get('question_4', ''),  # question_4
            data_dict.get('answer_4', ''),  # answer_4
            data_dict.get('question_5', ''),  # question_5
            data_dict.get('answer_5', ''),  # answer_5
        ]

        worksheet.append_row(new_row)
        return True, new_id

    except Exception as e:
        return False, str(e)


# -------------------------------
# 8. СОЗДАНИЕ КАРТЫ С ИЗОГЛОССАМИ
# -------------------------------
def create_map(df, selected_question=None, selected_answer=None, show_isoglosses=True):
    center_lat = 57.0
    center_lon = 53.0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles='OpenStreetMap')

    if show_isoglosses and selected_question and selected_question != "Все вопросы":
        iso_manager = IsoglossManager()
        m = iso_manager.add_isoglosses_to_map(m, df, selected_question)

    for idx, row in df.iterrows():
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            color = 'blue'
            settlement = row['settlement'] if 'settlement' in row.index else ''
            settlement_type = row['settlement_type'] if 'settlement_type' in row.index and pd.notna(
                row['settlement_type']) else ''
            district = row['district'] if 'district' in row.index and pd.notna(row['district']) else ''
            region = row['region'] if 'region' in row.index and pd.notna(row['region']) else ''

            tooltip = f"{settlement}"
            popup_text = f"""
                <b>{settlement}</b><br>
                <i>{settlement_type}</i><br>
                <b>Район:</b> {district}<br>
                <b>Регион:</b> {region}<br>
                <hr>
            """

            if selected_question and selected_question != "Все вопросы":
                for q_col in [c for c in df.columns if c.startswith('question_')]:
                    if row[q_col] == selected_question:
                        ans_col = q_col.replace('question_', 'answer_')
                        if ans_col in df.columns:
                            answer = row[ans_col]
                            tooltip += f" - {answer}"
                            popup_text += f"<b>Вопрос:</b> {selected_question}<br>"
                            popup_text += f"<b>Ответ:</b> {answer}<br>"
                            color = get_color_for_answer(selected_question, answer)
                            break

            popup_text += "<hr><b>Все диалектные особенности:</b><br>"
            for q_col in [c for c in df.columns if c.startswith('question_')]:
                if pd.notna(row[q_col]):
                    ans_col = q_col.replace('question_', 'answer_')
                    if ans_col in df.columns and pd.notna(row[ans_col]):
                        popup_text += f"• {row[q_col]}: <b>{row[ans_col]}</b><br>"

            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=tooltip,
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)

    return m


# -------------------------------
# 9. ИНТЕРФЕЙС РЕДАКТИРОВАНИЯ
# -------------------------------
def show_editor_interface(df):
    st.markdown("## ✏️ Режим редактирования данных")
    st.markdown("---")

    # Ссылка на Google Таблицу
    st.markdown("""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
        <b>📊 Прямой доступ к Google Таблице:</b><br>
        <a href="https://docs.google.com/spreadsheets/d/11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM/edit?gid=0#gid=0" target="_blank">
            🔗 Открыть Google Таблицу для ручного редактирования
        </a><br>
        <small>Вы можете редактировать данные напрямую в таблице. Изменения появятся на карте через 60 секунд.</small>
    </div>
    """, unsafe_allow_html=True)

    geocoder = LocationGeocoder()

    # Кнопка показа шаблонов (вне формы)
    if st.button("📋 Показать шаблоны вопросов ДАРЯ"):
        st.session_state['show_templates'] = not st.session_state.get('show_templates', False)

    if st.session_state.get('show_templates', False):
        show_question_templates()
        st.markdown("---")

    # ========== ФОРМА ДОБАВЛЕНИЯ НОВОГО ПУНКТА ==========
    with st.form("add_settlement_form"):
        st.markdown("### ➕ Добавление нового населенного пункта")
        st.info("Заполните информацию. Координаты можно найти автоматически или ввести вручную.")

        col1, col2 = st.columns(2)

        with col1:
            new_region = st.text_input("Регион *", value="Удмуртская Республика")
            new_district = st.text_input("Район *", placeholder="Завьяловский район")
            new_settlement = st.text_input("Населенный пункт *", placeholder="д. Новая Деревня")
            new_type = st.selectbox("Тип населенного пункта", ["деревня", "село", "поселок", "город"])


        with col2:
            st.markdown("#### 🌍 Координаты")

            # Кнопка автоматического поиска координат (submit button)
            search_clicked = st.form_submit_button("🔍 Найти координаты автоматически")

            if search_clicked and new_settlement:
                with st.spinner("Поиск координат..."):
                    result, wiki_info = geocoder.get_coordinates(new_settlement, new_district, new_region)

                    if result:
                        lat, lon = result
                        st.session_state['auto_lat'] = lat
                        st.session_state['auto_lon'] = lon
                        st.success(f"✅ Найдено: {lat:.6f}, {lon:.6f}")
                    else:
                        st.error("❌ Не найдено в базе данных")
                        if wiki_info:
                            st.info(f"💡 Попробуйте найти координаты на Википедии: [ссылка]({wiki_info['page_url']})")

            # Поля для ручного ввода координат
            st.markdown("**Введите координаты вручную:**")
            st.caption("💡 Поддерживаются оба формата: точка (56.253333) или запятая (56,253333)")

            col_lat, col_lon = st.columns(2)
            with col_lat:
                lat_value = st.session_state.get('auto_lat', st.session_state.get('new_lat', 57.0))
                # Преобразуем число в строку и заменяем точку на запятую для отображения
                if isinstance(lat_value, (int, float)):
                    lat_display = str(lat_value).replace('.', ',')
                else:
                    lat_display = str(lat_value).replace(',', '.')

                lat_input = st.text_input(
                    "Широта",
                    value=lat_display,
                    key="lat_input"
                )
                # Обрабатываем ввод - заменяем запятую на точку
                processed_lat = lat_input.replace(',', '.')
                try:
                    new_lat = float(processed_lat)
                    st.session_state['new_lat'] = new_lat
                except ValueError:
                    st.error("❌ Неверный формат широты")
                    new_lat = 57.0

            with col_lon:
                lon_value = st.session_state.get('auto_lon', st.session_state.get('new_lon', 53.0))
                if isinstance(lon_value, (int, float)):
                    lon_display = str(lon_value).replace('.', ',')
                else:
                    lon_display = str(lon_value).replace(',', '.')

                lon_input = st.text_input(
                    "Долгота",
                    value=lon_display,
                    key="lon_input"
                )
                processed_lon = lon_input.replace(',', '.')
                try:
                    new_lon = float(processed_lon)
                    st.session_state['new_lon'] = new_lon
                except ValueError:
                    st.error("❌ Неверный формат долготы")
                    new_lon = 53.0

        # Диалектные особенности
        st.markdown("#### 📝 Диалектные особенности")

        default_question = st.session_state.get('template_question', '')
        num_questions = st.number_input("Количество вопросов", min_value=1, max_value=10, value=3)

        questions_data = {}
        question_options = list(DARYA_QUESTIONS.values())

        for i in range(int(num_questions)):
            col_q, col_a = st.columns(2)
            with col_q:
                q_index = 0
                if default_question and default_question in question_options:
                    q_index = question_options.index(default_question) + 1
                q = st.selectbox(
                    f"Вопрос {i + 1}",
                    [""] + question_options,
                    index=q_index,
                    key=f"new_q_{i}"
                )
            with col_a:
                a = st.text_input(f"Ответ {i + 1}", key=f"new_a_{i}")
            if q and a:
                questions_data[f"question_{i + 1}"] = q
                questions_data[f"answer_{i + 1}"] = a

        # Очищаем шаблон после использования
        if st.session_state.get('template_question'):
            st.session_state['template_question'] = None

        # Кнопка отправки формы
        submitted = st.form_submit_button("✅ Добавить населенный пункт в Google Таблицу", type="primary",
                                          use_container_width=True)

        if submitted:
            if new_region and new_district and new_settlement:
                new_data = {
                    "region": new_region,
                    "district": new_district,
                    "settlement": new_settlement,
                    "type": new_type,
                    "latitude": new_lat,
                    "longitude": new_lon,
                    **questions_data
                }

                with st.spinner("Добавление данных в Google Таблицу..."):
                    success, result = add_to_google_sheets(new_data)

                    if success:
                        st.success(f"✅ Пункт '{new_settlement}' успешно добавлен в Google Таблицу! (ID: {result})")
                        st.info(
                            "🔄 Данные появятся на карте через 60 секунд (или нажмите 'Обновить данные' на главной странице)")

                        # Очищаем session state
                        st.session_state['auto_lat'] = 57.0
                        st.session_state['auto_lon'] = 53.0
                        st.session_state['new_lat'] = 57.0
                        st.session_state['new_lon'] = 53.0
                        st.session_state['selected_question_num'] = None
                        st.session_state['selected_question_text'] = None

                        st.rerun()
                    else:
                        st.error(f"❌ Ошибка при добавлении: {result}")
                        st.info("Вы можете добавить данные вручную через Google Таблицу по ссылке выше")
            else:
                st.error("❌ Заполните обязательные поля (*)")

    # ========== КОНВЕРТЕР КООРДИНАТ (отдельный блок, не исчезает) ==========
    st.markdown("---")
    st.markdown("## Конвертер координат (градусы → десятичные градусы)")
    st.info(
        "Если координаты не найдены автоматически, скопируйте их из Википедии и сконвертируйте здесь. Результат можно скопировать в поля выше.")

    conv_col1, conv_col2 = st.columns(2)

    with conv_col1:
        dms_lat_input = st.text_input(
            "Широта в градусах",
            placeholder='Пример: 56°51′22″ с.ш. или 56.8563',
            key="dms_lat_main"
        )

    with conv_col2:
        dms_lon_input = st.text_input(
            "Долгота в градусах",
            placeholder='Пример: 53°12′41″ в.д. или 53.2115',
            key="dms_lon_main"
        )

    # Кнопка конвертации
    if st.button("🔄 Конвертировать координаты", key="convert_main_btn"):
        conv_lat = convert_dms_to_decimal(dms_lat_input)
        conv_lon = convert_dms_to_decimal(dms_lon_input)

        if conv_lat is not None and conv_lon is not None:
            st.success(f"### Результат конвертации:")
            st.code(f"Широта: {conv_lat}\nДолгота: {conv_lon}", language="text")
            st.info("💡 Скопируйте эти значения и вставьте в поля 'Широта' и 'Долгота' в форме выше")

            # Кнопка для автоматической вставки
            if st.button("📌 Автоматически вставить в форму", key="auto_insert_btn"):
                st.session_state['auto_lat'] = conv_lat
                st.session_state['auto_lon'] = conv_lon
                st.session_state['new_lat'] = conv_lat
                st.session_state['new_lon'] = conv_lon
                st.success("✅ Координаты вставлены в форму! Продолжите заполнение.")
                st.rerun()
        else:
            if conv_lat is None:
                st.error("❌ Не удалось распознать широту. Пример: 56°51′22″ с.ш. или 56.8563")
            if conv_lon is None:
                st.error("❌ Не удалось распознать долготу. Пример: 53°12′41″ в.д. или 53.2115")

    # Примеры для быстрой вставки
    st.markdown("**📋 Примеры для копирования (нажмите на пример - он скопируется в поля выше):**")

    examples_col1, examples_col2, examples_col3 = st.columns(3)

    with examples_col1:
        if st.button("📍 Ижевск (56°51′ с.ш., 53°12′ в.д.)"):
            st.session_state['dms_lat_main'] = "56°51′00″ с.ш."
            st.session_state['dms_lon_main'] = "53°12′00″ в.д."
            st.rerun()

    with examples_col2:
        if st.button("📍 Воткинск (57°03′ с.ш., 53°59′ в.д.)"):
            st.session_state['dms_lat_main'] = "57°03′00″ с.ш."
            st.session_state['dms_lon_main'] = "53°59′00″ в.д."
            st.rerun()

    with examples_col3:
        if st.button("📍 Глазов (58°08′ с.ш., 52°40′ в.д.)"):
            st.session_state['dms_lat_main'] = "58°08′00″ с.ш."
            st.session_state['dms_lon_main'] = "52°40′00″ в.д."
            st.rerun()

    # Дополнительные примеры
    examples_col4, examples_col5, examples_col6 = st.columns(3)

    with examples_col4:
        if st.button("📍 Сарапул (56°28′ с.ш., 53°48′ в.д.)"):
            st.session_state['dms_lat_main'] = "56°28′00″ с.ш."
            st.session_state['dms_lon_main'] = "53°48′00″ в.д."
            st.rerun()

    with examples_col5:
        if st.button("📍 Можга (56°26′ с.ш., 52°13′ в.д.)"):
            st.session_state['dms_lat_main'] = "56°26′00″ с.ш."
            st.session_state['dms_lon_main'] = "52°13′00″ в.д."
            st.rerun()

    with examples_col6:
        if st.button("📍 Тарасово (Сарапульский р-н)"):
            st.session_state['dms_lat_main'] = "56°30′00″ с.ш."
            st.session_state['dms_lon_main'] = "53°45′00″ в.д."
            st.rerun()

    st.markdown("---")
    st.info(
        "💡 **Совет:** Вы также можете редактировать данные напрямую в Google Таблице по ссылке вверху страницы. Изменения появятся на карте автоматически.")


# -------------------------------
# 10. ЗАГРУЗКА ДАННЫХ
# -------------------------------
with st.spinner('🔄 Загрузка данных из Google Sheets...'):
    df = load_data_from_gsheet()

if df.empty:
    st.warning("⚠️ Нет данных для отображения")
    st.stop()

# -------------------------------
# 11. БОКОВАЯ ПАНЕЛЬ
# -------------------------------
with st.sidebar:
    st.markdown("## 🔍 Поиск и фильтры")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗺️ Карта", use_container_width=True):
            st.session_state['edit_mode'] = False
            st.rerun()
    with col2:
        if st.button("✏️ Редактор", use_container_width=True):
            st.session_state['edit_mode'] = True
            st.rerun()

    st.markdown("---")

    search_settlement = st.text_input("🔎 Найти населенный пункт", placeholder="например: Русская Лоза")

    st.markdown("---")

    st.markdown("## 🔬 Поиск по диалектным особенностям")

    search_linguistic = st.text_input(
        "🔎 Найти по слову/особенности",
        placeholder="например: взрывной, фрикативный, твердое..."
    )

    st.markdown("### Или выберите из списка:")
    linguistic_units = get_unique_linguistic_units(df)
    selected_unit = st.selectbox(
        "📋 Лингвистические единицы",
        [""] + linguistic_units,
        format_func=lambda x: "Выберите..." if x == "" else x
    )

    st.markdown("---")

    st.markdown("## 📋 Анализ по вопросам")
    questions_display = get_unique_questions(df)
    selected_question_display = st.selectbox("Выберите вопрос из программы ДАРЯ", ["Все вопросы"] + questions_display)

    if selected_question_display == "Все вопросы":
        selected_question = "Все вопросы"
    else:
        selected_question = get_original_question(selected_question_display)

    selected_answer = "Все ответы"
    if selected_question and selected_question != "Все вопросы":
        answers = ['Все ответы'] + get_answers_for_question(df, selected_question)
        selected_answer = st.selectbox("Фильтр по ответу", answers)

    st.markdown("---")

    st.session_state['show_isoglosses'] = st.checkbox("🗺️ Показывать изоглоссы (ареалы распространения)",
                                                      value=st.session_state['show_isoglosses'])

    st.markdown("---")

    regions = ['Все регионы'] + sorted(df['region'].unique().tolist())
    selected_region = st.selectbox("📍 Регион", regions)

    st.markdown("---")

    st.markdown("## 📊 Статистика")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Населенных пунктов", len(df))
        st.metric("Районов", df['district'].nunique() if 'district' in df.columns else 0)
    with col2:
        st.metric("Регионов", df['region'].nunique() if 'region' in df.columns else 0)
        st.metric("Вопросов", len(get_unique_questions(df)))

    st.markdown("---")

    with st.expander("📖 ПОЛНАЯ ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ", expanded=False):
        st.markdown("""
        ### 🗺️ РАБОТА С КАРТОЙ

        **Основные действия:**
        - **Кликните на любой маркер** - откроется окно со всей информацией
        - **Приближайте/отдаляйте карту** - используйте колесико мыши или кнопки +/-
        - **Перетаскивайте карту** - зажмите левую кнопку мыши

        ### 🔍 ПОИСК И ФИЛЬТРАЦИЯ

        **Поиск по населенному пункту:**
        - Введите название в поле "Найти населенный пункт"

        **Поиск по диалектным особенностям:**
        - Введите ключевое слово или выберите из списка

        **Анализ по вопросам ДАРЯ:**
        - Выберите вопрос (отображаются с номерами из ДАРЯ)
        - Включите "Показывать изоглоссы" для отображения ареалов

        ### ✏️ РЕЖИМ РЕДАКТИРОВАНИЯ

        **Добавление пункта:**
        1. Нажмите "✏️ Редактор"
        2. Заполните поля: регион, район, название
        3. Нажмите "🔍 Найти координаты автоматически"
        4. Выберите вопросы из шаблонов ДАРЯ
        5. Нажмите "✅ Добавить"

        **Если координаты не найдены:**
        - Используйте конвертер координат внизу страницы
        - Скопируйте координаты из Википедии
        - Нажмите "Конвертировать", затем "Автоматически вставить в форму"

        ### 🗺️ ИЗОГЛОССЫ (АРЕАЛЫ)

        Что это такое? Изоглоссы - это линии на карте, показывающие границы распространения языковых явлений.

        **Как использовать:**
        1. Выберите вопрос из списка
        2. Включите чекбокс "Показывать изоглоссы"
        3. На карте появятся цветные области - ареалы распространения
        """)

# -------------------------------
# 12. ФИЛЬТРАЦИЯ ДАННЫХ
# -------------------------------
filtered_df = df.copy()

if selected_region != "Все регионы" and 'region' in df.columns:
    filtered_df = filtered_df[filtered_df['region'] == selected_region]

if search_settlement and 'settlement' in df.columns:
    filtered_df = filtered_df[
        filtered_df['settlement'].str.contains(search_settlement, case=False, na=False)
    ]

if search_linguistic:
    filtered_df = search_by_linguistic_unit(filtered_df, search_linguistic)
    if len(filtered_df) > 0:
        st.sidebar.success(f"🔍 Найдено пунктов: {len(filtered_df)}")
    else:
        st.sidebar.warning("🔍 Ничего не найдено")

if selected_unit:
    filtered_df = search_by_linguistic_unit(filtered_df, selected_unit)
    st.sidebar.info(f"📌 Пунктов с '{selected_unit}': {len(filtered_df)}")

if selected_question and selected_question != "Все вопросы":
    filtered_df = filter_by_question(
        filtered_df,
        selected_question,
        selected_answer if selected_answer != "Все ответы" else None
    )

# -------------------------------
# 13. ОСНОВНОЙ ИНТЕРФЕЙС
# -------------------------------
if st.session_state['edit_mode']:
    show_editor_interface(df)
else:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("## 🗺️ Интерактивная карта")

        map_obj = create_map(
            filtered_df,
            selected_question if selected_question != "Все вопросы" else None,
            selected_answer if selected_answer != "Все ответы" else None,
            st.session_state['show_isoglosses']
        )

        st_folium(map_obj, width=800, height=550)

        points_with_coords = filtered_df.dropna(subset=['latitude', 'longitude'])
        st.info(
            f"📍 Показано населенных пунктов на карте: **{len(points_with_coords)}** из **{len(filtered_df)}** отфильтрованных")

    with col2:
        st.markdown("## 📋 Легенда")

        if selected_question and selected_question != "Все вопросы":
            q_number = QUESTION_TO_NUMBER.get(selected_question, "")
            if q_number:
                st.markdown(f"**Вопрос №{q_number}:** *{selected_question}*")
            else:
                st.markdown(f"**Вопрос:** *{selected_question}*")
            st.markdown("---")
            answers = get_answers_for_question(df, selected_question)
            for answer in answers:
                color = get_color_for_answer(selected_question, answer)
                st.markdown(f"<span style='color: {color}; font-size: 20px;'>●</span> {answer}", unsafe_allow_html=True)

            if st.session_state['show_isoglosses']:
                st.markdown("---")
                st.markdown("**🗺️ Изоглоссы (ареалы):**")
                st.markdown("Цветные области показывают границы распространения")
        else:
            st.markdown("""
            **Цвета маркеров по умолчанию:**

            | Цвет | Значение |
            |------|----------|
            | 🔴 Красный | взрывной [г] |
            | 🟢 Зеленый | фрикативный [ɣ] |
            | 🟠 Оранжевый | твердое [ца] |
            | 🟣 Фиолетовый | мягкое [ц'а] |
            | 🔵 Синий | стандартные окончания |
            """)

# -------------------------------
# 14. ТАБЛИЦА С ДАННЫМИ
# -------------------------------
st.markdown("---")
st.markdown("## 📋 Данные населенных пунктов")

display_cols = ['region', 'district', 'settlement']
if 'settlement_type' in df.columns:
    display_cols.append('settlement_type')
if 'latitude' in df.columns and 'longitude' in df.columns:
    display_cols.extend(['latitude', 'longitude'])

for i in range(1, 10):
    q_col = f'question_{i}'
    a_col = f'answer_{i}'
    if q_col in filtered_df.columns and a_col in filtered_df.columns:
        display_cols.extend([q_col, a_col])

st.dataframe(
    filtered_df[display_cols],
    width='stretch',
    height=350,
    hide_index=True
)

# -------------------------------
# 15. КНОПКИ ЭКСПОРТА
# -------------------------------
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("📥 Экспорт в CSV", use_container_width=True):
        csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "💾 Скачать CSV",
            csv,
            f"dialekt_udmurtii_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )

with col2:
    if st.button("🔄 Обновить данные", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# -------------------------------
# 16. ПОДВАЛ
# -------------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: small;'>
        <b>📊 Источник данных:</b> Google Sheets (программа ДАРЯ/ЛАРНГ)<br>
        <b>🔄 Автообновление:</b> данные обновляются каждые 60 секунд<br>
        <b>🗺️ Изоглоссы:</b> показывают границы распространения диалектных явлений<br>
        <b>🔍 Поиск по лемме:</b> работает по всем диалектным особенностям<br>
        <b>📝 Номера вопросов:</b> соответствуют программе ДАРЯ<br>
        <b>🌐 Конвертер координат:</b> преобразует градусы из Википедии в десятичные<br>
        <b>📌 Поддержка форматов:</b> точка (56.253333) или запятая (56,253333)<br>
        <hr>
        © Диалектологическая карта Удмуртии | Проект выполнен в рамках изучения русских говоров
    </div>
    """,
    unsafe_allow_html=True
)