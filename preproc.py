import platform
from tempfile import TemporaryDirectory
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import PyPDF2
import camelot
import collection_lib as cl
import numpy as np
import re
import logging

settings = {}
poppler_path = ""
output_path = ""

base_path = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(filename= os.path.join(base_path,"preproc_error.log"), level=logging.ERROR, filemode="w")

state_cols = [] #load columns stored for states
dist_cols = [] #load columns stored for districts

backlog = [] #contains columns that weren't recognised in the previous csv file
prev_file_district = "" #district name of the previous csv file

columns_found = {}
values_found = []

districts = dict() #contains state name, district name and page number (in pdf)
offsets = dict() #offset at which first state/district data starts. Useful for understanding page nums in pdf

#Set the params loaded from settings file to settings variable of this code file
def set_settings(settings1):
    settings = settings1
    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = (
            settings["tesseract_path"][0]
        )
        global poppler_path,output_path
        # Windows also needs poppler_exe
        poppler_path = Path(settings["poppler_path"][0])     

    output_path = Path(settings["output_path"][0])

    #Load the columns/scheme for states
    state_cols_path = os.path.join(base_path,settings["state_cols"][0])
    with open(state_cols_path, encoding="utf-8") as state_cols_f:
        for line in state_cols_f:
            state_cols.append(line.strip())
    #Load the columns/schema for districts
    dist_cols_path = os.path.join(base_path,settings["dist_cols"][0])
    with open(dist_cols_path, encoding="utf-8") as dist_cols_f:
        for line in dist_cols_f:
            dist_cols.append(line.strip())

#Function to create directory ("path" arg) if it doesn't exist
def makedirs(path):
    if not os.path.isdir(path):
            os.makedirs(path)

#Whenever there is a change in state or district, the backlog, etc. vars must be cleared
def clear_backlog():
    global backlog
    global values
    backlog = []
    values = []

#Below are some methods to read pdfs: 1. Read via OCR, 2. Extract text, 3. Extract text from tables

#This function converts pages of pdf into images and reads them through OCR
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

            filename = f"{tempdir}/page_{page_enumeration:03}.jpg"

            page.save(filename, "JPEG")
            image_file_list.append(filename)

        makedirs(os.path.join(base_path,output_path))

        with open(text_file, "a+") as output_file:

            for image_file in image_file_list:
 
                text = str(((pytesseract.image_to_string(Image.open(image_file)))))

                text = text.replace("-\n", "")

                output_file.write(text)

#Extract all the text from the pdfs and return it
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

#Use camelot lib to return only the tables in the pdf files
#NOTE: This method is used by the Bharat Info project, as it is more reliable than the above 2 options
def read_pdf_table(pdf_path):
    tables = camelot.read_pdf(pdf_path, pages='all', flag_size=True, process_background=True)
    #Save the data as a csv file in the output folder with the same name as the pdf
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pdf_output_path = os.path.join(base_path,output_path,pdf_name)
    print("Extracted " + str(tables.n) + " tables from " + pdf_path + ", saving at " + pdf_output_path)
    #Create the directories if they do not exist
    makedirs(pdf_output_path)
    tables.export(os.path.join(pdf_output_path,"table.csv"), f="csv")

