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

        # Получаем все уникальные ответы на выбранный вопрос
        answers = set()
        for q_col in [c for c in df.columns if c.startswith('question_')]:
            mask = df[q_col] == selected_question
            if mask.any():
                ans_col = q_col.replace('question_', 'answer_')
                if ans_col in df.columns:
                    answers.update(df.loc[mask, ans_col].dropna().unique())

        # Цвета для разных ответов
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'darkred', 'darkblue']

        for i, answer in enumerate(answers):
            points = self.get_points_for_question(df, selected_question, answer)
            hull_points = self.create_convex_hull(points)

            if hull_points and len(hull_points) >= 3:
                color = colors[i % len(colors)]

                # Добавляем полигон (ареал)
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

                # Добавляем границу (изоглоссу)
                folium.PolyLine(
                    locations=hull_points,
                    color=color,
                    weight=3,
                    opacity=0.9,
                    dash_array='5, 5'
                ).add_to(m)

        return m


# -------------------------------
# 3. КЛАСС ДЛЯ ГЕОКОДИРОВАНИЯ
# -------------------------------
class LocationGeocoder:
    def __init__(self):
        """Инициализация геокодера с локальной базой данных"""

        self.coordinates_db = {
            'ижевск': (56.8528, 53.2115),
            'воткинск': (57.0517, 53.9933),
            'сарапул': (56.4768, 53.7978),
            'глазов': (58.1359, 52.6635),
            'можга': (56.4428, 52.2278),
            'завьялово': (56.7892, 53.3736),
            'игра': (57.5528, 53.0544),
            'ува': (56.9808, 52.1851),
            'русская лоза': (56.8165, 53.3895),
            'зура': (57.5269, 53.0247),
            'чур': (57.1267, 53.3881),
            'бобино': (58.5589, 50.3395),
            'шестаково': (58.9522, 50.2456),
            'фоки': (56.6939, 54.1131),
            'танайка': (55.7891, 52.0345),
            'янаул': (56.2658, 54.9347),
        }

        self.timeout_count = 0
        self.success_count = 0

    def normalize_name(self, name):
        if pd.isna(name) or name is None:
            return ""
        name = str(name).lower().strip()
        prefixes = ['д. ', 'с. ', 'п. ', 'г. ', 'дер. ', 'село ', 'деревня ']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        return name

    def get_coordinates(self, settlement, district="", region=""):
        try:
            settlement_norm = self.normalize_name(settlement)

            if settlement_norm in self.coordinates_db:
                self.success_count += 1
                return self.coordinates_db[settlement_norm]

            for key, coords in self.coordinates_db.items():
                if settlement_norm and (settlement_norm in key or key in settlement_norm):
                    self.success_count += 1
                    return coords

            self.timeout_count += 1
            return None, None
        except Exception as e:
            return None, None


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
def get_unique_questions(df):
    questions = set()
    for col in df.columns:
        if col.startswith('question_'):
            questions.update(df[col].dropna().unique())
    return sorted(list(questions))


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
    """Поиск населенных пунктов по лингвистическим единицам (ответам)"""
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
    """Получает список всех уникальных лингвистических единиц (ответов)"""
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
# 6. СОЗДАНИЕ КАРТЫ С ИЗОГЛОССАМИ
# -------------------------------
def create_map(df, selected_question=None, selected_answer=None, show_isoglosses=True):
    center_lat = 57.0
    center_lon = 53.0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles='OpenStreetMap')

    # Добавляем изоглоссы (если включены и выбран вопрос)
    if show_isoglosses and selected_question and selected_question != "Все вопросы":
        iso_manager = IsoglossManager()
        m = iso_manager.add_isoglosses_to_map(m, df, selected_question)

    # Добавляем маркеры
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
# 7. ИНТЕРФЕЙС РЕДАКТИРОВАНИЯ
# -------------------------------
def show_editor_interface(df):
    st.markdown("## ✏️ Режим редактирования данных")
    st.markdown("---")

    geocoder = LocationGeocoder()

    tab1, tab2 = st.tabs(["➕ Добавить пункт", "🔄 Обновить координаты"])

    with tab1:
        st.markdown("### Добавление нового населенного пункта")

        col1, col2 = st.columns(2)

        with col1:
            new_region = st.text_input("Регион *", value="Удмуртская Республика")
            new_district = st.text_input("Район *", placeholder="Завьяловский район")
            new_settlement = st.text_input("Населенный пункт *", placeholder="д. Новая Деревня")
            new_type = st.selectbox("Тип населенного пункта", ["деревня", "село", "поселок", "город", "хутор"])

        with col2:
            st.markdown("#### 🌍 Координаты")

            if st.button("🔍 Найти координаты", type="primary"):
                if new_settlement:
                    lat, lon = geocoder.get_coordinates(new_settlement, new_district, new_region)
                    if lat and lon:
                        st.session_state['new_lat'] = lat
                        st.session_state['new_lon'] = lon
                        st.success(f"✅ Найдено: {lat:.6f}, {lon:.6f}")
                    else:
                        st.error("❌ Не найдено в базе данных")

            new_lat = st.number_input("Широта", value=st.session_state.get('new_lat', 57.0), format="%.6f", step=0.0001)
            new_lon = st.number_input("Долгота", value=st.session_state.get('new_lon', 53.0), format="%.6f",
                                      step=0.0001)

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
        if 'latitude' in df.columns and 'longitude' in df.columns:
            missing_coords = df[df['latitude'].isna() | df['longitude'].isna()]
            if len(missing_coords) > 0:
                st.warning(f"⚠️ Найдено {len(missing_coords)} пунктов без координат")
                st.dataframe(missing_coords[['region', 'district', 'settlement']])
            else:
                st.success("✅ Все пункты имеют координаты!")


