"""Tiny translation table: English source strings, Spanish when the desktop is in Spanish.

``MANDARINE_LANG=en`` or ``=es`` forces a language.
"""
from __future__ import annotations

import locale
import os

ES = {
    # wheel
    "COMPRESS": "COMPRIMIR", "METADATA": "METADATOS", "EDIT": "EDITAR", "ROTATE": "GIRAR",
    "ADD BG": "FONDO", "CROP": "RECORTAR", "REDACT": "OCULTAR", "ANNOTATE": "ANOTAR", "MERGE": "UNIR",
    "TOOLS": "HERRAMIENTAS", "FORMATS": "FORMATOS", "MUTE": "SILENCIAR", "LOUDNESS": "VOLUMEN",
    "720P": "720P", "CLEAN": "LIMPIAR", "Drop here": "Suelta aquí",
    # tray and toasts
    "Hold Shift while dragging a file": "Mantén Shift mientras arrastras un archivo",
    "Shift+drag is unavailable here: use the bubble or Show Wheel":
        "Shift+arrastrar no está disponible aquí: usa la burbuja o Mostrar rueda",
    "Show Wheel": "Mostrar rueda", "Settings…": "Ajustes…", "Quit": "Salir", "Show": "Mostrar",
    "Mandarine on GitHub": "Mandarine en GitHub",
    "Converting to {}…": "Convirtiendo a {}…", "Compressing…": "Comprimiendo…", "Rotating…": "Girando…",
    "Removing audio…": "Quitando el audio…", "Resizing to 720p…": "Bajando a 720p…",
    "Normalizing loudness…": "Ajustando el volumen…", "Cleaning metadata…": "Limpiando metadatos…",
    "Cropping…": "Recortando…", "Adding background…": "Añadiendo fondo…", "Redacting…": "Ocultando…",
    "Saving annotations…": "Guardando anotaciones…", "Saving edits…": "Guardando cambios…",
    "Merging…": "Uniendo…",
    "{} of {} saved": "{} de {} guardados", "{} file saved": "{} archivo guardado",
    "{} files saved": "{} archivos guardados", ", {} failed": ", {} con error",
    "{} done": "{}: listo", "Nothing saved": "No se guardó nada", "Something went wrong": "Algo salió mal",
    "Could not open {}": "No se pudo abrir {}", "already optimal": "ya estaba optimizado",
    "Working… {}%": "Procesando… {}%",
    # settings
    "Mandarine Settings": "Ajustes de Mandarine", "Shortcut": "Atajo", "Default": "Por defecto",
    "Open the wheel": "Abrir la rueda", "Behaviour": "Comportamiento", "Defaults": "Valores por defecto",
    "Show the wheel when I hold Shift while dragging a file":
        "Mostrar la rueda al mantener Shift mientras arrastro un archivo",
    "Show the floating bubble (drop files on it; works on Wayland)":
        "Mostrar la burbuja flotante (suelta archivos encima; funciona en Wayland)",
    "Add Mandarine to the file manager's right-click menu":
        "Añadir Mandarine al menú del clic derecho del gestor de archivos",
    "Open at login": "Abrir al iniciar sesión",
    "Open the tools ring first (Ctrl+Shift opens the other one)":
        "Abrir primero el anillo de herramientas (Ctrl+Shift abre el otro)",
    "Compression": "Compresión", "Light (best quality)": "Ligera (mejor calidad)", "Balanced": "Equilibrada",
    "Strong (smallest)": "Fuerte (más pequeño)", "Done": "Listo",
    "Set up the shortcut in GNOME": "Configurar el atajo en GNOME",
    "On Wayland, apps cannot watch global drags or keys. Use the floating bubble, or add a shortcut in your "
    "desktop's keyboard settings that runs: mandarine wheel":
        "En Wayland las apps no pueden vigilar el arrastre ni el teclado de todo el sistema. Usa la burbuja "
        "flotante, o añade en los ajustes de teclado de tu escritorio un atajo que ejecute: mandarine wheel",
    "Shortcut added to GNOME: {}": "Atajo añadido a GNOME: {}",
    "A global shortcut is not available in this session.":
        "En esta sesión no hay atajo global disponible.",
    "No shortcut set.": "Sin atajo.",
    "That shortcut is taken by another app or not supported. Try another one.":
        "Ese atajo ya lo usa otra app o no es compatible. Prueba otro.",
    "Opens the wheel for the files you then drop on it.":
        "Abre la rueda para los archivos que sueltes en ella.",
    "Mandarine {} · free and open source (AGPL-3.0) · based on Astral Shift":
        "Mandarine {} · libre y de código abierto (AGPL-3.0) · basado en Astral Shift",
    "Helper programs": "Programas auxiliares", "Video and audio (ffmpeg)": "Vídeo y audio (ffmpeg)",
    "Documents (LibreOffice)": "Documentos (LibreOffice)",
    "Text from images (Tesseract OCR)": "Texto de imágenes (OCR con Tesseract)",
    "Installed": "Instalado", "Missing · {}": "Falta · {}", "Install": "Instalar",
    # dialogs
    "Cancel": "Cancelar", "Reset": "Restablecer", "Apply": "Aplicar", "Undo": "Deshacer", "Free": "Libre",
    "Crop": "Recortar", "Crop Image": "Recortar imagen", "Crop PDF": "Recortar PDF", "Aspect ratio": "Proporción",
    "Add BG": "Añadir fondo", "Background": "Fondo", "Padding": "Margen", "Corners": "Esquinas", "Shadow": "Sombra",
    "Ratio": "Proporción", "Save with Background": "Guardar con fondo",
    "Redact": "Ocultar", "Redact & Save": "Ocultar y guardar",
    "Drag over anything to hide it.": "Arrastra sobre lo que quieras ocultar.",
    " Text under the boxes is removed from the PDF.": " El texto bajo los recuadros se elimina del PDF.",
    "Annotate": "Anotar", "Save": "Guardar", "Pen": "Lápiz", "Highlight": "Resaltar", "Box": "Recuadro",
    "Arrow": "Flecha", "Text": "Texto", "Edit": "Editar", "Rotate": "Girar", "Flip H": "Voltear H",
    "Flip V": "Voltear V", "Size": "Tamaño", "Black and white": "Blanco y negro", "Field": "Campo", "Value": "Valor", "Brightness": "Brillo", "Contrast": "Contraste",
    "Saturation": "Saturación",
    "PDF pages stay sharp: only rotation applies to PDFs.":
        "Las páginas PDF siguen nítidas: en PDF solo se aplica el giro.",
    "Split into Pages": "Separar en páginas", "Metadata": "Metadatos", "Save Clean Copy": "Guardar copia limpia",
    "Saving a clean copy removes author, software, GPS, dates and XMP. The original is kept.":
        "La copia limpia quita autor, programa, GPS, fechas y XMP. El original se conserva.",
    "Merge into PDF": "Unir en un PDF",
    "Drag to reorder. PDFs and images become one PDF, in this order.":
        "Arrastra para ordenar. Los PDF e imágenes se unen en un solo PDF, en este orden.",
    "Move Up": "Subir", "Move Down": "Bajar", "Merge": "Unir", "Page {} of {}": "Página {} de {}",
    "No metadata found.": "No hay metadatos.",
}


def lang() -> str:
    for var in ("MANDARINE_LANG", "LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value:
            return value[:2].lower()
    # Windows sets none of those: ask the C library ("Spanish_Spain" or "es_ES").
    name = (locale.getlocale()[0] or "").lower()
    return "es" if name.startswith(("es", "spanish")) else "en"


def tr(text: str, *args) -> str:
    """Translate ``text`` and fill ``{}`` placeholders with ``args``."""
    out = ES.get(text, text) if lang() == "es" else text
    return out.format(*args) if args else out