#Read csv file containing data extracted from the pdf and store the data in a structured dictionary (columns_found)
def load_csv(csv_path):
    contents = False
    state_name = os.path.split(os.path.dirname(csv_path))[1]
    file_name = os.path.split(csv_path)[1]
    match = re.match(r"^table-page-(?P<tablepage>\d+)-table-\d+[.]csv$",file_name)
    if match:
        table_page = match.group("tablepage")
    else:
        table_page = file_name.replace("-table-1","").replace("table-page-", "").replace(".csv")
    if state_name != "Lakshadweep" and state_name != "Chandigarh" and (table_page == "3" or table_page == "4"):
        #Contents page
        contents = True
    with open(csv_path, encoding="utf8") as file:
        text = file.read()
        #EDA of file shows that states have 131 columns, districts have 104
        #So using notepad++ get column names in one file
        #Then find each column in the text. Then look for its values above and below
        text = text.replace("\"","\n")
        text = re.sub("<s>na</s>","na",text) #Special case where camelot for some reason thinks last na in table is superscript
        text = re.sub("<s>[)]</s>",")",text)
        text = re.sub("<s>[(]</s>","(",text)
        text = re.sub("<s>.*?</s>","",text)
        #CHECK IF CONTENTS FILE, STATE FILE OR DIST FILE
        if contents:
            #Read contents file
            dist = re.compile(r"(\d+)\s*[.]\s*([A-Z][A-Za-z&()-.\s]+)")
            state = re.compile(r"^\s*([A-Z][A-Za-z&\s]+)\s*(\d+)")
            pg_no = re.compile(r"(\d+)\s")
            #Find the state name and page number first
            m = state.search(text)
            state_pg_no = None
            if m:
                state_name_r = m.group(1).strip()
                state_pg_no = m.group(2).strip()
                print("state details = ", state_name_r, state_pg_no)
                #Remove the state name, pg no. from the text i.e. return remaining text
                text = state.sub("", text)
            #Find other (district) page numbers in the remaining text
            m = pg_no.findall(text)
            page_no_list = []
            for match in m:
                page_no = str(match).strip()
                page_no_list.append(page_no)
            #Remove district page numbers from text i.e. return the remaining text
            text = pg_no.sub("", text)
            #Search for district names in the remaining text
            m = dist.findall(text)
            districts_list = []
            for match in m:
                district_name = str(match[1]).strip()
                districts_list.append(district_name)
            #Now we have district names, page numbers and state name and page number, store them in dict
            if not districts.get(state_name):
                #If entry for state does not exist in distrct, create it
                districts[state_name] = {}
                if state_pg_no:
                    districts[state_name][state_name] = state_pg_no
                else:
                    logging.debug("state pg no = null")
            for i in range(0,len(districts_list)):
                district = districts_list[i]
                page = page_no_list[i]
                districts[state_name][district] = page
            pass
            #Now calculate offset i.e. page at which difference between contents page no.s and actual page no.
        else:
            #Read data file based on contents
            #First get Chandigarh and Lakshadweep out of the way, they are special cases
            if state_name != "Chandigarh" and state_name != "Lakshadweep":
                #Get offset: Is this the first data table?
                if not offsets.get(state_name):
                    #Yes. Calculate the offset
                    #Find page no of the state
                    state_pg_no = int(districts[state_name][state_name])
                    offset = int(table_page) - state_pg_no
                    offsets[state_name] = offset
                #Is it state or district?
                state_districts = districts[state_name]
                offset = offsets[state_name]
                district_names = list(state_districts.keys())
                district = None
                prev_district_name = district_names[0]
                district_name = prev_district_name
                for district_name in district_names:
                    page_no = int(state_districts[district_name])
                    #page_no contains the contents page no. of a district
                    #for ascending values of page_no, check for which table page - offset is less than page no
                    if int(table_page) < page_no + offset:
                        #Found the district
                        district = prev_district_name
                        break
                    else:
                        prev_district_name = district_name
                if not district:
                    #If above iteration finished without finding district, it means last value of "district_name" was the district
                    district = district_name
                #NOW "district" contains the name of the district/state
                columns = None
                #Now set the columns based on if the file is for a state or a district within a state
                if district == state_name:
                    #It is a state
                    columns = state_cols
                else:
                    #It is a district
                    columns = dist_cols
            else:
                #Lakshadweep or Chandigarh, there are no districts
                district = state_name
                columns = state_cols
            #Now start matching each column in the data
            #First check if backlog columns are present from previous iteration (and if so, deal with them)
            global backlog
            global prev_file_district #this contains the district of the file from the previous iteration
            #Check if there is a change in district name from prev file, refresh backlog if so
            if prev_file_district != "" and district != prev_file_district:
                if len(backlog):
                    logging.error("BACKLOG", "Items remained in backlog for state " + state_name + ", district " + district + ", file " + file_name)
                print("Elements in data table: " + str(len(columns_found.keys())))
                #Clear the backlog, values, etc. lists to populate new elements for the next district/state
                clear_backlog()
                print("Change of district from " + prev_file_district + " to " + district)

            #Following lists are to divide "columns found" into actual columns and subheaders
            columns_only_list = [] #Values must only be attributed to actual columns, not headers
            subheaders_only_list = []

            if file_name == 'table-page-9-table-2.csv' and state_name == 'Andaman_Nicobar_Islands':
                pass #purely for debugging

            #If there are backlog columns which weren't found in the previous csv file, search for them in this one (if not, then search for all columns afresh)
            if len(backlog) > 0:
                #Make a copy of backlog so we can iterate over the new list while modifying contents of the old one
                temp_backlog = backlog.copy()
                for i in range(len(temp_backlog)):
                    column = columns[temp_backlog[i]] #Get column corresponding to the index stored in backlog list
                    escaped_col = r_escape(column) #escape certain characters to not confuse regex
                    col_r = re.compile(r"(" + escaped_col + ")")
                    if column == '104. Blood sugar level - high or very high (>140 mg/dl) or taking medicine to control blood sugar level (%)':
                        pass #purely for debugging
                    m = col_r.search(text) #Search for the column in the csv file
                    if m: #Column has been found
                        process_col(state_name, district, column)
                        text = col_r.subn("\n", text, 1)[0] #Remove the found column from the csv file text

                        #Some part of the column is present after a few lines. These residual columns
                        #...create issues in finding data later, so must be removed:
                        residue = None
                        found_text = ""
                        #First find the part of a column that was recognised (found_text)
                        for group in m.groups():
                            if group == None:
                                residue = "\n" #If residue is not None, then search for it
                            else:
                                if found_text == "":
                                    found_text = group
                                else:
                                    found_text = found_text + r"\s*" + group
                        if residue:
                            #Now remove found_text part from the column name to get residual part
                            residue = re.subn("(" + r_escape(found_text) + ")", "", column, 1)[0]
                            #Now remove the residual part from the text of the csv file
                            text = re.subn("(" + r_escape(residue) + ")", "\n", text, 1)[0]  

                        #Following regex matches columns which start like "23. Some text"
                        m = re.match(r"\d+\s*[.]\s*.*", column)
                        if m:
                            columns_only_list.append(column)
                        else:
                            #Everything else is a subheader
                            subheaders_only_list.append(column)
                        
                        backlog.remove(temp_backlog[i]) #delete the item from backlog (delete by value to avoid issues due to index changing due to deletion of prior elements)
                    else:
                        pass #Place breakpoint here if needed for debugging
            else:
                #No backlog columns present, so search for all columns in this file (and add those not found to backlog)
                for i in range(0, len(columns)):
                    column = columns[i]
                    escaped_col = r_escape(column) #escape certain characters to not confuse regex
                    col_r = re.compile("(" + escaped_col + ")")
                    m = col_r.search(text) #Search for the column in the csv file
                    if m: #Column has been found
                        process_col(state_name, district, column)
                        text = col_r.subn("\n", text, 1)[0] #Remove the found column from the csv file text
                        
                        #Some part of the column is present after a few lines. These residual columns
                        #...create issues in finding data later, so must be removed:
                        residue = None
                        found_text = ""
                        #First find the part of a column that was recognised (found_text)
                        for group in m.groups():
                            if group == None:
                                residue = "\n" #If residue is not None, then search for it
                            else:
                                if found_text == "":
                                    found_text = group
                                else:
                                    found_text = found_text + r"\s*" + group
                        if residue:
                            #Now remove found_text part from the column name to get residual part
                            residue = re.subn("(" + r_escape(found_text) + ")", "", column, 1)[0]
                            #Now remove the residual part from the text of the csv file
                            text = re.subn("(" + r_escape(residue) + ")", "\n", text, 1)[0]

                        #Following regex matches columns which start like "23. Some text"
                        m = re.match(r"\d+\s*[.]\s*.*", column)
                        if m:
                            columns_only_list.append(column)
                        else:
                            #Everything else is a subheader
                            subheaders_only_list.append(column)
                        
                        try:
                            backlog.remove(i) #attempt to delete the found column from backlog just in case it is present in it
                        except ValueError as e:
                            pass
                    else:
                        #It did not find the column text in this file
                        #Either because the column in the file is not proper
                        # or because the column is present in the next file
                        #Soln: add it to a backlog dictionary, search for it in the next file
                        backlog.append(i) #Store index of column that is not found in "backlog" list
            #Now find values for columns that are found, first find how many values per column from the # of headers
            #Header means the "Urban", "Rural", "Total" master column names found at beginning of a file
            header_count = find_headers(text)
            #Check if number of headers found is as per the data (upto 4, at least 1)
            if header_count >=1 and header_count <= 4:
                #Values are thus: 100.0 32.0 1,341 654 na * thus the following pattern:
                text = text.replace("(2015-16)", "", 1).replace("NFHS-5","", 1).replace("(2019-20)", "", 1).replace("(2019-21)", "", 1).replace("(2020-21)", "", 1).replace("NFHS-4", "", 1)
                values = re.findall(r"\n\s*\"*,*\"*(?:[(]%[)])?\s*[(]?(?:(\d{1,3}[.]\d)|(\d+,\d{3})|(\d{1,3})|(na)|([*]))",text)
                values = np.array(values)
                #28/02/23 - filter out '', None, etc. values from np array
                values = values[values != '']
                
                columns_count = len(columns_only_list)
                subheader_count = len(subheaders_only_list)
                #Check if values can be divided evenly into number of headers (= Urban, Rural, Total) found
                if len(values)%header_count == 0:
                    #Check if values can be exactly divided into #header_count columns and #columns_count rows
                    if len(values)/header_count == columns_count:
                        for i in range(0, len(values)):
                            #put every header_count (Ex. 4) values into each column
                            col_i = int(i/header_count)
                            #Avoid attributing the values to subheaders by using "columns_only_list" instead of "columns"
                            columns_found[state_name][district][columns_only_list[col_i]].append(values[i])
                    else:
                        logging.error("Values are for " + str(len(values)/header_count) + " columns but state columns are " + str(len(columns_found)))
                else:
                    logging.error("Header count must be off because " + str(len(values)) + " values cannot be cleanly divided into " + str(header_count) + " headers")
            else:
                logging.error("Found " + str(header_count) + " headers in file " + file_name)
            prev_file_district = district

#When a column in found in the file, process it (add it to "columns_found" 3D dictionary)
def process_col(state, district, column):
    global columns_found
    if not columns_found.get(state): #Create if not exist
        columns_found[state] = {}
    if not columns_found[state].get(district): #Create if not exist
        columns_found[state][district] = {}
    if not columns_found[state][district].get(column): #Create if not exist
        columns_found[state][district][column] = []

#Function to escape certain characters so they may be used in regex expressions
def r_escape(text):
    text = text.replace(".", "[.]").replace("(", "[(]").replace(")", "[)]") #escape following regex characters: ".","(",")"
    words = re.split(r'\s', text)
    if len(words)>8:
        last4 = r")?\s*(".join(words[-7:])
        text = r"\s*".join(words[:-7]) + r"\s*(" + last4 + ")?"
    else:
        text = r"\s*".join(words)
    return text

#Find the number of headers (Urban, Rural, Total) present in the file, to know number of values per column
def find_headers(text):
    m = re.findall(r"(\n\"?Urban)|(\nRural)|(\n\"?Total\"?)", text)
    return len(m)

def get_data():
    return columns_found