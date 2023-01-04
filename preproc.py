import platform
from tempfile import TemporaryDirectory
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def read_pdf(filepath):
    with open(filepath,'rb') as f:
        pdf = PdfFileReader(f)
        for i in range(pdf.getNumPages()):
            page = pdf.getPage(i)
            content = page.getContents()
            


