#This programme collects, preprocesses, analyzes, visualises and models relevant data
#Relevant data - Census, National Family Health Survey, etc. datasets

import os
import collection_lib as cl
import preproc as pp
import pandas as pd
import re


base_path = os.path.dirname(os.path.realpath(__file__))
settings_path = os.path.join(base_path,"settings")

settings = cl.get_settings(os.path.join(settings_path,"paths.txt"))

resource_path = settings["resource_path"][0]
states_path = settings["states_path"][0]
output_path = settings["output_path"][0]
clean_output_path = settings["clean_output_path"][0]
restrict_list = [base_path, resource_path,states_path, output_path,clean_output_path]

pp.makedirs(os.path.join(base_path,output_path))

table_dfs = {} #dict storing all tables of all states as dataframes
state_offset = {}

pdf_paths = cl.get_pdfs(os.path.join(base_path,resource_path,states_path))
output_folders = cl.get_folders(os.path.join(base_path,output_path),restrict_list)

numbers = re.compile(r'(\d+)')

def numericalSort(value):
    if type(value) is not str:
        value = value.path
    parts = numbers.split(value)
    parts[1::2] = map(int, parts[1::2])
    return parts

def page_to_district(state, page_num):
    state_districts = pp.districts[state]
    pages = list(state_districts.keys())
    pages.sort(key=numericalSort)
    offset = state_offset[state] #at what page the data actually starts
    page = pages[0]
    prev_page = page
    real_page_num = int(page_num)-offset
    for page in pages:
        if real_page_num >= int(page):
            prev_page = page
        else: #found the page for the district, return its starting point
            break
    return state_districts[prev_page] #must be last district if any at all

def second_page(page_nums):
    page_nums.sort()
    return page_nums[1]

output_folders.sort(key=numericalSort)


if len(pdf_paths)==0:
    #CODE TO GET DOCUMENTS OF EACH STATE FROM NFHS 5
    urlpath = "http://rchiips.org/nfhs/Factsheet_Compendium_NFHS-5.shtml"

    cl.load_browser()
    cl.load_page(urlpath)

    first_index=1 #0 if first element is to be considered, else 1
    idname = "state" #dropdown containing indian states
    tagname = "option"

    cl.wait_until(5,1,idname)

    states = cl.get_elements(idname,tagname)
    count = len(states)

    pdf_paths = []

    #get url in value attribute of option tag of select element, and download it
    for i in range(first_index,count):
        value = cl.get_attr(states[i],"value")
        state_link = cl.absolutise_url(base_url=urlpath,rel_url=value)
        cl.dl(state_link, os.path.join(base_path,resource_path,states_path))
    #ALL DOCUMENTS DOWNLOADED
    pdf_paths = cl.get_pdfs(os.path.join(base_path,resource_path,states_path))
elif len(output_folders)==0: #if there are no folders inside output folder
    pp.set_settings(settings)
    #PREPROCESS DATA OF PDFS
    for pdf_path in pdf_paths:
        pp.read_pdf_table(pdf_path)
else: #if pdfs are downloaded and also there are folders in output folder i.e. csvs extracted
    pp.set_settings(settings)
    for folder in output_folders:
        folder_name = os.path.split(folder)[1]
        table_dfs[folder_name] = []
        tables = list(os.scandir(folder))
        tables.sort(key=numericalSort)
        for table in tables:
            table_ext = os.path.splitext(os.path.basename(table))[1]
            if table_ext == ".csv":
                table_df = pp.clean_csv(table.path)
                continue
                table_df = pp.load_csv(table.path)
                if table_df is not None:
                    table_dfs[folder_name].append(table_df)
    #Now tables are ready for processing
    for folder in table_dfs.keys():
        clean_path = os.path.join(base_path, clean_output_path, folder)
        pp.makedirs(clean_path)
        district_tables = {}
        page_nums = []
        for table in table_dfs[folder]:
            print(table.name)
            page_num = int(table.name.replace("table-page-","").replace("-table-1.csv",""))
            page_nums.append(page_num)
            offset = page_nums[0] #get first (non contents) table's page number to know offset
            if offset:
                offset = offset - 1 #as page numbers start counting from 1
                state_offset[folder] = offset
            else:
                pass #breakpoint here
            state = str(folder)
            district = page_to_district(state,page_num) #found district the table corresponds to
            district_table = district_tables.get(district)
            if district_table is not None:
                district_tables[district] = table #if no table for this district, put this table
            else:
                district_tables[district] = pd.concat([district_table,table], axis=1)

        for district in district_tables.keys():
            district_tables[district].to_csv(os.path.join(clean_path, str(district) + ".csv"))
        #state_table = pd.concat(list(table_dfs[folder]), axis=1)
        #state_table.to_csv(os.path.join(clean_path,"table.csv"))
print("end")
