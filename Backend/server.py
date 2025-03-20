#!/usr/bin/env python3
"""
Ollama Chat Backend Server

Hauptserver-Datei, die alle API-Endpunkte und die Hauptfunktionalität
des Ollama Chat Backends bereitstellt.
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
import webbrowser
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

# Lokale Module importieren
try:
    from config import (
        SERVER_HOST,
        SERVER_PORT,
        DEBUG_MODE,
        LOG_LEVEL,
        LOG_FORMAT,
        DEFAULT_MODEL,
        LOCAL_IP,
        DATABASE_PATH
    )
    from database import (
        init_db,
        create_chat,
        add_message,
        get_chat,
        get_all_chats,
        get_chat_messages,
        delete_chat,
        save_server,
        get_default_server,
        get_all_servers,
        update_server_connection
    )
    from ollama_client import (
        ollama_client
    )
    from qr_handler import (
        generate_server_qr,
        generate_backend_qr,
        verify_qr_data
    )
except ImportError as e:
    print(f"Fehler beim Importieren der Module: {e}")
    print("Bitte stellen Sie sicher, dass alle erforderlichen Dateien vorhanden sind.")
    sys.exit(1)

# Logger einrichten
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger("OllamaServer")

# Flask-App initialisieren
app = Flask(__name__)
CORS(app)  # Cross-Origin Resource Sharing aktivieren

# Datenbank initialisieren
try:
    init_db()
except Exception as e:
    logger.error(f"Fehler bei der Datenbankinitialisierung: {e}")
    sys.exit(1)

# API-Endpunkte

@app.route('/api/health', methods=['GET'])
def health_check():
    """Einfacher Health-Check-Endpunkt zur Überprüfung der Serververfügbarkeit."""
    return jsonify({
        "status": "online",
        "timestamp": time.time(),
        "version": "1.0.0"
    })

@app.route('/api/models', methods=['GET'])
def get_models():
    """
    Ruft alle verfügbaren Ollama-Modelle ab.
    
    Query-Parameter:
        force_refresh (bool): Bei True wird der Cache ignoriert
        
    Returns:
        JSON-Antwort mit der Liste der verfügbaren Modelle
    """
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    result = ollama_client.get_models(force_refresh=force_refresh)
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
    
    return jsonify(result)

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Sendet eine Chat-Nachricht an das Ollama-Modell und gibt die Antwort zurück.
    
    Request-Body JSON:
        model (str): Name des zu verwendenden Modells
        message (str): Nachricht des Benutzers
        chat_id (str, optional): ID eines existierenden Chats
        temperature (float, optional): Temperatur für die Generierung
        max_tokens (int, optional): Maximale Anzahl an Tokens in der Antwort
        
    Returns:
        JSON-Antwort mit der generierten Nachricht
    """
    data = request.json
    
    # Pflichtfelder überprüfen
    if not data or not all(key in data for key in ['model', 'message']):
        return jsonify({"error": "Modell und Nachricht sind erforderlich"}), 400
    
    model = data.get('model', DEFAULT_MODEL)
    message = data.get('message')
    chat_id = data.get('chat_id')
    temperature = data.get('temperature')
    max_tokens = data.get('max_tokens')
    
    # Chat-Historie laden, falls vorhanden
    history = []
    if chat_id:
        messages = get_chat_messages(chat_id)
        if messages:
            history = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    
    # Anfrage an Ollama senden
    response = ollama_client.chat(
        model=model,
        message=message,
        history=history,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    if "error" in response:
        return jsonify({"error": response["error"]}), 500
    
    # Chat erstellen oder Nachricht hinzufügen
    try:
        if not chat_id:
            # Neuen Chat erstellen
            title = message[:50] + ('...' if len(message) > 50 else '')
            chat_id = create_chat(title, model)
        
        # Benutzernachricht speichern
        user_message_id = add_message(chat_id, "user", message)
        
        # Assistentennachricht speichern
        assistant_content = response.get("message", {}).get("content", "")
        assistant_message_id = add_message(chat_id, "assistant", assistant_content)
        
        return jsonify({
            "chat_id": chat_id,
            "response": assistant_content,
            "message_id": assistant_message_id
        })
    
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Chats: {e}")
        return jsonify({
            "warning": "Antwort erhalten, aber Fehler beim Speichern",
            "response": response.get("message", {}).get("content", ""),
            "error": str(e)
        })

@app.route('/api/chat/stream', methods=['POST'])
def stream_chat():
    """
    Sendet eine Chat-Nachricht und gibt die Antwort als Event-Stream zurück.
    
    Request-Body JSON:
        model (str): Name des zu verwendenden Modells
        message (str): Nachricht des Benutzers
        chat_id (str, optional): ID eines existierenden Chats
        temperature (float, optional): Temperatur für die Generierung
        max_tokens (int, optional): Maximale Anzahl an Tokens in der Antwort
        
    Returns:
        Event-Stream mit der generierten Antwort
    """
    data = request.json
    
    # Pflichtfelder überprüfen
    if not data or not all(key in data for key in ['model', 'message']):
        return jsonify({"error": "Modell und Nachricht sind erforderlich"}), 400
    
    model = data.get('model', DEFAULT_MODEL)
    message = data.get('message')
    chat_id = data.get('chat_id')
    temperature = data.get('temperature')
    max_tokens = data.get('max_tokens')
    
    # Chat-Historie laden, falls vorhanden
    history = []
    if chat_id:
        messages = get_chat_messages(chat_id)
        if messages:
            history = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    
    def generate():
        # Variablen für die vollständige Antwort
        full_response = ""
        chat_created = False
        
        # Chat erstellen, falls keiner vorhanden
        if not chat_id:
            title = message[:50] + ('...' if len(message) > 50 else '')
            new_chat_id = create_chat(title, model)
            # Benutzernachricht speichern
            add_message(new_chat_id, "user", message)
            yield f"data: {json.dumps({'chat_id': new_chat_id})}\n\n"
            nonlocal chat_id
            chat_id = new_chat_id
            chat_created = True
        elif not chat_created:
            # Benutzernachricht speichern, wenn Chat bereits existiert
            add_message(chat_id, "user", message)
        
        # Stream von Ollama starten
        try:
            for chunk in ollama_client.chat_stream(
                model=model,
                message=message,
                history=history,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                if "error" in chunk:
                    yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                    return
                
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"
            
            # Assistentennachricht speichern
            assistant_message_id = add_message(chat_id, "assistant", full_response)
            
            # Abschluss-Event senden
            yield f"data: {json.dumps({'done': True, 'message_id': assistant_message_id})}\n\n"
            
        except Exception as e:
            logger.error(f"Fehler beim Streaming: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/chats', methods=['GET'])
def get_chats():
    """
    Ruft alle gespeicherten Chats ab.
    
    Returns:
        JSON-Antwort mit der Liste aller Chats
    """
    chats = get_all_chats()
    return jsonify({"chats": chats})

@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat_by_id(chat_id):
    """
    Ruft einen bestimmten Chat ab.
    
    Path-Parameter:
        chat_id (str): ID des abzurufenden Chats
        
    Returns:
        JSON-Antwort mit dem Chat und seinen Nachrichten
    """
    chat = get_chat(chat_id)
    if chat:
        return jsonify(chat)
    else:
        return jsonify({"error": "Chat nicht gefunden"}), 404

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def delete_chat_by_id(chat_id):
    """
    Löscht einen bestimmten Chat.
    
    Path-Parameter:
        chat_id (str): ID des zu löschenden Chats
        
    Returns:
        JSON-Antwort mit dem Ergebnis der Löschoperation
    """
    success = delete_chat(chat_id)
    if success:
        return jsonify({"success": True, "message": "Chat erfolgreich gelöscht"})
    else:
        return jsonify({"error": "Fehler beim Löschen des Chats"}), 500

@app.route('/api/qrcode/server', methods=['GET', 'POST'])
def generate_server_qrcode():
    """
    Generiert einen QR-Code für die Verbindung mit dem Ollama-Server.
    
    GET-Parameter oder POST-Body:
        name (str, optional): Name des Servers
        ip (str, optional): IP-Adresse des Servers
        
    Returns:
        JSON-Antwort mit dem generierten QR-Code als Base64-String
    """
    # Daten aus GET oder POST holen
    if request.method == 'GET':
        server_name = request.args.get('name')
        custom_ip = request.args.get('ip')
    else:  # POST
        data = request.json or {}
        server_name = data.get('name')
        custom_ip = data.get('ip')
    
    try:
        qr_code, server_data = generate_server_qr(server_name, custom_ip)
        return jsonify({
            "qrcode": qr_code,
            "server": server_data
        })
    except Exception as e:
        logger.error(f"Fehler bei der QR-Code-Generierung: {e}")
        return jsonify({"error": f"QR-Code konnte nicht generiert werden: {str(e)}"}), 500

@app.route('/api/qrcode/backend', methods=['GET', 'POST'])
def generate_backend_qrcode():
    """
    Generiert einen QR-Code für die Verbindung mit dem Backend-Server.
    
    GET-Parameter oder POST-Body:
        name (str, optional): Name des Servers
        ip (str, optional): IP-Adresse des Servers
        
    Returns:
        JSON-Antwort mit dem generierten QR-Code als Base64-String
    """
    # Daten aus GET oder POST holen
    if request.method == 'GET':
        server_name = request.args.get('name')
        custom_ip = request.args.get('ip')
    else:  # POST
        data = request.json or {}
        server_name = data.get('name')
        custom_ip = data.get('ip')
    
    try:
        qr_code, server_data = generate_backend_qr(server_name, custom_ip)
        return jsonify({
            "qrcode": qr_code,
            "server": server_data
        })
    except Exception as e:
        logger.error(f"Fehler bei der QR-Code-Generierung: {e}")
        return jsonify({"error": f"QR-Code konnte nicht generiert werden: {str(e)}"}), 500

@app.route('/api/server/connect', methods=['POST'])
def connect_server():
    """
    Testet die Verbindung zu einem Ollama-Server und speichert ihn bei Erfolg.
    
    Request-Body JSON:
        name (str): Name des Servers
        ip (str): IP-Adresse des Servers
        port (str/int): Port des Servers
        is_default (bool, optional): Ob der Server als Standard gesetzt werden soll
        
    Returns:
        JSON-Antwort mit dem Verbindungsstatus
    """
    data = request.json
    
    # Pflichtfelder überprüfen
    if not data or not all(key in data for key in ['name', 'ip', 'port']):
        return jsonify({"error": "Name, IP-Adresse und Port sind erforderlich"}), 400
    
    name = data.get('name')
    ip = data.get('ip')
    port = data.get('port')
    is_default = data.get('is_default', False)
    
    # URL zusammenbauen
    url = f"http://{ip}:{port}"
    
    # Verbindung testen
    try:
        # Temporären Client erstellen für den Test
        test_client = ollama_client.__class__(api_url=url)
        result = test_client.get_models()
        
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500
        
        # Server speichern
        server_id = save_server(name, url, is_default)
        
        return jsonify({
            "success": True,
            "server_id": server_id,
            "models": result
        })
        
    except Exception as e:
        logger.error(f"Fehler bei der Serververbindung: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/servers', methods=['GET'])
def get_servers():
    """
    Ruft alle gespeicherten Server ab.
    
    Returns:
        JSON-Antwort mit der Liste aller Server
    """
    servers = get_all_servers()
    return jsonify({"servers": servers})

@app.route('/api/server/default', methods=['GET'])
def get_default_server_info():
    """
    Ruft den Standard-Server ab.
    
    Returns:
        JSON-Antwort mit den Informationen zum Standard-Server
    """
    server = get_default_server()
    if server:
        return jsonify(server)
    else:
        return jsonify({"error": "Kein Standard-Server gefunden"}), 404

# Statische Dateien (falls vorhanden)
@app.route('/', defaults={'path': 'index.html'})
@app.route('/<path:path>')
def static_files(path):
    """
    Stellt statische Dateien aus dem static-Verzeichnis bereit, falls vorhanden.
    Falls nicht, gibt einen Statuscode 404 zurück.
    """
    static_dir = Path(__file__).parent / 'static'
    if static_dir.exists() and (static_dir / path).exists():
        return send_from_directory('static', path)
    else:
        # API-Informationsseite anzeigen, wenn kein Frontend vorhanden ist
        if path == 'index.html':
            api_info = {
                "name": "Ollama Chat Backend API",
                "version": "1.0.0",
                "endpoints": {
                    "/api/health": "Server-Status prüfen",
                    "/api/models": "Verfügbare Modelle abrufen",
                    "/api/chat": "Chat-Nachricht senden",
                    "/api/chat/stream": "Chat-Nachricht mit Stream-Antwort senden",
                    "/api/chats": "Alle Chats abrufen",
                    "/api/qrcode/server": "QR-Code für Ollama-Server generieren",
                    "/api/qrcode/backend": "QR-Code für Backend-Server generieren",
                    "/api/server/connect": "Mit Ollama-Server verbinden"
                }
            }
            return jsonify(api_info)
        return jsonify({"error": "Datei nicht gefunden"}), 404

# Server-Start-Funktion
def run_server(host=None, port=None, debug=None, open_browser=True):
    """
    Startet den Flask-Server.
    
    Args:
        host (str, optional): Host-Adresse für den Server
        port (int, optional): Port für den Server
        debug (bool, optional): Debug-Modus aktivieren
        open_browser (bool, optional): Browser automatisch öffnen
    """
    host = host or SERVER_HOST
    port = port or SERVER_PORT
    debug = debug if debug is not None else DEBUG_MODE
    
    # IP-Adresse und Port anzeigen
    server_url = f"http://{LOCAL_IP}:{port}"
    logger.info(f"Server wird gestartet auf {server_url}")
    logger.info(f"Datenbank: {DATABASE_PATH}")
    
    # Browser öffnen
    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(server_url)).start()
    
    # Server starten
    app.run(host=host, port=port, debug=debug)

# Hauptfunktion
if __name__ == "__main__":
    # Kommandozeilenargumente parsen
    parser = argparse.ArgumentParser(description="Ollama Chat Backend Server")
    parser.add_argument('--host', type=str, help=f"Host (Standard: {SERVER_HOST})")
    parser.add_argument('--port', type=int, help=f"Port (Standard: {SERVER_PORT})")
    parser.add_argument('--debug', action='store_true', help="Debug-Modus aktivieren")
    parser.add_argument('--no-browser', action='store_true', help="Browser nicht automatisch öffnen")
    
    args = parser.parse_args()
    
    try:
        # Server starten
        run_server(
            host=args.host,
            port=args.port,
            debug=args.debug,
            open_browser=not args.no_browser
        )
    except KeyboardInterrupt:
        logger.info("Server manuell beendet.")
    except Exception as e:
        logger.error(f"Fehler beim Starten des Servers: {e}")
        sys.exit(1)