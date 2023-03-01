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
    state_cols_path = os.path.join(base_path,settings["state_cols"][0])
    with open(state_cols_path, encoding="utf-8") as state_cols_f:
        for line in state_cols_f:
            state_cols.append(line.strip())
    dist_cols_path = os.path.join(base_path,settings["dist_cols"][0])
    with open(dist_cols_path, encoding="utf-8") as dist_cols_f:
        for line in dist_cols_f:
            dist_cols.append(line.strip())

    

def makedirs(path):
    if not os.path.isdir(path):
            os.makedirs(path)

def clear_backlog():
    global backlog
    global values
    backlog = []
    values = []

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
    tables = camelot.read_pdf(pdf_path, pages='all', flag_size=True, process_background=True)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pdf_output_path = os.path.join(base_path,output_path,pdf_name)
    print("Extracted " + str(tables.n) + " tables from " + pdf_path + ", saving at " + pdf_output_path)
    makedirs(pdf_output_path)
    tables.export(os.path.join(pdf_output_path,"table.csv"), f="csv")

def clean_csv(csv_path):
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
        text.replace("\"","")
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
                #Now start matching each column in the data
                #First check if backlog columns are present from previous iteration (and if so, deal with them)
                global backlog
                global prev_file_district #this contains the district of the file from the previous iteration
                #Check if there is a change in district name from prev file, refresh backlog if so
                if prev_file_district != "" and district != prev_file_district:
                    print(str(len(backlog)) + " indices remain in backlog before clearing:")
                    print("Elements in data table: " + str(len(columns_found.keys())))
                    #Clear the backlog, values, etc. lists to populate new elements for the next district/state
                    clear_backlog()
                    print("Change of district from " + prev_file_district + " to " + district)

                #Following lists are to divide "columns found" into actual columns and subheaders
                columns_only_list = [] #Values must only be attributed to actual columns, not headers
                subheaders_only_list = []

                if file_name == 'table-page-121-table-2.csv' and state_name == 'Gujarat':
                    pass #purely for debugging

                #If there are backlog columns which weren't found in the previous csv file, search for them in this one (if not, then search for all columns afresh)
                if len(backlog) > 0:
                    #Make a copy of backlog so we can iterate over the new list while modifying contents of the old one
                    temp_backlog = backlog.copy()
                    for i in range(len(temp_backlog)):
                        column = columns[temp_backlog[i]] #Get column corresponding to the index stored in backlog list
                        escaped_col = r_escape(column) #escape certain characters to not confuse regex
                        col_r = re.compile(r"(?:" + escaped_col + ")")
                        m = col_r.search(text) #Search for the column in the csv file
                        if m: #Column has been found
                            process_col(state_name, district, column)
                            text = col_r.subn("", text, 1)[0] #Remove the found column from the csv file text

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
                        col_r = re.compile("(?:" + escaped_col + ")")
                        m = col_r.search(text) #Search for the column in the csv file
                        if m: #Column has been found
                            process_col(state_name, district, column)
                            text = col_r.subn("", text, 1)[0] #Remove the found column from the csv file text

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
                    text = text.replace("(2019-20)", "", 1).replace("(2019-21)", "", 1).replace("(2015-16)", "", 1).replace("NFHS-5","", 1).replace("NFHS-4", "", 1)
                    values = re.findall(r"\n\s*\"*,*\"*\s*[(]?(?:(\d{1,3}[.]\d)|(\d+,\d{3})|(\d{1,3})|(na)|([*]))",text)
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
    if len(words)>7:
        last4 = r")?\s*(".join(words[-6:])
        text = r"\s*".join(words[:-6]) + r"\s*(" + last4 + ")?"
    else:
        text = r"\s*".join(words)
    return text

#Find the number of headers (Urban, Rural, Total) present in the file, to know number of values per column
def find_headers(text):
    m = re.findall(r"(\n\"?Urban)|(\nRural)|(\n\"?Total\"?)", text)
    return len(m)


