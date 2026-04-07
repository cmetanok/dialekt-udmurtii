# isoglosses.py
import folium
import pandas as pd
from scipy.spatial import ConvexHull
import numpy as np


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
            # Замыкаем полигон (добавляем первую точку в конец)
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
                    fill_opacity=0.15,
                    dash_array='5, 5'  # Пунктирная линия
                ).add_to(m)

                # Добавляем границу (изоглоссу)
                folium.PolyLine(
                    locations=hull_points,
                    color=color,
                    weight=3,
                    opacity=0.8,
                    dash_array='5, 5'
                ).add_to(m)

        return m

    def create_isogloss_legend(self):
        """Создает HTML-легенду для изоглосс"""
        return """
        <div style="background-color: white; padding: 10px; border-radius: 5px; margin-top: 10px;">
            <b>🗺️ Изоглоссы (ареалы):</b><br>
            <span style="color: red;">⬤</span> Красный - ареал 1<br>
            <span style="color: blue;">⬤</span> Синий - ареал 2<br>
            <span style="color: green;">⬤</span> Зеленый - ареал 3<br>
            <span style="color: orange;">⬤</span> Оранжевый - ареал 4<br>
            <i>Пунктирные линии - границы распространения</i>
        </div>
        """