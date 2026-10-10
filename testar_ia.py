"""Diagnóstico da IA, sem WhatsApp. Rode na pasta do projeto:  python testar_ia.py"""
import requests

from src import config
from src.db import init_db

print("IA_PROVIDER :", repr(config.IA_PROVIDER))
print("OLLAMA_URL  :", config.OLLAMA_URL)
print("OLLAMA_MODEL:", repr(config.OLLAMA_MODEL))

if config.IA_PROVIDER == "OLLAMA":
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        nomes = [m["name"] for m in r.json().get("models", [])]
        print("Modelos instalados no Ollama:", nomes)
        if config.OLLAMA_MODEL not in nomes:
            print(f">>> PROBLEMA: '{config.OLLAMA_MODEL}' não está na lista acima. Ajuste OLLAMA_MODEL no .env.")
    except Exception as exc:
        print(">>> PROBLEMA: Ollama não responde:", exc)

from src import ia

init_db()
print("\nTestando uma resposta (a 1ª vez pode demorar, o modelo carrega na memória)...")
try:
    print("RESPOSTA:", ia.responder("5500000000000", "oi, qual o horario de voces?"))
except ia.IAIndisponivel as exc:
    print(">>> IA indisponível:", exc)
