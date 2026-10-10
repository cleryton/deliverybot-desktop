"""Gera valores aleatorios fortes para preencher as variaveis de seguranca
do .env que sao usadas por maquinas, nao digitadas por humanos (WEBHOOK_SECRET,
WAHA_DASHBOARD_PASSWORD, WAHA_API_KEY).

A senha do painel da cozinha NAO e gerada aqui -- ela e uma senha que uma
pessoa precisa digitar para entrar, entao tem um script proprio que nunca
mostra nem guarda o valor em texto puro:
    python definir_senha_cozinha.py

Rode SEMPRE localmente, na sua maquina:   python gerar_segredos.py

Importante: cole os valores direto no seu .env. Nunca cole esses valores
em um chat, print de tela, grupo ou repositorio publico -- qualquer
segredo que aparecer em texto em algum lugar deve ser considerado exposto
e trocado de novo.
"""
import secrets

print("Copie cada linha abaixo para a variavel correspondente no seu .env:\n")
print(f"WEBHOOK_SECRET={secrets.token_urlsafe(24)}")
print(f"WAHA_DASHBOARD_PASSWORD={secrets.token_urlsafe(16)}")
print(f"WAHA_API_KEY={secrets.token_urlsafe(24)}")
print("\nDepois de colar os novos valores, reinicie o Flask e rode:")
print("  docker compose down && docker compose up -d")
print("(o WAHA precisa subir de novo para ler o novo WAHA_API_KEY/senha).")
print("\nPara a senha do painel da cozinha, rode: python definir_senha_cozinha.py")
