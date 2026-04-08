# geocoder.py
import streamlit as st
import pandas as pd
import re
import urllib.parse

# Словарь вопросов ДАРЯ с номерами
DARYA_QUESTIONS = {
    "1": "Фонетика: произношение [г]",
    "2": "Фонетика: произношение окончаний -тся/-ться",
    "3": "Морфология: окончание глаголов 3 л. мн.ч.",
    "4": "Лексика: название 'избы'",
    "5": "Синтаксис: конструкция с 'у меня есть'",
    "6": "Фонетика: цоканье/чоканье",
    "7": "Фонетика: произношение [в]",
    "8": "Морфология: окончание Р.п. ед.ч. сущ. ж.р.",
    "9": "Морфология: форма Тв.п. мн.ч.",
    "10": "Лексика: название 'петуха'",
    "11": "Лексика: название 'ковша'",
    "12": "Синтаксис: конструкция с 'у меня есть' (развернутая)",
}

# Обратный словарь для поиска номера по тексту вопроса
QUESTION_TO_NUMBER = {v: k for k, v in DARYA_QUESTIONS.items()}


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
            'понино': (58.2000, 52.7000),
            'пычас': (56.5000, 52.3000),
            'якшур-бодья': (57.1925, 53.1622),
            'вавож': (56.7756, 51.9289),
            'селты': (57.3133, 52.1344),
            'кез': (57.8956, 53.7131),
            'балезино': (57.9789, 53.0111),
            'юкаменское': (57.8833, 52.2417),
            'каракулино': (56.0122, 53.7067),
            'алнаши': (56.1878, 52.4794),
            'дебесы': (57.6514, 53.8058),
            'шаркан': (57.0494, 53.9967),
            'красногорское': (57.7067, 52.4969),
            'сюмси': (57.1111, 51.6156),
            'камбарка': (56.2694, 54.2022),
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

    def create_wikipedia_url(self, settlement, district="", region=""):
        """Создает ссылку на страницу Википедии для поиска координат"""
        # Формируем поисковый запрос
        search_parts = [settlement]
        if district and district not in settlement:
            search_parts.append(district)
        if region and region not in settlement:
            search_parts.append(region)

        search_query = " ".join(search_parts)
        encoded_query = urllib.parse.quote(search_query)

        # Ссылка на поиск в Википедии
        wiki_url = f"https://ru.wikipedia.org/wiki/{encoded_query}"

        # Альтернативная ссылка на страницу с координатами
        coords_url = f"https://ru.wikipedia.org/w/index.php?search={encoded_query}&title=Служебная:Поиск"

        return {
            "page_url": wiki_url,
            "search_url": coords_url,
            "query": search_query
        }

    def get_coordinates(self, settlement, district="", region=""):
        """Получает координаты, возвращает также ссылку на Википедию"""
        try:
            settlement_norm = self.normalize_name(settlement)

            # Поиск в локальной базе
            if settlement_norm in self.coordinates_db:
                self.success_count += 1
                return self.coordinates_db[settlement_norm], None

            for key, coords in self.coordinates_db.items():
                if settlement_norm and (settlement_norm in key or key in settlement_norm):
                    self.success_count += 1
                    return coords, None

            # Если не нашли, формируем ссылку на Википедию
            self.timeout_count += 1
            wiki_url = self.create_wikipedia_url(settlement, district, region)
            return None, wiki_url

        except Exception as e:
            return None, None

    def batch_geocode(self, df):
        """Обрабатывает все населенные пункты в DataFrame"""
        progress_bar = st.progress(0)
        status_text = st.empty()

        total = len(df)
        updated_count = 0
        failed_count = 0
        skipped_count = 0

        for idx, row in df.iterrows():
            has_lat = 'latitude' in df.columns and pd.notna(row['latitude'])
            has_lon = 'longitude' in df.columns and pd.notna(row['longitude'])

            if has_lat and has_lon:
                skipped_count += 1
                progress_bar.progress((idx + 1) / total)
                continue

            settlement_val = row['settlement'] if 'settlement' in df.columns else ""
            district_val = row['district'] if 'district' in df.columns and pd.notna(row['district']) else ""
            region_val = row['region'] if 'region' in df.columns and pd.notna(row['region']) else ""

            status_text.text(f"🔍 [{idx + 1}/{total}] {settlement_val}...")

            result, _ = self.get_coordinates(settlement_val, district_val, region_val)

            if result:
                lat, lon = result
                df.at[idx, 'latitude'] = lat
                df.at[idx, 'longitude'] = lon
                updated_count += 1
            else:
                failed_count += 1

            progress_bar.progress((idx + 1) / total)

        progress_bar.empty()
        status_text.empty()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Найдено", updated_count)
        with col2:
            st.metric("❌ Не найдено", failed_count)
        with col3:
            st.metric("⏭️ Пропущено", skipped_count)

        return df