"""Login do painel da cozinha usando a senha da própria conta do Windows,
como alternativa a manter uma senha separada no .env.

Só funciona no Windows (a conta validada é da máquina que está RODANDO o
Flask, não a de quem está acessando pelo navegador) e requer a biblioteca
pywin32 (pip install pywin32). Se não estiver disponível, `disponivel()`
retorna False e o chamador deve usar o login por senha no .env em vez
disso -- ver config.COZINHA_AUTH_MODO.
"""
import logging

logger = logging.getLogger(__name__)

try:
    import win32con
    import win32security

    _PYWIN32_OK = True
except ImportError:
    _PYWIN32_OK = False


def disponivel() -> bool:
    return _PYWIN32_OK


def validar_credenciais_windows(usuario: str, senha: str) -> bool:
    """True se usuario/senha forem uma conta Windows válida NESTA máquina."""
    if not _PYWIN32_OK:
        logger.warning(
            "COZINHA_AUTH_MODO=WINDOWS mas a biblioteca pywin32 não está "
            "instalada. Rode: pip install pywin32"
        )
        return False
    if not usuario or not senha:
        return False

    handle = None
    try:
        handle = win32security.LogonUser(
            usuario,
            None,  # domínio: None = conta local desta máquina
            senha,
            win32con.LOGON32_LOGON_NETWORK,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
        return True
    except Exception:
        return False
    finally:
        if handle:
            handle.Close()