def load_csv(csv_path):
    table_dict = {}

    state_name = os.path.split(os.path.dirname(csv_path))[1]
    file_name = os.path.split(csv_path)[1]
    if state_name == "Telangana":
        pass
    match = re.match(r"^table-page-(?P<tablepage>\d+)-table-\d+[.]csv$",file_name)
    if match:
        table_page = match.group("tablepage")
    else:
        table_page = file_name.replace("-table-1","").replace("table-page-", "").replace(".csv")
    with open(csv_path) as file:
        temp_line = file.readline()
        line_i = 1
        nfhs_count = 0
        header_count = (0,0,0)
        urban = 0
        rural =0
        total = 0

        if temp_line.find("Content") != -1: #check 1st line for word "content"
            #Check if this is indeed the first table
            
            if match:
                #It is the first table containing list of all districts. 
                #Iterate through it and remember the page numbers of districts
                if not districts.get(state_name):
                    districts[state_name] = dict() #Add a new dictionary for districts, page_nums for this state
                dist_flag = False
                line = temp_line
                prev_line = ""
                while not dist_flag and line_i<10:
                    if line.strip() != "":
                        prev_line = line
                    line = file.readline()
                    if line == "": #EOF reached
                        dist_flag = True    
                    line_i = line_i + 1
                    match = re.match(r"^\s*District\s*\n$",line)
                    if match:
                        dist_flag = True
                #Now "District" line has been reached. Begin recognition from here:
                #First get line just before district, which contains page number of the state's data
                match = re.match(r"^\s*(?P<statenum>\d+)\"?\s*\n?$",prev_line)
                state_num = "0"
                if match:
                    #Found state page number, enter it into districts dictionary
                    state_num = match.group("statenum")
                    state_num = str(int(state_num))
#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< ADD 6 TO STATE_NUM IF NEEDED
                    if not districts.get(state_name):
                        districts[state_name] = {}
                    districts[state_name][state_num] = state_name
                else: #Page number not above "districts" line (exception)
                    logging.error("Issue at state page number " + state_num + " for " + state_name + " state " + csv_path + " at line: " + line)    
                #Now begin recognition of district page numbers
                text = file.readlines()
                dist_name = ""
                dist_page = ""
                fix_column = None
                for line in text:
                    #First check is the column name to be fixed (is the column # present, Ex. "23. "):
                    match = re.match(r"^(\d+[.])\s*\n$",line)
                    if match:
                        fix_column = match.group(1) #get the column no.
                    else: #Check if it is column to be fixed (was column # present in last line)
                        if fix_column:
                            match = re.match(r"^\s*[A-Z][A-Z\sa-z&.()-]+\s*\n$",line) #see if next line is indeed column name
                            if match:
                                line = fix_column + " " + line
                                fix_column = None
                            else:
                                logging.error("Issue at state page number " + state_num + " for " + state_name + " state " + csv_path + " at line: " + line)
                    match = re.match(r"^\d+[.]\s*(?P<distname>[A-Z][A-Z\sa-z&.()-]+)\s*\n$",line)
                    if match:
                        #DISTRICT NAME
                        dist_name = match.group("distname").strip(" ").replace("  ", " ")
                    else:
                        #Check for page number
                        match = re.match(r"^\s*(?P<pagenum>(\d+)|(\d+\"))\s*\n$",line)
                        if match:
                            #PAGE NUMBER
                            dist_page = match.group("pagenum").replace("\"","").replace(" ", "")
                            dist_page = str(int(dist_page))
