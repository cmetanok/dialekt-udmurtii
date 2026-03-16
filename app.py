import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import plotly.express as px
from datetime import datetime
from pathlib import Path
import re
import time

# Импорт нашего геокодера из отдельного файла
from geocoder import LocationGeocoder

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
# 2. ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ
# -------------------------------
@st.cache_data(ttl=60)
def load_data_from_gsheet():
    """
    Загружает данные из Google Sheets
    """
    try:
        # Определяем права доступа - используем правильные scopes
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",  # Только чтение
            "https://www.googleapis.com/auth/drive.readonly"  # Только чтение
        ]

        # Пытаемся загрузить из секретов Streamlit Cloud
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

                # ID таблицы
                SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"

                sheet = client.open_by_key(SHEET_ID)
                worksheet = sheet.get_worksheet(0)

                data = worksheet.get_all_records()
                df = pd.DataFrame(data)

                # Обработка координат
                if 'latitude' in df.columns:
                    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
                if 'longitude' in df.columns:
                    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

                return df
        except Exception as e:
            st.warning(f"Не удалось загрузить из секретов: {e}")

        # Если не получилось с секретами, пробуем локальный файл
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
            st.error("❌ Файл .streamlit/google-credentials.json не найден!")
            return create_demo_data()

    except Exception as e:
        st.error(f"❌ Ошибка загрузки данных: {e}")
        return create_demo_data()


def load_from_local_file():
    """Загружает данные из локального файла (для разработки)"""
    try:
        # Путь к файлу с ключами
        cred_path = Path(".streamlit/google-credentials.json")

        if not cred_path.exists():
            st.error(f"❌ Файл {cred_path} не найден!")
            st.info("Поместите файл google-credentials.json в папку .streamlit")
            return create_demo_data()

        # Определяем права доступа
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Загружаем credentials из файла
        creds = Credentials.from_service_account_file(
            str(cred_path),
            scopes=scopes
        )

        # Авторизуемся
        client = gspread.authorize(creds)

        # ID вашей таблицы
        SHEET_ID = "11hjMbvXri7tRfD_201wQwtnzV54S7xBFTxAGmJEtasM"  # Ваш ID!

        # Открываем таблицу
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.get_worksheet(0)

        # Получаем данные
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # Обработка координат
        if 'latitude' in df.columns:
            df['latitude'] = df['latitude'].astype(str).str.strip()
            df['latitude'] = df['latitude'].str.replace(',', '.')
            df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')

        if 'longitude' in df.columns:
            df['longitude'] = df['longitude'].astype(str).str.strip()
            df['longitude'] = df['longitude'].str.replace(',', '.')
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

        return df

    except Exception as e:
        st.error(f"❌ Ошибка загрузки из локального файла: {e}")
        return create_demo_data()


def create_demo_data():
    """Создает демонстрационные данные на случай ошибки"""
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
# 3. ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ
# -------------------------------
def get_unique_questions(df):
    """Получает список всех вопросов из таблицы"""
    questions = set()
    for col in df.columns:
        if col.startswith('question_'):
            questions.update(df[col].dropna().unique())
    return sorted(list(questions))


def get_answers_for_question(df, question):
    """Получает все варианты ответов на конкретный вопрос"""
    answers = set()
    for q_col in [c for c in df.columns if c.startswith('question_')]:
        mask = df[q_col] == question
        if mask.any():
            ans_col = q_col.replace('question_', 'answer_')
            if ans_col in df.columns:
                answers.update(df.loc[mask, ans_col].dropna().unique())
    return sorted(list(answers))


def filter_by_question(df, question, answer=None):
    """Фильтрует данные по вопросу и ответу"""
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


def get_color_for_answer(question, answer):
    """Определяет цвет маркера в зависимости от ответа"""
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
# 4. СОЗДАНИЕ КАРТЫ
# -------------------------------
def create_map(df, selected_question=None, selected_answer=None):
    """
    Создает интерактивную карту с маркерами
    """
    # Центрируем карту на Удмуртии
    center_lat = 57.0
    center_lon = 53.0

    # Создаем карту
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles='OpenStreetMap'
    )

    # Добавляем маркеры для каждого населенного пункта
    for idx, row in df.iterrows():
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            # Определяем цвет и всплывающую подсказку
            color = 'blue'

            # Безопасное получение значений
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

            # Если выбран конкретный вопрос, добавляем информацию о нем
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

            # Добавляем всю остальную информацию
            popup_text += "<hr><b>Все диалектные особенности:</b><br>"
            for q_col in [c for c in df.columns if c.startswith('question_')]:
                if pd.notna(row[q_col]):
                    ans_col = q_col.replace('question_', 'answer_')
                    if ans_col in df.columns and pd.notna(row[ans_col]):
                        popup_text += f"• {row[q_col]}: <b>{row[ans_col]}</b><br>"

            # Создаем маркер
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=tooltip,
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)

    return m


