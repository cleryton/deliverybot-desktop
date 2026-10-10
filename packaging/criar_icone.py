"""Ícone geométrico do aplicativo, sem dependências de desenho."""
from pathlib import Path
import struct
import zlib


def criar():
    size = 64
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            inside = 3 <= x <= 60 and 3 <= y <= 60
            letter = (19 <= x <= 25 and 17 <= y <= 46 or
                      25 <= x <= 38 and (17 <= y <= 23 or 40 <= y <= 46) or
                      38 <= x <= 44 and 23 <= y <= 40 or
                      33 <= x <= 40 and (20 <= y <= 25 or 38 <= y <= 43))
            rows.extend((255,255,255,255) if letter else (24,125,100,255) if inside else (0,0,0,0))
    def chunk(kind, data):
        return struct.pack('>I',len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0)) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b'')
    ico = struct.pack('<HHH',0,1,1) + struct.pack('<BBBBHHII',size,size,0,0,1,32,len(png),22) + png
    (Path(__file__).parent / 'DeliveryBot.ico').write_bytes(ico)


if __name__ == '__main__':
    criar()