#>>>>>>>>>>>>>>>>>>>>>>>>>>>ADD 6 TO DIST_PAGE IF YOU WANT
                            if not districts.get(state_name):
                                districts[state_name] = dict()
                            districts[state_name][dist_page] = dist_name
                            
                            #Henceforth, we can get a district from the state and page number from districts dictionary
            return None
        else: #1st line does not have "content" => it is useful data
            #find number of columns in the data
            match = re.match(r"^\s*\"?NFHS-\d\s*\n$",temp_line)
            if match:
                nfhs_count = nfhs_count + 1
            temp_line = file.readline()
            line_i = 2
            match = re.match(r"^\s*\"?NFHS-\d\s*\n$",temp_line)
            if match:
                nfhs_count = nfhs_count + 1
            text = file.readlines() #read rest of the file
            column=False
            column_name = ""
            column_suffix = ""
            fix_column = None
            forward = True
            values = []
            length = 0
            after_column = False; #this is in case column name is split in two lines

            for line in text:
                blank_match = re.match(r"^\s*\n$",line)
                if blank_match:
                    continue
                line_i = line_i + 1
                match = None
                line = line.replace("\"","")
                if line_i<11: #in the first 9 lines
                    #check for headers
                    urban_m = re.match(r"^\s*\"?(Urban)\s*\n$", line)
                    if urban_m:
                        urban = urban + 1
                        header_count = (urban,rural,total)
                    else:
                        rural_m = re.match(r"^\s*\"?(Rural)\s*\n$", line)
                        if rural_m:
                            rural = rural + 1
                            header_count = (urban,rural,total)
                        else:
                            total_m = re.match(r"^\s*\"?(Total)\s*\n$", line)
                            if total_m:
                                total = total + 1
                                header_count = (urban,rural,total)
                            else:
                                total_m = re.match(r"^\s*(Urban)\s*(Rural)\s*\n$",line)
                                if total_m:
                                    urban = urban + 1
                                    rural = rural + 1
                                    header_count = (urban,rural,total)
                if fix_column:
                    #column must be missing its initial number, check:
                    match = re.match(r"^\s*.*\n$",line)
                    if match:
                        #Column needs to be prefixed with value given in fix_column
                        line = fix_column + " " + match.group()
                        fix_column = None
                        #now let programme check as usual if the line is a column
                
                match = re.match(r"^\d+[.]\s.*\n$",line)
                if match:
                    #it is a column
                    match = pure_name(match.group())
                    if column:
                        #next column found
                        if not forward: #if values preceded column name, save previous values with this column name
                            column_name = pure_name(match) #pure text
                        
                        prev_length = length
                        length = len(values)

                        if length == 0: #no values found
                            if forward==False: #backward, meaning consecutive columns mostly
                                forward = True
                                #nothing more to do in this iteration
                            #...and if it is forward, then no values found makes sense
                        elif length == 8:
                            if forward == True: #easy case
                                forward = False
                                #save the previous column
                                half_vals = values[:4]
                                values = values[4:]
                                #save earlier column with former 4 values
                                insert_to_dict(table_dict,half_vals,column_name,column_suffix, header_count)
                                #save this column with latter 4 values
                                column_name = pure_name(match) #pure text
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        elif length == 4:
                            if prev_length==2:
                                #this means there is reversal of data again
                                if forward == True: #easy case
                                    forward = False
                                    #save the previous column
                                    half_vals = values[:2]
                                    values = values[2:]
                                    #save earlier column with former 4 values
                                    insert_to_dict(table_dict,half_vals,column_name,column_suffix, header_count)
                                    #save this column with latter 4 values
                                    column_name = pure_name(match) #pure text
                                    insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                    values=[]
                            else: #nothing fishy, could be 4 value table
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        elif length == 2: #safest
                            if nfhs_count == 2:
                                #no issues
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                            else: #only 1 column but 2 values
                                #Because we have found a column, it must mean reversal
                                if prev_length == 1:
                                    if forward == True: #easy case
                                        forward = False
                                        #save the previous column
                                        half_vals = values[:1]
                                        values = values[1:]
                                        #save earlier column with former 4 values
                                        insert_to_dict(table_dict,half_vals,column_name,column_suffix, header_count)
                                        #save this column with latter 4 values
                                        column_name = pure_name(match) #pure text
                                        insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                        values=[]
                                    else: #it was backwards and 1 column yet 2 values => fishy
                                        logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)    
                                else:
                                    logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)    
                        elif length == 1:
                            #check if there is indeed only 1
                            if nfhs_count == 1:
                                #no issues
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        else:
                            logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
            
                        column_name = match #update to new column name
                    else:
                        #probably is the first column in the table
                        if not forward:
                            #values have been found and this is first column
                            column_name = match
                        #WHAT DOES FOLLOWING CODE DO?
                        # It checks number of values found. If it finds no values i.e. two consecutive columns
                        # ... then it changes reverses direction of data to forward from backward
                        # If it finds 8 values, and was forward, means now direction has reversed. It does so
                        # ... and saves the new (backwards) column as well. If there are 4 values, it is tricky
                        # ... as it could be reversal of 2 value columns, or a normal 4 value column. It checks
                        # ... if the table has 2 values or 4 and acts accordingly. Any other value shows an issue
                        # ... with the data, and thus a breakpoint is to be kept to fix the data manually
                        
                        prev_length = length
                        length = len(values)

                        if length == 0: #no values found
                            if forward==False: #backward, meaning consecutive columns mostly
                                forward = True
                                #nothing more to do in this iteration
                            #...and if it is forward, then no values found makes sense
                        elif length == 8:
                            if forward == True: #easy case
                                forward = False
                                #save the previous column
                                half_vals = values[:4]
                                values = values[4:]
                                #save earlier column with former 4 values
                                insert_to_dict(table_dict,half_vals,column_name,column_suffix, header_count)
                                #save this column with latter 4 values
                                column_name = pure_name(match) #pure text
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        elif length == 4:
                            if prev_length==2:
                                #this means there is reversal of data again
                                if forward == True: #easy case
                                    forward = False
                                    #save the previous column
                                    half_vals = values[:2]
                                    values = values[2:]
                                    #save earlier column with former 4 values
                                    insert_to_dict(table_dict,half_vals,column_name,column_suffix, header_count)
                                    #save this column with latter 4 values
                                    column_name = pure_name(match) #pure text
                                    insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                    values=[]
                            else: #nothing fishy, could be 4 value table
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        elif length == 2: #safest
                            if nfhs_count == 2:
                                #no issues
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                            else: #only 1 column but 2 values
                                logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)    
                        elif length == 1:
                            #check if there is indeed only 1
                            if nfhs_count == 1:
                                #no issues
                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                values=[]
                        else:
                            logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                        column_name = match #update to new column name
                        column = True
                    after_column = True
                else: #NOT A COLUMN
                    #it is not a column, is it a value?
                    match = re.match(r"^\s*((\d+([,]\d*)?[.]?\d*)|([(]\d+([,]\d*)?[.]?\d*[)])|(na)|([*]))\s*\n$",line)
                    if match: #VALUE
                        match = match.group() #get matched text
                        #IT IS MOST PROBABLY DATA but we need to make sure it is not
                        # a question/column number (expected in this dataset)
                        match2 = re.match(r"^\s*\d+[.]\s*\n$",match)
                        if match2:
                            #It is actually issue in data where # of column and column name are separated
                            #Confirm if this is the case:
                            fix_column = re.sub(r"^\s*(\d+[.])\s*\n$",r"\g<1>",match2.group())
                        else:
                            fix_column = None
                            if column == False or forward == False:
                                #found value before any column, i.e. backwards
                                forward = False
                            values.append(pure_value(match))
                    else: #NOT A VALUE => SOME OTHER TEXT
                        prev_length = length
                        length = len(values)
                        #Is it "Men"/"Women" header?
                        match = re.search(r"^\s*((Men)|(Women))\s*\n$",line) #Man/Woman suffix
                        if match != None:
                            #it is "men" or "women", make it as suffix for following columns (until some other heading shows up)
                            suffix = re.sub(r"^\s*((Men)|(Women))\s*\n$",r"\g<1>",match.group())
                            if  suffix == "Men" or suffix == "Women":
                                #Men or women, add the suffix
                                column_suffix = "_" + suffix
                        else: #NOT men/women header. Is it continuation of column?
                            match = re.match(r"^\s*[a-z]+.*\s*\n$",line)
                            if match: #CONTINUATION OF PREVIOUS COLUMN
                                #most probably is part of the column above, join it there
                                if not forward: #if backward, prev column must have been inserted
                                    prev_col = list(table_dict.keys())[-1]
                                    new_col = re.sub(r"^\s*(?P<colname>.*)((_Women)|(_Men))?((5U)|(5R)|(5T)|(4T))?\s*$",r"\g<colname>",prev_col)
                                    print("debug")
                                    #NOTE: It seems this case never comes. So above regex has NOT BEEN TESTED to work
                                else: #if forward, simply append to column name?
                                    column_name = pure_name(column_name) + " " + remove_blanks(match.group())
                            else: #Not even men/women or continuation of column
                                if forward and column and values:
                                    #It is some other text entirely, if going forward, save column
                                    #If there are no pending values to be written, then no issue
                                    column_suffix = "" #reset column suffix
                                    if length == 0:
                                        pass #nothing to do. No pending values
                                    elif length == 8:
                                        #Data issue, as there are 8 values to be written and less than 2 columns
                                        logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                                    elif length == 4:
                                        if prev_length==2:
                                            #this means there is some issue
                                            logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                                        else:
                                            if forward: #nothing fishy, column's 4 values followed by random text. save column
                                                insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                                values=[]
                                            else:
                                                logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                                    elif length == 2:
                                        if nfhs_count == 2:
                                            #no issues
                                            insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                            values=[]
                                        else: #only 1 column but 2 values
                                            logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)    
                                    elif length == 1:
                                    #check if there is indeed only 1
                                        if nfhs_count == 1:
                                            #no issues
                                            insert_to_dict(table_dict,values,column_name,column_suffix, header_count)
                                            values=[]
                                        else:
                                            logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)    
                                    else:
                                        logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                                else: #random text like headings
                                    column_suffix = ""
                                    if length != 0:
                                        #whom do these values belong to if no column is present?
                                        logging.error("Found " + str(length) + " values in " + csv_path + " at line: " + line)
                                    else:
                                        #do nothing, random text
                                        pass
                    if after_column:
                            after_column = False
    table_df = pd.DataFrame(table_dict, index=[0])
    table_df.name = file_name
    return table_df