# -------------------------------
# 5. ИНТЕРФЕЙС РЕДАКТИРОВАНИЯ
# -------------------------------
def show_editor_interface(df):
    """Показывает интерфейс для редактирования данных"""

    st.markdown("## ✏️ Режим редактирования данных")
    st.markdown("---")

    # Подключаем геокодер
    geocoder = LocationGeocoder()

    # Создаем вкладки
    tab1, tab2, tab3 = st.tabs([
        "➕ Добавить пункт",
        "🔄 Обновить координаты",
        "🗺️ Проверить на карте"
    ])

    with tab1:
        st.markdown("### Добавление нового населенного пункта")
        st.info("Координаты определяются автоматически из локальной базы данных!")

        col1, col2 = st.columns(2)

        with col1:
            new_region = st.text_input("Регион *", value="Удмуртская Республика")
            new_district = st.text_input("Район *", placeholder="Завьяловский район")
            new_settlement = st.text_input("Населенный пункт *", placeholder="д. Новая Деревня")
            new_type = st.selectbox("Тип населенного пункта",
                                    ["деревня", "село", "поселок", "город", "хутор"])

        with col2:
            st.markdown("#### 🌍 Координаты")

            # Кнопка для поиска координат
            if st.button("🔍 Найти координаты", type="primary"):
                if new_settlement:
                    lat, lon = geocoder.get_coordinates(new_settlement, new_district, new_region)
                    if lat and lon:
                        st.session_state['new_lat'] = lat
                        st.session_state['new_lon'] = lon
                        st.success(f"✅ Найдено: {lat:.6f}, {lon:.6f}")

                        # Показываем карту
                        m = folium.Map(location=[lat, lon], zoom_start=12)
                        folium.Marker([lat, lon], popup=new_settlement).add_to(m)
                        st_folium(m, width=400, height=300)
                    else:
                        st.error("❌ Не найдено в базе данных. Введите вручную")

            # Поля для ручного ввода
            new_lat = st.number_input("Широта",
                                      value=st.session_state.get('new_lat', 57.0),
                                      format="%.6f",
                                      step=0.0001)
            new_lon = st.number_input("Долгота",
                                      value=st.session_state.get('new_lon', 53.0),
                                      format="%.6f",
                                      step=0.0001)

        # Кнопка добавления
        if st.button("✅ Добавить населенный пункт", use_container_width=True):
            if new_region and new_district and new_settlement:
                st.success(f"✅ Пункт {new_settlement} готов к добавлению!")
                st.json({
                    "region": new_region,
                    "district": new_district,
                    "settlement": new_settlement,
                    "type": new_type,
                    "latitude": new_lat,
                    "longitude": new_lon,
                })
            else:
                st.error("❌ Заполните обязательные поля (*)")

    with tab2:
        st.markdown("### Обновление координат для существующих пунктов")

        # Проверяем наличие колонок
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Пункты без координат
            missing_coords = df[df['latitude'].isna() | df['longitude'].isna()]

            if len(missing_coords) > 0:
                st.warning(f"⚠️ Найдено {len(missing_coords)} пунктов без координат")
                st.dataframe(missing_coords[['region', 'district', 'settlement']])

                if st.button("🔄 Найти координаты для всех", type="primary"):
                    with st.spinner("Поиск координат..."):
                        updated_df = geocoder.batch_geocode(df.copy())
                        st.success("✅ Координаты обновлены!")
                        st.rerun()
            else:
                st.success("✅ Все пункты имеют координаты!")

    with tab3:
        st.markdown("### Проверка координат на карте")

        if 'settlement' in df.columns:
            settlements = df['settlement'].dropna().tolist()
            selected = st.selectbox("Выберите населенный пункт", settlements)

            if selected:
                point = df[df['settlement'] == selected].iloc[0]
                if pd.notna(point['latitude']) and pd.notna(point['longitude']):
                    st.success(f"Координаты: {point['latitude']:.6f}, {point['longitude']:.6f}")

                    m = folium.Map(location=[point['latitude'], point['longitude']], zoom_start=12)
                    folium.Marker([point['latitude'], point['longitude']], popup=selected).add_to(m)
                    st_folium(m, width=800, height=400)
                else:
                    st.warning("У этого пункта нет координат")


# -------------------------------
# 6. ЗАГРУЗКА ДАННЫХ
# -------------------------------
with st.spinner('🔄 Загрузка данных из Google Sheets...'):
    df = load_data_from_gsheet()

