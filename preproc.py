import platform
from tempfile import TemporaryDirectory
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import PyPDF2
import camelot
import pandas

settings = {}
poppler_path = ""
output_path = ""
base_path = os.path.dirname(os.path.realpath(__file__))

def set_settings(settings1):
    settings = settings1
    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = (
            settings["tesseract_path"][0]
        )

        global poppler_path,output_path
        # Windows also needs poppler_exe
        poppler_path = Path(settings["poppler_path"][0])     
        
        # Put our output files in a sane place...
        output_path = Path(settings["output_path"][0])
    else:
        output_path = Path(settings["output_path"][0])
        # Store all the pages of the PDF in a variable

def makedirs(path):
    if not os.path.isdir(path):
            os.makedirs(path)


def read_pdf_ocr(pdf_path):

    image_file_list = []

    pdf_file = Path(pdf_path)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    text_file = os.path.join(base_path, output_path, pdf_name+".txt")

    with TemporaryDirectory() as tempdir:

        if platform.system() == "Windows":
            pdf_pages = convert_from_path(
                pdf_file, 500, poppler_path=poppler_path
            )
        else:
            pdf_pages = convert_from_path(pdf_file, 500)

        for page_enumeration, page in enumerate(pdf_pages, start=1):

            filename = f"{tempdir}\page_{page_enumeration:03}.jpg"

            page.save(filename, "JPEG")
            image_file_list.append(filename)

        makedirs(os.path.join(base_path,output_path))
        
        with open(text_file, "a+") as output_file:

            for image_file in image_file_list:
 
                text = str(((pytesseract.image_to_string(Image.open(image_file)))))

                text = text.replace("-\n", "")

                output_file.write(text)




def read_pdf_txt(pdf_path):
    with open(pdf_path,"rb") as file:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        txt_output_path = os.path.join(base_path,output_path, "extracted text")
        makedirs(txt_output_path)
        with open(os.path.join(txt_output_path, pdf_name +'.txt'),"w+", encoding='utf-8') as output:
            pdf_file = PyPDF2.PdfReader(file)
            for i in range(len(pdf_file.pages)):
                page = pdf_file.pages[i]
                extracted_text = page.extract_text()
                output.write(extracted_text)

def read_pdf_table(pdf_path):
    tables = camelot.read_pdf(pdf_path, pages='1-end')
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pdf_output_path = os.path.join(base_path,output_path,pdf_name)
    print("Extracted " + str(tables.n) + " tables from " + pdf_path + ", saving at " + pdf_output_path)
    makedirs(pdf_output_path)
    tables.export(os.path.join(pdf_output_path,"table.csv"), f="csv")
