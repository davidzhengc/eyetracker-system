# Mejora y despliegue multiplataforma de un sistema de eye tracking basado en webcam

El proyecto es un software de seguimiento ocular (*eye-tracking*) accesible y autónomo, desarrollado como Trabajo de Fin de Grado (TFG) por David Zheng (UAB).
El sistema estima las coordenadas de la mirada del usuario en tiempo real utilizando una cámara web estándar, eliminando la necesidad de utilizar hardware infrarrojo especializado y costoso. \
Este proyecto nace como una continuación y evolución del repositorio original https://github.com/ManuIluro22/eye-tracker/.

## Descripción del Proyecto

Este sistema utiliza *Deep Learning* para la extracción de *landmarks* faciales y aplica modelos matemáticos rigurosos para mapear las coordenadas de la pupila a la pantalla. 
Para superar los problemas de usabilidad típicos de los *trackers* basados en webcam, se ha implementado una arquitectura híbrida avanzada de procesamiento de señales que estabiliza el cursor y reduce drásticamente el temblor (*jitter*).

## Estructura del repositorio
```text
eyetracker-system/
├── assets/                 # Iconos
│   └── eyetracker_icon.png
├── .gitignore              # Reglas de exclusión para el control de versiones
├── analysis.py             # Módulo de visualización post-sesión
├── analysis_ui.py          # Interfaz del módulo de visualización post-sesión
├── calibration_module.py   # Módulo de calibración
├── gaze_tracker.py         # Bucle principal de seguimiento ocular
├── evaluation.py           # Módulo de evaluación
├── main_app.py             # Punto de entrada de la aplicación y GUI (PySide6)
└── requirements.txt        # Manifiesto de dependencias de Python
```

## Instalación y Uso

Para ejecutar el eyetracker simplemente se ha de utilizar el ejecutable precompilado:

Ejecutable Nativo (Windows)
1. Ve a la pestaña de [Releases](../../releases) en este repositorio.
2. Descarga el archivo `EyeTracker.zip`.
3. Extrae la carpeta.
4. Haz doble clic en `EyeTracker.exe` para iniciar la aplicación.


## Autor
David Zheng
