#This programme collects, preprocesses, analyzes, visualises and models relevant data
#Relevant data - Census, National Family Health Survey, etc. datasets

import os
import collection_lib as cl
import preproc as pp
import pandas as pd


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

pdf_paths = cl.get_pdfs(os.path.join(base_path,resource_path,states_path))
output_folders = cl.get_folders(os.path.join(base_path,output_path),restrict_list)


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
        folder_name = os.path.split(folder)[0]
        table_dfs[folder_name] = []
        tables = os.scandir(folder)
        for table in tables:
            table_ext = os.path.splitext(os.path.basename(table))[1]
            if table_ext == ".csv":
                table_df= pp.load_csv(table.path)
                if table_df is not None:
                    table_dfs[folder_name].append(table_df)
    #Now tables are ready for processing
    for folder in table_dfs:
        clean_path = os.path.join(clean_output_path, folder)
        pp.makedirs(clean_path)
        state_table = pd.DataFrame()
        pd.concat(list(table_dfs), axis=1)
        state_table.to_csv(os.path.join(clean_path,"table.csv"))
print("end")