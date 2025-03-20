

import socket
import subprocess
import os
import sys
import platform
from datetime import datetime

def install_package(package):
    """Installiert ein Python-Paket, wenn es nicht verfügbar ist"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"{package} wurde erfolgreich installiert.")
    except subprocess.CalledProcessError:
        print(f"Fehler bei der Installation von {package}. Bitte manuell installieren: pip install {package}")
        sys.exit(1)

# Prüfen, ob die benötigten Pakete installiert sind
try:
    import qrcode
except ImportError:
    print("qrcode-Modul nicht gefunden. Wird installiert...")
    install_package("qrcode")

try:
    from PIL import Image
except ImportError:
    print("Pillow-Modul (PIL) nicht gefunden. Wird installiert...")
    install_package("pillow")
    from PIL import Image

# Ollama-Port
OLLAMA_PORT = 11434

def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Computers"""
    try:
        # Erstellt eine temporäre Socket-Verbindung um die lokale IP zu ermitteln
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Verbindung zum Google DNS (wird keine tatsächliche Verbindung hergestellt)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback-Methode
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            # Weitere Fallback-Methode für Linux
            try:
                output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()[0]
                return output
            except:
                pass
        return ip

def check_ollama_running():
    """Überprüft, ob Ollama auf dem angegebenen Port läuft"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('localhost', OLLAMA_PORT))
        s.close()
        return result == 0
    except:
        return False

def generate_qr_code(url, save_path):
    """Generiert einen QR-Code für die URL und zeigt ihn an"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # QR-Code als Bild generieren
    img = qr.make_image(fill_color="black", back_color="white")
    
    # QR-Code speichern
    img.save(save_path)
    
    # Konsolen-QR-Code anzeigen (einfache ASCII-Version)
    qr.print_ascii()
    
    return save_path

def open_image(image_path):
    """Öffnet ein Bild mit dem Standardprogramm des Betriebssystems"""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(image_path)
        elif system == "Darwin":  # macOS
            subprocess.call(["open", image_path])
        else:  # Linux und andere
            subprocess.call(["xdg-open", image_path])
    except:
        print(f"Konnte das Bild nicht automatisch öffnen. Bitte manuell öffnen: {image_path}")

def main():
    print("Suche lokale IP-Adresse und erstelle Ollama-URL...")
    
    # IP-Adresse ermitteln
    ip_address = get_local_ip()
    if not ip_address or ip_address.startswith("127."):
        print("Warnung: Konnte keine gültige lokale Netzwerk-IP finden. Lokale IP wird verwendet.")
    
    # Ollama-URL erstellen
    ollama_url = f"http://{ip_address}:{OLLAMA_PORT}"
    
    # Prüfen, ob Ollama läuft
    if not check_ollama_running():
        print("\nWarnung: Ollama scheint nicht auf Port {} zu laufen!".format(OLLAMA_PORT))
        print("Stelle sicher, dass der Ollama-Server gestartet ist.")
    
    # Aktuelles Datum und Zeit für den Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Speicherpfad für QR-Code
    home_dir = os.path.expanduser("~")
    qr_code_path = os.path.join(home_dir, f"ollama_url_qrcode_{timestamp}.png")
    
    # QR-Code generieren und anzeigen
    print("\n----------------------------------------------")
    print(f"Ollama läuft auf: {ollama_url}")
    print("----------------------------------------------\n")
    
    print("Generiere QR-Code für einfachen Scan mit der Ollama Android App...")
    qr_code_file = generate_qr_code(ollama_url, qr_code_path)
    
    print(f"\nQR-Code wurde als Bild gespeichert: {qr_code_file}")
    
    # Hinweis zur Verwendung
    print("\nSo verwendest du die URL:")
    print("1. Öffne die Ollama Android App")
    print("2. Gib die oben gezeigte URL ein oder scanne den QR-Code")
    print("3. Stelle sicher, dass dein Smartphone im gleichen WLAN-Netzwerk ist")
    
    # Fragen, ob Bild geöffnet werden soll
    try:
        response = input("\nMöchtest du den QR-Code öffnen? (j/n): ").lower()
        if response in ["j", "ja", "y", "yes"]:
            open_image(qr_code_path)
    except:
        pass

if __name__ == "__main__":
    main()