def insert_to_dict(table_dict,values,column_name,column_suffix, header_count):
    length = len(values)
    urban, rural, total = header_count
    if length==4:
        #_5_U, _5_R, _5_T, _4_T
        if urban+rural+total==4:
            if urban==1 and rural == 1:
                table_dict[column_name + column_suffix + "_5U"] = values[0]
                table_dict[column_name + column_suffix + "_5R"] = values[1]
                table_dict[column_name + column_suffix + "_5T"] = values[2]
                table_dict[column_name + column_suffix + "_4T"] = values[3]
            else:
                print("debug")
        else:
            print("debug")
        return 1
    elif length==2:
        #_5_T, _4_T
        if urban+rural+total==2:
            if total == 2:
                table_dict[column_name + column_suffix + "_5T"] = values[0]
                table_dict[column_name + column_suffix + "_4T"] = values[1]
            else:
                print("debug")
        else:
            print("debug")
        return 1
    elif length==1:
        #_5_T, _4_T
        table_dict[column_name + column_suffix + "_5T"] = values[0]
    else:
        return 0

def pure_name(column_name):
    return re.sub(r"^\s*\d+[.]\s*(.*)\s*\n$",r"\g<1>",column_name)

def remove_blanks(text):
    return re.sub(r"^\s*(.*)\s*\n$",r"\g<1>",text)

def pure_value(value):
    value = re.sub("[,]","",value)
    return re.sub(r"^\s*(([(]?\d+[.]*\d*[)]?)|(na)|([*]))\s*\n$",r"\g<1>",value)

def get_district(state, page):
    return districts[state][page]
