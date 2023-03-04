#This programme collects, preprocesses, analyzes, visualises and models relevant data
#Relevant data - Census, National Family Health Survey, etc. datasets

import os
import collection_lib as cl
import preproc as pp
import pandas as pd
import numpy as np
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
pp.makedirs(os.path.join(base_path,clean_output_path))

table_dfs = {} #dict storing all tables of all states as dataframes
state_offset = {}

pdf_paths = cl.get_pdfs(os.path.join(base_path,resource_path,states_path))
output_folders = cl.get_folders(os.path.join(base_path,output_path),restrict_list)
clean_output_folders = cl.get_folders(os.path.join(base_path,clean_output_path),restrict_list)

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
clean_output_folders.sort(key=numericalSort)

def get_df(columns_list):
    columns = ['Metric','Urban5','Rural5','Total5','Total4']
    columns_df = pd.DataFrame(columns=columns)
    columns_df.index.name = 'Index'
    for column in columns_list.keys():
        row = columns_list[column]
        m = re.search(r"(\d+)\s*[.]\s*(.*)", column)
        if m:
            index = int(m.group(1))
            column = m.group(2)
            for i in range(0,len(row)):
                if row[i] == "na":
                    row[i] = np.nan
            if len(row) == 4:
                row_df = pd.DataFrame(data=[[column, row[0], row[1], row[2], row[3]]],columns=columns)
                columns_df = pd.concat([columns_df, row_df], ignore_index=True)
            elif len(row) == 2:
                row_df = pd.DataFrame(data=[[column, np.nan, np.nan, row[0], row[1]]],columns=columns)
                columns_df = pd.concat([columns_df, row_df], ignore_index=True)
            elif len(row) == 1:
                row_df = pd.DataFrame(data=[[column, np.nan, np.nan, row[0], np.nan]],columns=columns)
                columns_df = pd.concat([columns_df, row_df], ignore_index=True)
            elif len(row) == 0:
                continue
            else:
                return #Error   
        else:
            pass
    return columns_df

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
if len(output_folders)==0: #if there are no folders inside output folder
    pp.set_settings(settings)
    #PREPROCESS DATA OF PDFS
    for pdf_path in pdf_paths:
        pp.read_pdf_table(pdf_path)
if len(clean_output_folders) == 0: #if pdfs are downloaded and also there are folders in output folder i.e. csvs extracted
    pp.set_settings(settings)
    for folder in output_folders:
        folder_name = os.path.split(folder)[1]
        tables = list(os.scandir(folder))
        tables.sort(key=numericalSort)
        for table in tables:
            table_ext = os.path.splitext(os.path.basename(table))[1]
            if table_ext == ".csv":
                pp.load_csv(table.path)
    data = pp.get_data()
    #'Schema' of "data" dict is: data[state][district][column] = [value1, value2,...]
    #Save the data as csv files (in x state folder, y district folder) in the clean output path:
    for state in list(data.keys()):
        state_path = os.path.join(base_path, clean_output_path, state)
        for district in data[state].keys():
            district_path = os.path.join(state_path, district)
            dist_df = get_df(data[state][district])
            pp.makedirs(state_path)
            pp.makedirs(district_path)
            dist_df.to_csv(os.path.join(district_path,"data.csv"))
            data[state][district] = dist_df
else:
    #Read the list of folders (input arg) and return a dict with keys [state][district]
    #data[state][district] = Dataframe object containing all columns and values
    #Scheme of df: Metric, Urban5, Rural5, Total5, Total4
    states = clean_output_folders
    data = {}
    for state in states:
        districts = cl.get_folders(state,restrict_list)
        state_name = os.path.split(state)[1]
        if not data.get(state_name):
            data[state_name] = {}
        for district in districts:
            district_name = os.path.split(district)[1]
            data_paths = cl.get_csvs(district)
            for data_path in data_paths:
                dist_df = pd.read_csv(data_path)
                data[state_name][district_name] = dist_df
                print("Loaded " + state_name + " - " + district_name + ":")
                print(dist_df)
#Now 2D dict "data" contains dataframes of data for each state, district

print("end")


