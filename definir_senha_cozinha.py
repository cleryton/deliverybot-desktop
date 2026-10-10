"""Define (ou troca) a senha de login do painel da cozinha.

A senha digitada NUNCA aparece na tela (nem como asteriscos -- é assim que
o getpass funciona, de propósito) e nunca é guardada em texto puro: só o
hash fica salvo no .env, em COZINHA_SENHA_HASH.

Rode (com o venv ativo):
    python definir_senha_cozinha.py
"""
import getpass
import re
from pathlib import Path

from werkzeug.security import generate_password_hash

ENV_PATH = Path(__file__).parent / ".env"


def main():
    if not ENV_PATH.exists():
        print("Não encontrei o arquivo .env nesta pasta. Rode isso de dentro")
        print("da pasta do projeto (a mesma onde está o .env).")
        return

    print("Defina a senha de login do painel da cozinha.")
    print("(a digitação não aparece na tela -- é esperado, não travou)\n")

    senha = getpass.getpass("Nova senha: ")
    confirmacao = getpass.getpass("Confirme a senha: ")

    if senha != confirmacao:
        print("\nAs senhas não coincidem. Nada foi alterado -- tente de novo.")
        return
    if len(senha) < 6:
        print("\nUse uma senha com pelo menos 6 caracteres. Nada foi alterado.")
        return

    hash_senha = generate_password_hash(senha)
    conteudo = ENV_PATH.read_text(encoding="utf-8")

    # Remove uma eventual COZINHA_SENHA antiga em texto puro (de uma versão
    # anterior do projeto, antes de existir o hash).
    conteudo = re.sub(r"(?m)^COZINHA_SENHA=.*\n?", "", conteudo)

    if re.search(r"(?m)^COZINHA_SENHA_HASH=.*$", conteudo):
        conteudo = re.sub(r"(?m)^COZINHA_SENHA_HASH=.*$", f"COZINHA_SENHA_HASH={hash_senha}", conteudo)
    else:
        conteudo = conteudo.rstrip("\n") + f"\nCOZINHA_SENHA_HASH={hash_senha}\n"

    ENV_PATH.write_text(conteudo, encoding="utf-8")
    print("\nSenha definida. Reinicie o sistema (Flask) para aplicar.")


if __name__ == "__main__":
    main()