# -------------------------------
# 8. ЗАГРУЗКА ДАННЫХ
# -------------------------------
with st.spinner('🔄 Загрузка данных из Google Sheets...'):
    df = load_data_from_gsheet()

if df.empty:
    st.warning("⚠️ Нет данных для отображения")
    st.stop()

# -------------------------------
# 9. БОКОВАЯ ПАНЕЛЬ
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

    # Поиск по населенному пункту
    search_settlement = st.text_input("🔎 Найти населенный пункт", placeholder="например: Русская Лоза")

    st.markdown("---")

    # Поиск по лингвистическим единицам
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

    # Выбор вопроса
    st.markdown("## 📋 Анализ по вопросам")
    questions = ['Все вопросы'] + get_unique_questions(df)
    selected_question = st.selectbox("Выберите вопрос из программы ДАРЯ", questions)

    selected_answer = "Все ответы"
    if selected_question and selected_question != "Все вопросы":
        answers = ['Все ответы'] + get_answers_for_question(df, selected_question)
        selected_answer = st.selectbox("Фильтр по ответу", answers)

    st.markdown("---")

    # Показ изоглосс
    st.session_state['show_isoglosses'] = st.checkbox("🗺️ Показывать изоглоссы (ареалы распространения)",
                                                      value=st.session_state['show_isoglosses'])

    st.markdown("---")

    # Фильтр по региону
    regions = ['Все регионы'] + sorted(df['region'].unique().tolist())
    selected_region = st.selectbox("📍 Регион", regions)

    st.markdown("---")

    # Статистика
    st.markdown("## 📊 Статистика")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Населенных пунктов", len(df))
        st.metric("Районов", df['district'].nunique() if 'district' in df.columns else 0)
    with col2:
        st.metric("Регионов", df['region'].nunique() if 'region' in df.columns else 0)
        st.metric("Вопросов", len(get_unique_questions(df)))

    st.markdown("---")

    # ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ
    with st.expander("📖 ПОЛНАЯ ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ", expanded=False):
        st.markdown("""
        ### 🗺️ РАБОТА С КАРТОЙ

        **Основные действия:**
        - **Кликните на любой маркер** - откроется окно со всей информацией о населенном пункте: все диалектные особенности, район, регион
        - **Приближайте/отдаляйте карту** - используйте колесико мыши или кнопки +/- на карте
        - **Перетаскивайте карту** - зажмите левую кнопку мыши и двигайте

        ### 🔍 ПОИСК И ФИЛЬТРАЦИЯ

        **Поиск по населенному пункту:**
        - Введите название деревни, села или города в поле "Найти населенный пункт"
        - Результаты отобразятся на карте и в таблице

        **Поиск по диалектным особенностям:**
        - Введите ключевое слово: "взрывной", "фрикативный", "твердое", "мягкое" и т.д.
        - Или выберите из выпадающего списка всех доступных вариантов
        - Карта покажет только те пункты, где есть выбранная особенность

        **Анализ по вопросам ДАРЯ:**
        - Выберите интересующий вас вопрос из программы ДАРЯ/ЛАРНГ
        - Маркеры на карте раскрасятся в соответствии с ответами
        - Включите **"Показывать изоглоссы"** - увидете границы распространения каждого ответа

        ### 🗺️ ИЗОГЛОССЫ (АРЕАЛЫ)

        Что это такое? Изоглоссы - это линии на карте, показывающие границы распространения определенных языковых явлений.

        **Как использовать:**
        1. Выберите любой вопрос из списка
        2. Включите чекбокс "Показывать изоглоссы"
        3. На карте появятся цветные области - ареалы распространения разных вариантов ответов
        4. Каждый цвет соответствует определенному варианту ответа

        ### ✏️ РЕЖИМ РЕДАКТИРОВАНИЯ

        **Как добавить новый населенный пункт:**
        1. Нажмите кнопку "✏️ Редактор" в боковой панели
        2. Перейдите на вкладку "➕ Добавить пункт"
        3. Заполните поля: регион, район, название, тип пункта
        4. Нажмите "🔍 Найти координаты" - они определятся автоматически
        5. Нажмите "✅ Добавить населенный пункт"

        **Как обновить координаты:**
        - Если у каких-то пунктов нет координат, перейдите на вкладку "🔄 Обновить координаты"
        - Система автоматически найдет координаты из базы данных

        ### 📊 ТАБЛИЦА ДАННЫХ

        Под картой находится таблица со всеми данными:
        - Показывает отфильтрованные результаты
        - Можно скопировать данные из таблицы
        - Нажмите "📥 Экспорт в CSV" - скачайте данные в формате Excel

        ### 🔄 ОБНОВЛЕНИЕ ДАННЫХ

        - Данные автоматически обновляются каждые 60 секунд
        - Для ручного обновления нажмите кнопку "🔄 Обновить данные"

        ### 📝 ПРИМЕЧАНИЯ

        - Данные хранятся в Google Sheets и могут редактироваться удаленно
        - При изменении таблицы, данные на карте обновятся автоматически
        - Для добавления новых вопросов нужно изменить структуру Google Таблицы
        """)

