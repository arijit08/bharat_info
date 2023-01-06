import platform
from tempfile import TemporaryDirectory
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import PyPDF2
import camelot
import pandas as pd
import re
import logging

settings = {}
poppler_path = ""
output_path = ""

base_path = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(filename="preproc_error.log", level=logging.ERROR)

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

def load_csv(csv_path):
    table_dict = {}
    with open(csv_path) as file:
        seek = 1
        if file.readline().find("Content") != -1: #check 1st line for word "content"
            return None
        else: #1st line does not have "content" => it is useful data
            text = file.readlines() #read rest of the file
            column=False
            column_name = ""
            forward = True
            values = []
            for line in text:
                match = re.findall(r"^\d+[.]\s.*\n$",line)
                if match:
                    #it is a column
                    match = match[0]
                    if column:
                        #next column found, save previous column + values
                        length = len(values)
                        if not forward: #if values preceded column name, save previous values with this column name
                            column_name = match
                        column_name = re.sub(r"^\d+[.]*\d*\s(.*)\s\n$",r"\g<1>",column_name) #pure text
                        if length==4:
                            #_5_U, _5_R, _5_T, _4_T
                            table_dict[column_name + "_5U"] = values[0]
                            table_dict[column_name + "_5R"] = values[1]
                            table_dict[column_name + "_5T"] = values[2]
                            table_dict[column_name + "_4T"] = values[3]
                            values = []
                        elif length==2:
                            #_5_T, _4_T
                            table_dict[column_name + "_5T"] = values[0]
                            table_dict[column_name + "_4T"] = values[1]
                            values = []
                        column_name = match #update to new column name
                    else:
                        if not forward:
                            #values have been found and this is first column
                            column_name = match
                        column_name = re.sub(r"^\d+[.]*\d*\s(.*)\s\n$",r"\g<1>",column_name)#pure text
                        length = len(values)
                        if length==4:
                            #_5_U, _5_R, _5_T, _4_T
                            table_dict[column_name + "_5U"] = values[0]
                            table_dict[column_name + "_5R"] = values[1]
                            table_dict[column_name + "_5T"] = values[2]
                            table_dict[column_name + "_4T"] = values[3]
                            values = []
                        elif length==2:
                            #_5_T, _4_T
                            table_dict[column_name + "_5T"] = values[0]
                            table_dict[column_name + "_4T"] = values[1]
                            values = []
                        column_name = match #update to new column name
                        #we have found a column, get its pure text
                        column = True
                else:
                    #it is not a column, is it a value?
                    match = re.findall("^((\d+[.]*\d*)|(na)|([*]))\s*\n$",line)
                    if match:
                        match = match[0][0]
                        #it is a value, does it follow a column or precede?
                        if column == False or forward == False:
                            #found value before any column, i.e. backwards
                            forward = False
                        values.append(match)
                    else:
                        #it is some other text, if forward, column are true and values aren't empty, save
                        if forward and column and values:
                            if length==4:
                                #_5_U, _5_R, _5_T, _4_T
                                table_dict[column_name + "_5U"] = values[0]
                                table_dict[column_name + "_5R"] = values[1]
                                table_dict[column_name + "_5T"] = values[2]
                                table_dict[column_name + "_4T"] = values[3]
                                values = []
                            elif length==2:
                                #_5_T, _4_T
                                table_dict[column_name + "_5T"] = values[0]
                                table_dict[column_name + "_4T"] = values[1]
                                values = []
                        else: #output error, verify later
                            logging.error("File [" + file.name + "], line [" + line +
                             "], forward=" + str(forward) + ", column=" + str(column) +
                             ", values=" + str(values) + ", column_name [" + column_name + "]")
    return pd.DataFrame(table_dict)
