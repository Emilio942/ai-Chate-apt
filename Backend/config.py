#!/usr/bin/env python3
"""
Konfigurationsdatei für das Ollama Chat Backend

Diese Datei enthält alle Konfigurationsparameter für das Backend.
Sie kann direkt bearbeitet werden oder über Umgebungsvariablen überschrieben werden.
"""

import os
import socket
from pathlib import Path


# Basis-Verzeichnis für die Anwendung
BASE_DIR = Path(__file__).resolve().parent


# Ollama API Konfiguration
OLLAMA_API_HOST = os.environ.get("OLLAMA_API_HOST", "localhost")
OLLAMA_API_PORT = int(os.environ.get("OLLAMA_API_PORT", 11434))
OLLAMA_API_URL = f"http://{OLLAMA_API_HOST}:{OLLAMA_API_PORT}"

# Server-Konfiguration
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")  # 0.0.0.0 = alle Interfaces
SERVER_PORT = int(os.environ.get("SERVER_PORT", 5000))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

# Datenbank-Konfiguration
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "chat_history.db"))
# Sicherstellen, dass das Verzeichnis existiert
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# Modell-Konfiguration
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "llama3")
MODEL_PARAMS = {
    "llama3": {
        "temperature": float(os.environ.get("LLAMA3_TEMPERATURE", 0.7)),
        "max_tokens": int(os.environ.get("LLAMA3_MAX_TOKENS", 2048)),
        "top_p": float(os.environ.get("LLAMA3_TOP_P", 0.9)),
        "repeat_penalty": float(os.environ.get("LLAMA3_REPEAT_PENALTY", 1.1))
    },
    "mistral": {
        "temperature": float(os.environ.get("MISTRAL_TEMPERATURE", 0.72)),
        "max_tokens": int(os.environ.get("MISTRAL_MAX_TOKENS", 2048)),
        "top_p": float(os.environ.get("MISTRAL_TOP_P", 0.9)),
        "repeat_penalty": float(os.environ.get("MISTRAL_REPEAT_PENALTY", 1.1))
    },
    "gemma": {
        "temperature": float(os.environ.get("GEMMA_TEMPERATURE", 0.7)),
        "max_tokens": int(os.environ.get("GEMMA_MAX_TOKENS", 2048)),
        "top_p": float(os.environ.get("GEMMA_TOP_P", 0.9)),
        "repeat_penalty": float(os.environ.get("GEMMA_REPEAT_PENALTY", 1.05))
    }
}

# QR-Code-Konfiguration
QRCODE_ERROR_CORRECTION = os.environ.get("QRCODE_ERROR_CORRECTION", "H")  # H = höchste Fehlerkorrektur
QRCODE_BOX_SIZE = int(os.environ.get("QRCODE_BOX_SIZE", 10))
QRCODE_BORDER = int(os.environ.get("QRCODE_BORDER", 4))

# Funktion zum Ermitteln der lokalen IP-Adresse
def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Servers im Netzwerk"""
    try:
        # Verbindung zu einem externen Server aufbauen, um Netzwerkadapter zu ermitteln
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback auf localhost
        return "127.0.0.1"

# Lokale IP-Adresse für QR-Code
LOCAL_IP = os.environ.get("LOCAL_IP", get_local_ip())

# Logging-Konfiguration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = os.environ.get("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
LOG_FILE = os.environ.get("LOG_FILE", "")  # Leer = nur Konsole

# Cache-Einstellungen
MODELS_CACHE_TIME = int(os.environ.get("MODELS_CACHE_TIME", 300))  # Sekunden