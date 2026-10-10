"""Consulta os avisos públicos do PyPI para as versões fixadas no projeto."""
import concurrent.futures
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def verificar(linha):
    nome, versao = linha.split("==")
    try:
        url = f"https://pypi.org/pypi/{nome}/{versao}/json"
        with urllib.request.urlopen(url, timeout=20) as response:
            dados = json.load(response)
        return {"pacote": nome, "versao": versao, "avisos": [
            {"id": v["id"], "corrigido_em": v.get("fixed_in", []), "fonte": v.get("link")}
            for v in dados.get("vulnerabilities", [])]}
    except Exception:
        return {"pacote": nome, "versao": versao, "erro": "Consulta indisponível"}


def main():
    linhas = [r.strip() for r in (ROOT / "requirements-desktop.lock.txt").read_text().splitlines()
              if re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", r.strip())]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        resultados = list(executor.map(verificar, linhas))
    avisos = sum(len(r.get("avisos", [])) for r in resultados)
    indisponiveis = sum("erro" in r for r in resultados)
    relatorio = {"fonte": "https://pypi.org", "pacotes": len(resultados), "avisos": avisos,
                 "consultas_indisponiveis": indisponiveis, "resultados": resultados}
    destino = ROOT / "artifacts/auditoria-python.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in relatorio.items() if k != "resultados"}))
    for r in resultados:
        if r.get("avisos") or "erro" in r:
            print(json.dumps(r))
    return 1 if avisos else 2 if indisponiveis else 0


if __name__ == "__main__":
    sys.exit(main())
