#!/usr/bin/env python3
"""
Datenbankmodul für das Ollama Chat Backend

Dieses Modul verwaltet die SQLite-Datenbank für die Chat-Historie und bietet
Funktionen zum Speichern und Abrufen von Chats und Nachrichten.
"""

import sqlite3
import uuid
import datetime
import logging
import json
import os
from pathlib import Path

# Konfiguration importieren
from config import DATABASE_PATH

# Logger einrichten
logger = logging.getLogger("OllamaDB")

# SQL-Anweisungen für die Tabellenerstellung
CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        model TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS servers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        last_connected TEXT NOT NULL,
        is_default INTEGER DEFAULT 0
    )
    """
]

def init_db():
    """
    Initialisiert die Datenbank und erstellt die notwendigen Tabellen,
    falls sie noch nicht existieren.
    """
    # Verzeichnis erstellen, falls es nicht existiert
    os.makedirs(Path(DATABASE_PATH).parent, exist_ok=True)
    
    conn = None
    try:
        # Verbindung herstellen
        conn = sqlite3.connect(DATABASE_PATH)
        # Fremdschlüssel aktivieren
        conn.execute("PRAGMA foreign_keys = ON")
        
        cursor = conn.cursor()
        
        # Tabellen erstellen
        for create_sql in CREATE_TABLES_SQL:
            cursor.execute(create_sql)
            
        # Standardserver hinzufügen, falls noch keiner existiert
        cursor.execute("SELECT COUNT(*) FROM servers WHERE is_default = 1")
        if cursor.fetchone()[0] == 0:
            add_default_server(conn)
            
        conn.commit()
        logger.info(f"Datenbank initialisiert: {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Datenbankfehler bei der Initialisierung: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def add_default_server(conn):
    """Fügt den lokalen Ollama-Server als Standard-Server hinzu."""
    from config import OLLAMA_API_URL
    
    server_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO servers (id, name, url, last_connected, is_default) VALUES (?, ?, ?, ?, 1)",
        (server_id, "Lokaler Ollama-Server", OLLAMA_API_URL, now)
    )

def get_db_connection():
    """Erstellt und gibt eine Datenbankverbindung zurück."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # Ergebnisse als Dict
    return conn

def create_chat(title, model):
    """
    Erstellt einen neuen Chat in der Datenbank.
    
    Args:
        title (str): Titel des Chats
        model (str): Verwendetes Ollama-Modell
        
    Returns:
        str: ID des erstellten Chats
    """
    chat_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chats (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, title, model, now, now)
        )
        conn.commit()
        logger.info(f"Neuer Chat erstellt: {chat_id} mit Modell {model}")
        return chat_id
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Erstellen des Chats: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def update_chat_timestamp(chat_id):
    """Aktualisiert den Zeitstempel eines Chats."""
    now = datetime.datetime.now().isoformat()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (now, chat_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Aktualisieren des Chat-Zeitstempels: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def add_message(chat_id, role, content):
    """
    Fügt eine Nachricht zu einem Chat hinzu.
    
    Args:
        chat_id (str): ID des Chats
        role (str): Rolle des Absenders (user/assistant)
        content (str): Inhalt der Nachricht
        
    Returns:
        str: ID der erstellten Nachricht
    """
    message_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (id, chat_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (message_id, chat_id, role, content, now)
        )
        conn.commit()
        
        # Chat-Zeitstempel aktualisieren
        update_chat_timestamp(chat_id)
        
        return message_id
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Hinzufügen der Nachricht: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_chat(chat_id):
    """
    Ruft einen Chat mit allen seinen Nachrichten ab.
    
    Args:
        chat_id (str): ID des Chats
        
    Returns:
        dict: Chat mit Nachrichten oder None, wenn nicht gefunden
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Chat-Informationen abrufen
        cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
        chat = cursor.fetchone()
        
        if not chat:
            return None
        
        # Nachrichten abrufen
        cursor.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp",
            (chat_id,)
        )
        messages = [dict(message) for message in cursor.fetchall()]
        
        # Chat als Dict zurückgeben
        chat_dict = dict(chat)
        chat_dict['messages'] = messages
        
        return chat_dict
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Abrufen des Chats: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_chat_messages(chat_id):
    """
    Ruft alle Nachrichten eines Chats ab.
    
    Args:
        chat_id (str): ID des Chats
        
    Returns:
        list: Liste der Nachrichten oder leere Liste, wenn keine gefunden
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp",
            (chat_id,)
        )
        messages = [dict(message) for message in cursor.fetchall()]
        return messages
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Abrufen der Nachrichten: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_chats():
    """
    Ruft alle Chats aus der Datenbank ab.
    
    Returns:
        list: Liste aller Chats (ohne Nachrichten)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chats ORDER BY updated_at DESC"
        )
        chats = [dict(chat) for chat in cursor.fetchall()]
        return chats
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Abrufen aller Chats: {e}")
        return []
    finally:
        if conn:
            conn.close()

def delete_chat(chat_id):
    """
    Löscht einen Chat und alle seine Nachrichten.
    
    Args:
        chat_id (str): ID des zu löschenden Chats
        
    Returns:
        bool: True, wenn erfolgreich, False bei Fehler
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        # Durch Foreign Key Constraint werden auch alle Nachrichten gelöscht
        conn.commit()
        logger.info(f"Chat gelöscht: {chat_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Löschen des Chats: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def save_server(name, url, is_default=False):
    """
    Speichert einen Ollama-Server in der Datenbank.
    
    Args:
        name (str): Name des Servers
        url (str): URL des Servers
        is_default (bool): Ob dieser Server als Standard gesetzt werden soll
        
    Returns:
        str: ID des gespeicherten Servers
    """
    server_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Wenn dieser Server der Standard sein soll, alle anderen zurücksetzen
        if is_default:
            cursor.execute("UPDATE servers SET is_default = 0")
        
        cursor.execute(
            "INSERT INTO servers (id, name, url, last_connected, is_default) VALUES (?, ?, ?, ?, ?)",
            (server_id, name, url, now, 1 if is_default else 0)
        )
        conn.commit()
        logger.info(f"Server gespeichert: {name} ({url})")
        return server_id
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Speichern des Servers: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_default_server():
    """
    Ruft den Standard-Server ab.
    
    Returns:
        dict: Server-Informationen oder None, wenn kein Standard-Server gefunden
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM servers WHERE is_default = 1")
        server = cursor.fetchone()
        return dict(server) if server else None
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Abrufen des Standard-Servers: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_servers():
    """
    Ruft alle gespeicherten Server ab.
    
    Returns:
        list: Liste aller Server
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM servers ORDER BY last_connected DESC")
        servers = [dict(server) for server in cursor.fetchall()]
        return servers
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Abrufen aller Server: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_server_connection(server_id):
    """Aktualisiert den Zeitstempel der letzten Verbindung eines Servers."""
    now = datetime.datetime.now().isoformat()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE servers SET last_connected = ? WHERE id = ?",
            (now, server_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Fehler beim Aktualisieren des Server-Zeitstempels: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()