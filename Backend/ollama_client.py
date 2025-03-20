#!/usr/bin/env python3
"""
Ollama API Client für das Ollama Chat Backend

Dieses Modul stellt die Verbindung zur Ollama API her und bietet Funktionen
zum Senden von Anfragen und Verarbeiten von Antworten.
"""

import json
import logging
import time
import requests
from typing import Dict, List, Any, Optional, Generator, Union, Tuple

# Konfiguration importieren
from config import (
    OLLAMA_API_URL,
    DEFAULT_MODEL,
    MODEL_PARAMS
)

# Logger einrichten
logger = logging.getLogger("OllamaClient")

class OllamaClient:
    """Client für die Kommunikation mit der Ollama API."""
    
    def __init__(self, api_url: str = None):
        """
        Initialisiert den Ollama-Client.
        
        Args:
            api_url (str, optional): URL der Ollama-API.
                                    Wenn nicht angegeben, wird die URL aus der Konfiguration verwendet.
        """
        self.api_url = api_url or OLLAMA_API_URL
        self.models_cache = {"timestamp": 0, "data": None}
        self.models_cache_time = 300  # Cache-Gültigkeit in Sekunden (5 Minuten)
        logger.info(f"Ollama-Client initialisiert mit API-URL: {self.api_url}")
    
    def _check_connection(self) -> bool:
        """
        Überprüft die Verbindung zur Ollama-API.
        
        Returns:
            bool: True bei erfolgreicher Verbindung, sonst False.
        """
        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Verbindungsfehler zur Ollama-API: {e}")
            return False
    
    def get_models(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Ruft die verfügbaren Modelle von der Ollama-API ab.
        
        Args:
            force_refresh (bool): Bei True wird der Cache ignoriert und neu geladen.
            
        Returns:
            Dict[str, Any]: JSON-Antwort der API oder Fehlermeldung.
        """
        current_time = time.time()
        
        # Cache verwenden, wenn er noch gültig ist und kein Force-Refresh gewünscht ist
        if (not force_refresh and 
            self.models_cache["data"] is not None and 
            current_time - self.models_cache["timestamp"] < self.models_cache_time):
            logger.debug("Modelle aus Cache geladen")
            return self.models_cache["data"]
        
        # Ansonsten neu laden
        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=10)
            if response.status_code == 200:
                # Cache aktualisieren
                self.models_cache["timestamp"] = current_time
                self.models_cache["data"] = response.json()
                return self.models_cache["data"]
            else:
                error_msg = f"Fehler beim Abrufen der Modelle: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}
        except Exception as e:
            error_msg = f"Verbindungsfehler bei Modellabfrage: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def chat(self, 
             model: str, 
             message: str, 
             history: List[Dict[str, str]] = None,
             temperature: float = None,
             max_tokens: int = None) -> Dict[str, Any]:
        """
        Sendet eine Chat-Anfrage an die Ollama-API und gibt die Antwort zurück.
        
        Args:
            model (str): Name des zu verwendenden Modells
            message (str): Die Nachricht des Benutzers
            history (List[Dict[str, str]], optional): Bisheriger Chatverlauf
            temperature (float, optional): Temperaturwert für die Generierung
            max_tokens (int, optional): Maximale Anzahl an Tokens in der Antwort
            
        Returns:
            Dict[str, Any]: Die Antwort des Models oder eine Fehlermeldung
        """
        # Standardwerte aus der Konfiguration laden, wenn nicht explizit angegeben
        model_config = MODEL_PARAMS.get(model, MODEL_PARAMS.get(DEFAULT_MODEL, {}))
        if temperature is None:
            temperature = model_config.get("temperature", 0.7)
        if max_tokens is None:
            max_tokens = model_config.get("max_tokens", 2048)
        
        # Chat-Verlauf vorbereiten
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Anfrage erstellen
        request_body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        # Anfrage senden
        try:
            response = requests.post(
                f"{self.api_url}/api/chat",
                json=request_body,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Fehler bei der Chat-Anfrage: {response.status_code}"
                logger.error(error_msg)
                if response.text:
                    logger.error(f"API-Antwort: {response.text[:200]}...")
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Verbindungsfehler bei Chat-Anfrage: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def chat_stream(self, 
                    model: str, 
                    message: str, 
                    history: List[Dict[str, str]] = None,
                    temperature: float = None,
                    max_tokens: int = None) -> Generator[Dict[str, Any], None, None]:
        """
        Sendet eine Chat-Anfrage und gibt die Antwort als Stream zurück.
        
        Args:
            model (str): Name des zu verwendenden Modells
            message (str): Die Nachricht des Benutzers
            history (List[Dict[str, str]], optional): Bisheriger Chatverlauf
            temperature (float, optional): Temperaturwert für die Generierung
            max_tokens (int, optional): Maximale Anzahl an Tokens in der Antwort
            
        Yields:
            Dict[str, Any]: Teile der Antwort als Stream
        """
        # Standardwerte aus der Konfiguration laden, wenn nicht explizit angegeben
        model_config = MODEL_PARAMS.get(model, MODEL_PARAMS.get(DEFAULT_MODEL, {}))
        if temperature is None:
            temperature = model_config.get("temperature", 0.7)
        if max_tokens is None:
            max_tokens = model_config.get("max_tokens", 2048)
        
        # Chat-Verlauf vorbereiten
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Anfrage erstellen
        request_body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        # Anfrage senden
        try:
            with requests.post(
                f"{self.api_url}/api/chat",
                json=request_body,
                stream=True,
                timeout=60
            ) as response:
                if response.status_code != 200:
                    error_msg = f"Fehler bei der Stream-Anfrage: {response.status_code}"
                    logger.error(error_msg)
                    yield {"error": error_msg}
                    return
                
                # Antwort als Stream verarbeiten
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            yield chunk
                        except json.JSONDecodeError as e:
                            logger.error(f"Fehler beim Parsen der Stream-Antwort: {e}")
                            yield {"error": f"Fehler beim Parsen der Antwort: {str(e)}"}
                
        except requests.RequestException as e:
            error_msg = f"Verbindungsfehler bei Stream-Anfrage: {str(e)}"
            logger.error(error_msg)
            yield {"error": error_msg}
    
    def generate(self, 
                model: str, 
                prompt: str,
                temperature: float = None,
                max_tokens: int = None) -> Dict[str, Any]:
        """
        Sendet eine Generierungsanfrage an die Ollama-API (ältere /api/generate Endpunkt).
        
        Args:
            model (str): Name des zu verwendenden Modells
            prompt (str): Der Prompt für die Generierung
            temperature (float, optional): Temperaturwert für die Generierung
            max_tokens (int, optional): Maximale Anzahl an Tokens in der Antwort
            
        Returns:
            Dict[str, Any]: Die Antwort des Models oder eine Fehlermeldung
        """
        # Standardwerte aus der Konfiguration laden, wenn nicht explizit angegeben
        model_config = MODEL_PARAMS.get(model, MODEL_PARAMS.get(DEFAULT_MODEL, {}))
        if temperature is None:
            temperature = model_config.get("temperature", 0.7)
        if max_tokens is None:
            max_tokens = model_config.get("max_tokens", 2048)
        
        # Anfrage erstellen
        request_body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        # Anfrage senden
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json=request_body,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Fehler bei der Generierungsanfrage: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Verbindungsfehler bei Generierungsanfrage: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def embed(self, model: str, text: str) -> Dict[str, Any]:
        """
        Erzeugt Embedding-Vektoren für den angegebenen Text.
        
        Args:
            model (str): Name des zu verwendenden Modells
            text (str): Der zu einbettende Text
            
        Returns:
            Dict[str, Any]: Die Embedding-Vektoren oder eine Fehlermeldung
        """
        # Anfrage erstellen
        request_body = {
            "model": model,
            "prompt": text
        }
        
        # Anfrage senden
        try:
            response = requests.post(
                f"{self.api_url}/api/embeddings",
                json=request_body,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Fehler bei der Embedding-Anfrage: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Verbindungsfehler bei Embedding-Anfrage: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

# Einzelne Client-Instanz für die Wiederverwendung
ollama_client = OllamaClient()