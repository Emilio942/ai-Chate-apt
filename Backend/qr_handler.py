#!/usr/bin/env python3
"""
QR-Code Handler für das Ollama Chat Backend

Dieses Modul generiert QR-Codes für die Verbindung mit dem Ollama-Server
und stellt Funktionen zur Verarbeitung dieser QR-Codes bereit.
"""

import json
import base64
import logging
from io import BytesIO
from typing import Dict, Any, Optional, Tuple

import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_M, ERROR_CORRECT_L, ERROR_CORRECT_Q

# Konfiguration importieren
from config import (
    LOCAL_IP,
    SERVER_PORT,
    OLLAMA_API_HOST,
    OLLAMA_API_PORT,
    QRCODE_ERROR_CORRECTION,
    QRCODE_BOX_SIZE,
    QRCODE_BORDER
)

# Logger einrichten
logger = logging.getLogger("QRHandler")

# Mapping für die QR-Code-Fehlerkorrektur-Level
ERROR_CORRECTION_LEVELS = {
    'L': ERROR_CORRECT_L,  # ~7% Fehlerkorrektur
    'M': ERROR_CORRECT_M,  # ~15% Fehlerkorrektur
    'Q': ERROR_CORRECT_Q,  # ~25% Fehlerkorrektur
    'H': ERROR_CORRECT_H   # ~30% Fehlerkorrektur
}

def create_connection_data(server_name: str = None, 
                           ip_address: str = None, 
                           port: int = None) -> Dict[str, Any]:
    """
    Erstellt die Verbindungsdaten für den QR-Code.
    
    Args:
        server_name (str, optional): Name des Servers
        ip_address (str, optional): IP-Adresse des Servers
        port (int, optional): Port des Servers
        
    Returns:
        Dict[str, Any]: Verbindungsdaten als Dictionary
    """
    # Standardwerte verwenden, wenn keine angegeben wurden
    if server_name is None:
        server_name = f"Ollama-Server ({LOCAL_IP})"
    if ip_address is None:
        ip_address = LOCAL_IP
    if port is None:
        port = OLLAMA_API_PORT
    
    # Verbindungsdaten zusammenstellen
    connection_data = {
        "type": "ollama_server",
        "name": server_name,
        "ip": ip_address,
        "port": str(port)
    }
    
    logger.debug(f"Verbindungsdaten erstellt: {connection_data}")
    return connection_data

def generate_qr_code(data: Dict[str, Any], 
                     error_correction: str = None, 
                     box_size: int = None, 
                     border: int = None) -> Tuple[str, Dict[str, Any]]:
    """
    Generiert einen QR-Code für die angegebenen Verbindungsdaten.
    
    Args:
        data (Dict[str, Any]): Die Verbindungsdaten als Dictionary
        error_correction (str, optional): Fehlerkorrektur-Level (L, M, Q, H)
        box_size (int, optional): Größe eines Quadrats im QR-Code
        border (int, optional): Breite des Randes in Quadraten
        
    Returns:
        Tuple[str, Dict[str, Any]]: Base64-kodierter QR-Code und die Verbindungsdaten
    """
    # Standardwerte aus der Konfiguration verwenden, wenn nicht angegeben
    if error_correction is None:
        error_correction = QRCODE_ERROR_CORRECTION
    if box_size is None:
        box_size = QRCODE_BOX_SIZE
    if border is None:
        border = QRCODE_BORDER
    
    # Fehlerkorrektur-Level auswählen
    error_level = ERROR_CORRECTION_LEVELS.get(
        error_correction.upper(), 
        ERROR_CORRECT_H  # Standardmäßig hohe Fehlerkorrektur
    )
    
    try:
        # Daten in JSON umwandeln
        json_data = json.dumps(data)
        
        # QR-Code-Objekt erstellen
        qr = qrcode.QRCode(
            version=1,
            error_correction=error_level,
            box_size=box_size,
            border=border
        )
        
        # Daten hinzufügen und QR-Code generieren
        qr.add_data(json_data)
        qr.make(fit=True)
        
        # QR-Code als Bild erzeugen
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Bild in Base64 umwandeln
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        logger.info(f"QR-Code generiert für Server: {data.get('name')}")
        return f"data:image/png;base64,{img_str}", data
        
    except Exception as e:
        logger.error(f"Fehler bei der QR-Code-Generierung: {e}")
        raise

def generate_server_qr(server_name: str = None, 
                       custom_ip: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Hilfsfunktion zur Generierung eines QR-Codes für den aktuellen Server.
    
    Args:
        server_name (str, optional): Name des Servers
        custom_ip (str, optional): Benutzerdefinierte IP-Adresse
        
    Returns:
        Tuple[str, Dict[str, Any]]: Base64-kodierter QR-Code und die Verbindungsdaten
    """
    # Verbindungsdaten erstellen
    server_data = create_connection_data(
        server_name=server_name,
        ip_address=custom_ip or LOCAL_IP,
        port=OLLAMA_API_PORT
    )
    
    # QR-Code generieren
    return generate_qr_code(server_data)

def generate_backend_qr(server_name: str = None,
                        custom_ip: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Generiert einen QR-Code für die Verbindung zum Backend-Server.
    
    Args:
        server_name (str, optional): Name des Servers
        custom_ip (str, optional): Benutzerdefinierte IP-Adresse
        
    Returns:
        Tuple[str, Dict[str, Any]]: Base64-kodierter QR-Code und die Verbindungsdaten
    """
    # Verbindungsdaten erstellen
    server_data = {
        "type": "ollama_backend",
        "name": server_name or f"Ollama-Backend ({LOCAL_IP})",
        "ip": custom_ip or LOCAL_IP,
        "port": str(SERVER_PORT)
    }
    
    # QR-Code generieren
    return generate_qr_code(server_data)

def verify_qr_data(qr_data: Dict[str, Any]) -> bool:
    """
    Überprüft, ob die QR-Code-Daten gültig sind.
    
    Args:
        qr_data (Dict[str, Any]): Die zu überprüfenden QR-Code-Daten
        
    Returns:
        bool: True, wenn die Daten gültig sind, sonst False
    """
    required_fields = ["type", "ip", "port"]
    
    # Prüfen, ob alle erforderlichen Felder vorhanden sind
    if not all(field in qr_data for field in required_fields):
        logger.warning(f"Ungültige QR-Code-Daten: Fehlende Felder")
        return False
    
    # Prüfen, ob der Typ korrekt ist
    if qr_data["type"] not in ["ollama_server", "ollama_backend"]:
        logger.warning(f"Ungültiger QR-Code-Typ: {qr_data.get('type')}")
        return False
    
    # Prüfen, ob der Port eine Zahl ist
    try:
        int(qr_data["port"])
    except ValueError:
        logger.warning(f"Ungültiger Port im QR-Code: {qr_data.get('port')}")
        return False
    
    return True