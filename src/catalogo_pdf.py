"""Catálogo para clientes: usa somente produtos disponíveis e dados públicos."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
import threading
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab import __file__ as reportlab_arquivo
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from . import cardapio, config
from .db import get_conn

_font_lock = threading.Lock()


def _fontes():
    with _font_lock:
        if 'DeliveryBotPDF' not in pdfmetrics.getRegisteredFontNames():
            pasta = Path(reportlab_arquivo).parent / 'fonts'
            pdfmetrics.registerFont(TTFont('DeliveryBotPDF', str(pasta/'Vera.ttf')))
            pdfmetrics.registerFont(TTFont('DeliveryBotPDFBold', str(pasta/'VeraBd.ttf')))


def _texto(valor):
    permitido = pdfmetrics.getFont('DeliveryBotPDF').face.charToGlyph
    return escape(''.join(c if ord(c) in permitido else '?' for c in str(valor)).replace('\x00', ''))


def gerar(mostrar_quantidades=False):
    _fontes()
    with get_conn() as conn:
        produtos = [dict(p) for p in conn.execute('SELECT p.*,f.dados AS foto FROM produtos p '
            'LEFT JOIN fotos_produto f ON f.produto_id=p.id WHERE p.ativo=1 AND (p.estoque IS NULL OR p.estoque>0) '
            'ORDER BY p.categoria,p.nome')]
    from .estoque import nome_completo
    saida = BytesIO()
    verde = colors.HexColor('#17634f')
    tinta = colors.HexColor('#1c3038')
    cinza = colors.HexColor('#54696c')
    estilo = ParagraphStyle('produto',fontName='DeliveryBotPDF',fontSize=9.5,leading=14,textColor=tinta)
    titulo = ParagraphStyle('titulo',parent=estilo,fontName='DeliveryBotPDFBold',fontSize=23,leading=29,textColor=verde)
    categoria = ParagraphStyle('categoria',parent=estilo,fontName='DeliveryBotPDFBold',fontSize=13,leading=20,textColor=verde,spaceAfter=8)
    pequeno = ParagraphStyle('pequeno',parent=estilo,fontSize=8,leading=12,textColor=cinza)
    preco = ParagraphStyle('preco',parent=estilo,fontName='DeliveryBotPDFBold',alignment=TA_RIGHT,textColor=verde)
    cabecalho = ParagraphStyle('cabecalho',parent=estilo,fontName='DeliveryBotPDFBold',textColor=colors.white)
    doc = SimpleDocTemplate(saida,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=38,bottomMargin=45,
        title='Catálogo de produtos',author='DeliveryBot',pageCompression=1)
    agora = datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y às %H:%M (UTC-3)')
    conteudo = [Paragraph(_texto(config.NOME_RESTAURANTE),titulo),Spacer(1,10),
        Paragraph('Catálogo de produtos disponíveis',categoria),
        Paragraph(_texto('Emitido em '+agora),pequeno),Spacer(1,9),
        Paragraph('Preços e disponibilidade podem mudar após a emissão. Confirme seu pedido com a loja.',pequeno),Spacer(1,8)]
    if not produtos:
        conteudo.append(Paragraph('O catálogo está sendo preparado. Consulte a loja para conhecer os próximos produtos.',estilo))
    for nome, itens in cardapio.agrupar_por_categoria(produtos).items():
        linhas = [[Paragraph(_texto(nome),categoria),'',''],
                  [Paragraph('Foto',cabecalho),Paragraph('Produto',cabecalho),Paragraph('Preço',cabecalho)]]
        for item in itens:
            foto = Paragraph('Sem foto',pequeno)
            if item['foto']:
                with PILImage.open(BytesIO(item['foto'])) as imagem:
                    imagem.thumbnail((180,180))
                    imgbytes = BytesIO()
                    imagem.convert('RGB').save(imgbytes,format='JPEG',quality=75)
                    largura,altura=imagem.size
                escala = min(58/largura,58/altura)
                imgbytes.seek(0)
                foto = Image(imgbytes,width=largura*escala,height=altura*escala)
            disponibilidade = 'Disponível'
            if mostrar_quantidades and item['estoque'] is not None:
                disponibilidade = 'Estoque: '+format(Decimal(str(item['estoque'])),'f').rstrip('0').rstrip('.') if '.' in str(item['estoque']) else 'Estoque: '+str(item['estoque'])
                disponibilidade += ' '+item['unidade']
            detalhe = _texto(nome_completo(item))+'<br/>'+_texto(disponibilidade)
            if item['descricao']:
                detalhe += '<br/>'+_texto(item['descricao'][:240])
            valor = format(Decimal(str(item['preco'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f').replace('.',',')
            linhas.append([foto,Paragraph(detalhe,estilo),Paragraph('R$ '+valor+'<br/>'+_texto('/ '+item['unidade']),preco)])
        tabela = Table(linhas,colWidths=[76,344,99],repeatRows=2,hAlign='LEFT',spaceBefore=10)
        tabela.setStyle(TableStyle([('SPAN',(0,0),(-1,0)),('BACKGROUND',(0,1),(-1,1),verde),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
            ('LINEBELOW',(0,2),(-1,-1),.5,colors.HexColor('#dce7e1')),
            ('ROWBACKGROUNDS',(0,2),(-1,-1),[colors.white,colors.HexColor('#f4f8f5')])]))
        conteudo.append(tabela)
    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont('DeliveryBotPDF',8)
        canvas.setFillColor(cinza)
        canvas.drawString(38,24,'Pedido direto com a loja | Catálogo para clientes')
        canvas.drawRightString(A4[0]-38,24,'Página '+str(documento.page))
        canvas.restoreState()
    doc.build(conteudo,onFirstPage=rodape,onLaterPages=rodape)
    return saida.getvalue()
