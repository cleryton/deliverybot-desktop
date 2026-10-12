"""Segredos do terminal protegidos pela conta Windows, sem dependências da loja."""
import ctypes
import os
from ctypes import wintypes


def dpapi(dados, abrir=False):
    if os.name != 'nt':
        raise ValueError('A proteção das credenciais do terminal requer Windows.')
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(dados)
    extra=ctypes.create_string_buffer(b'DeliveryBot-terminal-v1')
    entrada=Blob(len(dados),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    entropy=Blob(len(b'DeliveryBot-terminal-v1'),ctypes.cast(extra,ctypes.POINTER(ctypes.c_ubyte)))
    saida=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    func=crypt.CryptUnprotectData if abrir else crypt.CryptProtectData
    func.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    func.restype=wintypes.BOOL
    if not func(ctypes.byref(entrada),None,ctypes.byref(entropy),None,None,1,ctypes.byref(saida)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(saida.pbData,saida.cbData)
    finally:
        kernel=ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(saida.pbData,ctypes.c_void_p))
