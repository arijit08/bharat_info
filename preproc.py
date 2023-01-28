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

logging.basicConfig(filename= os.path.join(base_path,"preproc_error.log"), level=logging.ERROR)

districts = dict()

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
