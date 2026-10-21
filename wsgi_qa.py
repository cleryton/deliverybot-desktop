"""Entrada exclusiva da hospedagem QA; nunca carrega .env ou banco da loja."""
import os
import secrets
from pathlib import Path
import tempfile

if os.environ.get('QA_WEB_HABILITADO')!='SIM':
    raise RuntimeError('Use esta entrada somente no servidor exclusivo de QA.')
os.environ['DELIVERYBOT_ENV_FILE']=os.devnull
os.environ['WHATSAPP_PROVIDER']='TESTE'
os.environ['IA_PROVIDER']=''
os.environ['TUNEL_AUTOMATICO']='NAO'
os.environ['SEED_CATALOGO']='NAO'
pasta=Path(os.environ.get('QA_DATA_DIR') or (Path(tempfile.gettempdir())/'deliverybot-web-qa'))
os.environ['DATABASE_PATH']=str(pasta/'qa.db')
from src.web_qa import criar_app
app=criar_app(pasta,os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('QA_BASE_URL',''),os.environ.get('QA_SESSION_SECRET') or secrets.token_urlsafe(48))
