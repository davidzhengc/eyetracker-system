import pandas as pd
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QGroupBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt

import matplotlib

matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class AnalysisDialog(QDialog):
    def __init__(self, csv_filepath, screen_w=1920, screen_h=1080, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis")
        self.resize(1000, 700)

        self.csv_filepath = csv_filepath
        self.screen_w = screen_w
        self.screen_h = screen_h

        try:
            self.df = pd.read_csv(csv_filepath)
        except Exception as e:
            self.df = pd.DataFrame()
            print(f"Error cargando CSV: {e}")

        self.setup_ui()
        self.apply_styles()

        # Show the heatmap by default if there is data
        if not self.df.empty:
            self.plot_heatmap()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- LEFT PANEL (Controls) ---
        left_panel = QVBoxLayout()

        # 1. Data summary
        stats_group = QGroupBox("Resumen de la Sesión")
        stats_layout = QVBoxLayout()
        num_samples = len(self.df)
        duration = round(self.df['timestamp'].iloc[-1] - self.df['timestamp'].iloc[0], 2) if num_samples > 1 else 0

        stats_layout.addWidget(QLabel(f"<b>Archivo:</b> {self.csv_filepath.split('/')[-1]}"))
        stats_layout.addWidget(QLabel(f"<b>Muestras grabadas:</b> {num_samples}"))
        stats_layout.addWidget(QLabel(f"<b>Duración (aprox):</b> {duration} s"))
        stats_group.setLayout(stats_layout)
        left_panel.addWidget(stats_group)

        # 2. Visualization Tools
        viz_group = QGroupBox("Herramientas de Visualización")
        viz_layout = QVBoxLayout()

        btn_heatmap = QPushButton("Generar Mapa de Calor (Heatmap)")
        btn_heatmap.clicked.connect(self.plot_heatmap)

        btn_scanpath = QPushButton("Generar Trayectoria (Scanpath)")
        btn_scanpath.clicked.connect(self.plot_scanpath)

        viz_layout.addWidget(btn_heatmap)
        viz_layout.addWidget(btn_scanpath)
        viz_group.setLayout(viz_layout)
        left_panel.addWidget(viz_group)

        left_panel.addStretch()

        # Close button
        btn_close = QPushButton("Finalizar Sesión")
        btn_close.clicked.connect(self.accept)
        left_panel.addWidget(btn_close)

        # --- RIGHT PANEL (Matplotlib Canvas) ---
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)

        main_layout.addLayout(left_panel, 1)
        main_layout.addWidget(self.canvas, 3)

    def plot_heatmap(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if self.df.empty:
            ax.text(0.5, 0.5, "No hay datos grabados", ha='center', va='center')
        else:
            x = self.df['x']
            y = self.df['y']

            # Crear mapa de calor 2D
            h = ax.hist2d(x, y, bins=[50, 50], range=[[0, self.screen_w], [0, self.screen_h]], cmap='jet')
            self.figure.colorbar(h[3], ax=ax, label='Densidad de mirada')

            ax.invert_yaxis()  # Invert Y since (0,0) is at the top left corner
            ax.set_title('Mapa de Calor (Heatmap)')
            ax.set_xlim(0, self.screen_w)
            ax.set_ylim(self.screen_h, 0)

        self.canvas.draw()

    def plot_scanpath(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if self.df.empty:
            ax.text(0.5, 0.5, "No hay datos grabados", ha='center', va='center')
        else:
            x = self.df['x']
            y = self.df['y']

            ax.plot(x, y, marker='o', markersize=4, linestyle='-', linewidth=1, alpha=0.6, color='b')

            ax.invert_yaxis()
            ax.set_title('Trayectoria Ocular (Scanpath)')
            ax.set_xlim(0, self.screen_w)
            ax.set_ylim(self.screen_h, 0)
            ax.legend()

        self.canvas.draw()

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog { 
                background-color: #F8F9FA; 
                font-family: 'Segoe UI', Arial, sans-serif; 
                font-size: 13px;
            }
            QGroupBox { 
                font-weight: bold; 
                margin-top: 25px;
                border: 1px solid #CED4DA; 
                border-radius: 8px; 
                background-color: white;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                subcontrol-position: top left;
                padding: 0 5px; 
                color: #0D6EFD; 
                left: 15px;
            }
            QPushButton { 
                padding: 12px; 
                border-radius: 6px; 
                border: 1px solid #0D6EFD; 
                background-color: white; 
                color: #0D6EFD; 
                font-weight: bold; 
                font-size: 13px;
            }
            QPushButton:hover { 
                background-color: #0D6EFD; 
                color: white; 
            }
            QLabel {
                color: #495057;
                padding: 2px;
            }
        """)