if df.empty:
    st.warning("⚠️ Нет данных для отображения")
    st.stop()

# -------------------------------
# 7. БОКОВАЯ ПАНЕЛЬ
# -------------------------------
with st.sidebar:
    st.markdown("## 🔍 Поиск и фильтры")

    # Кнопки режимов
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

    # Поиск
    search_settlement = st.text_input("🔎 Найти населенный пункт")

    st.markdown("---")

    # Выбор вопроса
    questions = ['Все вопросы'] + get_unique_questions(df)
    selected_question = st.selectbox("📋 Выберите вопрос", questions)

    # Выбор ответа
    selected_answer = "Все ответы"
    if selected_question and selected_question != "Все вопросы":
        answers = ['Все ответы'] + get_answers_for_question(df, selected_question)
        selected_answer = st.selectbox("🎯 Фильтр по ответу", answers)

    st.markdown("---")

    # Фильтр по региону
    regions = ['Все регионы'] + sorted(df['region'].unique().tolist())
    selected_region = st.selectbox("📍 Регион", regions)

    st.markdown("---")

    # Статистика
    st.markdown("## 📊 Статистика")
    st.metric("Населенных пунктов", len(df))
    if 'district' in df.columns:
        st.metric("Районов", df['district'].nunique())
    if 'region' in df.columns:
        st.metric("Регионов", df['region'].nunique())

# -------------------------------
# 8. ФИЛЬТРАЦИЯ ДАННЫХ
# -------------------------------
filtered_df = df.copy()

if selected_region != "Все регионы" and 'region' in df.columns:
    filtered_df = filtered_df[filtered_df['region'] == selected_region]

if search_settlement and 'settlement' in df.columns:
    filtered_df = filtered_df[
        filtered_df['settlement'].str.contains(search_settlement, case=False, na=False)
    ]

if selected_question and selected_question != "Все вопросы":
    filtered_df = filter_by_question(
        filtered_df,
        selected_question,
        selected_answer if selected_answer != "Все ответы" else None
    )

# -------------------------------
# 9. ОСНОВНОЙ ИНТЕРФЕЙС
# -------------------------------
if st.session_state['edit_mode']:
    # Режим редактирования
    show_editor_interface(df)
else:
    # Режим просмотра карты
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("## 🗺️ Интерактивная карта")

        # Создаем карту
        map_obj = create_map(
            filtered_df,
            selected_question if selected_question != "Все вопросы" else None,
            selected_answer if selected_answer != "Все ответы" else None
        )

        # Отображаем карту
        st_folium(map_obj, width=800, height=500)

        # Информация о точках
        points_with_coords = filtered_df.dropna(subset=['latitude', 'longitude'])
        st.info(f"📍 Показано пунктов: {len(points_with_coords)} из {len(filtered_df)}")

    with col2:
        st.markdown("## 📋 Легенда")
        if selected_question and selected_question != "Все вопросы":
            answers = get_answers_for_question(df, selected_question)
            for answer in answers:
                color = get_color_for_answer(selected_question, answer)
                st.markdown(f"<span style='color: {color};'>●</span> {answer}", unsafe_allow_html=True)
        else:
            st.markdown("""
            **Цвета маркеров:**
            - 🔴 Красный - взрывной [г]
            - 🟢 Зеленый - фрикативный [ɣ]
            - 🟠 Оранжевый - твердое [ца]
            - 🟣 Фиолетовый - мягкое [ц'а]
            - 🔵 Синий - стандартный
            """)

# -------------------------------
# 10. ТАБЛИЦА С ДАННЫМИ
# -------------------------------
st.markdown("---")
st.markdown("## 📋 Данные населенных пунктов")

# Выбираем колонки для отображения
display_cols = ['region', 'district', 'settlement']
if 'settlement_type' in df.columns:
    display_cols.append('settlement_type')
if 'latitude' in df.columns and 'longitude' in df.columns:
    display_cols.extend(['latitude', 'longitude'])

# Добавляем вопросы
for i in range(1, 6):
    q_col = f'question_{i}'
    a_col = f'answer_{i}'
    if q_col in filtered_df.columns and a_col in filtered_df.columns:
        display_cols.extend([q_col, a_col])

# Отображаем таблицу
st.dataframe(
    filtered_df[display_cols],
    width='stretch',
    height=300,
    hide_index=True
)

# -------------------------------
# 11. КНОПКИ ЭКСПОРТА
# -------------------------------
col1, col2 = st.columns(2)
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
# 12. ПОДВАЛ
# -------------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: small;'>
        Данные загружены из Google Sheets • Обновление каждые 60 секунд<br>
        Координаты определяются из локальной базы данных
    </div>
    """,
    unsafe_allow_html=True
)