# -------------------------------
# 10. ФИЛЬТРАЦИЯ ДАННЫХ
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
# 11. ОСНОВНОЙ ИНТЕРФЕЙС
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

        if selected_question and selected_question != "Все вопросы" and st.session_state['show_isoglosses']:
            st.caption(
                "🗺️ **Цветные области на карте - это ареалы распространения (изоглоссы)**. Каждый цвет соответствует одному из вариантов ответа.")

    with col2:
        st.markdown("## 📋 Легенда")

        if selected_question and selected_question != "Все вопросы":
            st.markdown(f"**Цвета маркеров для вопроса:**")
            st.markdown(f"*{selected_question}*")
            st.markdown("---")
            answers = get_answers_for_question(df, selected_question)
            for answer in answers:
                color = get_color_for_answer(selected_question, answer)
                st.markdown(f"<span style='color: {color}; font-size: 20px;'>●</span> {answer}", unsafe_allow_html=True)

            if st.session_state['show_isoglosses']:
                st.markdown("---")
                st.markdown("**🗺️ Изоглоссы (ареалы):**")
                st.markdown("Цветные области на карте показывают границы распространения")
                st.caption("Пунктирные линии - это границы ареалов")
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

            *Цвета меняются при выборе конкретного вопроса*
            """)

        st.markdown("---")
        st.markdown("💡 **Совет:** Выберите вопрос из списка, чтобы увидеть изоглоссы!")

# -------------------------------
# 12. ТАБЛИЦА С ДАННЫМИ
# -------------------------------
st.markdown("---")
st.markdown("## 📋 Данные населенных пунктов")

# Выбираем колонки для отображения
display_cols = ['region', 'district', 'settlement']
if 'settlement_type' in df.columns:
    display_cols.append('settlement_type')
if 'latitude' in df.columns and 'longitude' in df.columns:
    display_cols.extend(['latitude', 'longitude'])

# Добавляем вопросы и ответы
for i in range(1, 10):  # до 10 вопросов
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
# 13. КНОПКИ ЭКСПОРТА
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
# 14. ПОДВАЛ
# -------------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: small;'>
        <b>📊 Источник данных:</b> Google Sheets (программа ДАРЯ/ЛАРНГ)<br>
        <b>🔄 Автообновление:</b> данные обновляются каждые 60 секунд<br>
        <b>🗺️ Изоглоссы:</b> показывают границы распространения диалектных явлений<br>
        <b>🔍 Поиск по лемме:</b> работает по всем диалектным особенностям в таблице<br>
        <b>📝 Редактирование:</b> данные можно редактировать в Google Sheets и через интерфейс приложения<br><br>
        © Диалектологическая карта Удмуртии | Проект выполнен в рамках изучения русских говоров
    </div>
    """,
    unsafe_allow_html=True
)