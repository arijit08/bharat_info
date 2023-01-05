#This programme collects, preprocesses, analyzes, visualises and models relevant data
#Relevant data - Census, National Family Health Survey, etc. datasets
#Developer - Arijit Bhagavatula

import os # os package
import collection_lib as cl
import preproc as pp


base_path = os.path.dirname(os.path.realpath(__file__))
settings_path = os.path.join(base_path,"settings")

settings = cl.get_settings(os.path.join(settings_path,"paths.txt"))

resource_path = settings["resource_path"][0]
states_path = settings["states_path"][0]
if not os.path.isdir(os.path.join(base_path,resource_path,states_path)):
    os.makedirs(os.path.join(base_path,resource_path,states_path))

pdf_paths = cl.get_pdfs(os.path.join(base_path,resource_path,states_path))

if len(pdf_paths)==0:
    #CODE TO GET DOCUMENTS OF EACH STATE FROM NFHS 5
    urlpath = "http://rchiips.org/nfhs/Factsheet_Compendium_NFHS-5.shtml"

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
else:
    pp.set_settings(settings)
    #PREPROCESS DATA OF PDFS
    for pdf_path in pdf_paths:
        pp.read_pdf(pdf_path)