from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout, QRadioButton
)

import sys
from gaze_tracker import GazeTracker, GazeTrackerConfig
from analysis_ui import AnalysisDialog

class ConfigDialog(QDialog):
    """Initial settings window implemented with PySide6."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración Inicial")
        self.resize(550, 650)
        self.config = GazeTrackerConfig()

        self.setup_ui()
        self.apply_modern_style()  # Apply the "CSS"

    def apply_modern_style(self):
        modern_qss = """
        QDialog {
            background-color: #F8F9FA;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
        }
        QGroupBox {
            background-color: #FFFFFF;
            border: 1px solid #DEE2E6;
            border-radius: 8px;
            margin-top: 20px;
            font-weight: bold;
            color: #212529;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #0D6EFD;
            left: 15px;
        }
        QLabel, QRadioButton, QCheckBox {
            color: #495057;
            font-size: 14px;
        }
        QComboBox, QSpinBox, QDoubleSpinBox {
            padding: 6px 12px;
            border: 1px solid #CED4DA;
            border-radius: 6px;
            background-color: #FFFFFF;
            min-height: 25px;
            color: #212529;
        }
        QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
            border: 1px solid #0D6EFD;
        }
        QPushButton {
            border-radius: 6px;
            padding: 10px 24px;
            font-size: 15px;
            font-weight: bold;
        }
        QPushButton#btn_start {
            background-color: #0D6EFD;
            color: white;
            border: none;
        }
        QPushButton#btn_start:hover {
            background-color: #0B5ED7;
        }
        QPushButton#btn_cancel {
            background-color: #FFFFFF;
            color: #6C757D;
            border: 1px solid #CED4DA;
        }
        QPushButton#btn_cancel:hover {
            background-color: #E9ECEF;
            color: #495057;
        }
        """
        self.setStyleSheet(modern_qss)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        # 2. ADD PADDINGS AND MARGINS
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # --- SECTION 1: EXECUTION MODE ---
        mode_group = QGroupBox("Modo de Ejecución")
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(20, 20, 20, 15)

        self.radio_tracking = QRadioButton("Modo Tracking")
        self.radio_tracking.setChecked(True)
        self.radio_eval = QRadioButton("Modo Evaluación")

        mode_layout.addWidget(self.radio_tracking)
        mode_layout.addWidget(self.radio_eval)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # --- SECTION 2: BASIC CALIBRATION ---
        calib_group = QGroupBox("Calibración N-Point")
        calib_layout = QFormLayout()
        calib_layout.setContentsMargins(20, 20, 20, 15)
        calib_layout.setSpacing(15)

        self.combo_points = QComboBox()
        self.combo_points.addItems(["9", "16", "25", "36", "49", "64"])
        self.combo_points.setCurrentText(str(self.config.num_points))
        calib_layout.addRow("Número de puntos:", self.combo_points)
        calib_group.setLayout(calib_layout)
        main_layout.addWidget(calib_group)

        # --- SECTION 3: LISSAJOUS CALIBRATION ---
        liss_group = QGroupBox("Calibración Avanzada (Lissajous)")
        liss_layout = QFormLayout()
        liss_layout.setContentsMargins(20, 20, 20, 15)
        liss_layout.setSpacing(15)

        self.check_lissajous = QCheckBox("Habilitar calibración Lissajous")
        self.check_lissajous.setChecked(self.config.use_lissajous)

        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(5, 60)
        self.spin_duration.setValue(int(self.config.lissajous_duration))
        self.spin_duration.setSuffix(" s")

        self.spin_coverage = QDoubleSpinBox()
        self.spin_coverage.setRange(0.1, 1.0)
        self.spin_coverage.setSingleStep(0.05)
        self.spin_coverage.setValue(self.config.lissajous_coverage)

        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.1, 3.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(self.config.lissajous_speed)

        self.check_lissajous.toggled.connect(self.toggle_lissajous_params)
        self.toggle_lissajous_params(self.config.use_lissajous)

        liss_layout.addRow(self.check_lissajous)
        liss_layout.addRow("Duración:", self.spin_duration)
        liss_layout.addRow("Cobertura de pantalla:", self.spin_coverage)
        liss_layout.addRow("Velocidad:", self.spin_speed)

        liss_group.setLayout(liss_layout)
        main_layout.addWidget(liss_group)

        # --- SECTION 4: SMOOTHING FILTER ---
        filter_group = QGroupBox("Procesamiento de Señal")
        filter_layout = QFormLayout()
        filter_layout.setContentsMargins(20, 20, 20, 15)

        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Kalman", "KDE", "Ninguno"])
        filter_layout.addRow("Tipo de filtro:", self.combo_filter)
        filter_group.setLayout(filter_layout)
        main_layout.addWidget(filter_group)

        # --- ACTION BUTTONS ---
        btn_layout = QHBoxLayout()
        btn_start = QPushButton("Iniciar Motor")
        btn_start.setObjectName("btn_start")  # Identificador para el QSS

        btn_cancel = QPushButton("Salir")
        btn_cancel.setObjectName("btn_cancel")  # Identificador para el QSS

        btn_start.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_start)
        main_layout.addLayout(btn_layout)

    def toggle_lissajous_params(self, checked):
        self.spin_duration.setEnabled(checked)
        self.spin_coverage.setEnabled(checked)
        self.spin_speed.setEnabled(checked)

    def get_final_config(self):
        self.config.evaluation_mode = self.radio_eval.isChecked()
        self.config.num_points = int(self.combo_points.currentText())
        self.config.use_lissajous = self.check_lissajous.isChecked()
        self.config.lissajous_duration = self.spin_duration.value()
        self.config.lissajous_coverage = self.spin_coverage.value()
        self.config.lissajous_speed = self.spin_speed.value()

        filter_idx = self.combo_filter.currentIndex()
        if filter_idx == 0:
            self.config.filter_type = "kalman"
        elif filter_idx == 1:
            self.config.filter_type = "kde"
        else:
            self.config.filter_type = "none"

        return self.config

def main():
    """
    Main entry point of the application.
    Shows the configuration UI and then launches the GazeTracker.
    """
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 1. Show configuration
    dialog = ConfigDialog()
    if dialog.exec() == QDialog.Accepted:
        config = dialog.get_final_config()
        print("\nConfiguración cargada. Iniciando Tracker...")

        # 2. Start tracking and record data
        tracker = GazeTracker(config)
        # The run method returns the filename of the saved CSV, or None
        saved_csv_path = tracker.run()

        # Upon completion, open analysis if a file was saved
        if saved_csv_path:
            print(f"Launching viewer for: {saved_csv_path}")
            analysis_window = AnalysisDialog(csv_filepath=saved_csv_path,
                                             screen_w=tracker.screen_w,
                                             screen_h=tracker.screen_h)
            analysis_window.exec()
        elif tracker.gaze_log:
             print("No se grabaron datos en esta sesión (Recuerda pulsar 'R' para grabar).")
    else:
        print("Operación cancelada.")
        sys.exit(0)

if __name__ == "__main__":
    main()
