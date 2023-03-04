#This file shall scrape relevant data from websites

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException,ElementNotSelectableException,ElementNotVisibleException, TimeoutException
import os
import wget

DRIVER_PATH = '/path/to/chromedriver'
options = Options()
options.headless = True #Do you want to see the browser window while scraping (True) or no (False)
driver = None

def load_browser():
    driver = webdriver.Chrome(options=options, executable_path=DRIVER_PATH)

#navigate browser to a url
def load_page(urlpath):
    driver.get(urlpath)

#wait for maximum t seconds until a webpage loads by polling every n seconds to check if an x element is clickable
def wait_until(timeout_s, every_s, idname):
    wait = WebDriverWait(driver,timeout=timeout_s,poll_frequency=every_s,ignored_exceptions=[NoSuchElementException, ElementNotSelectableException, ElementNotVisibleException, TimeoutException])
    wait.until(EC.element_to_be_clickable(((By.ID,idname))))

#get current URL that the browser is in
def get_url():
    driver.current_url

#append a relative URL to a base url (after removing the filename of the latter)
def absolutise_url(base_url,rel_url):
    base = os.path.dirname(base_url)
    return base+"/"+rel_url

def get_element(idname):
    return driver.find_element(By.ID,idname)

#select the nth item in a select element (dropdown box)
def select_index(idname, index):
    select = Select(get_element(idname))
    select.select_by_index(index)

def get_attr(element,attrname):
    return element.get_attribute(attrname)

def get_elements(idname,tagname):
    return get_element(idname).find_elements(By.TAG_NAME,tagname)

def dl(state_link, urlpath):
    return wget.download(state_link, urlpath)

def get_settings(settings_path):
    settings = {}
    for line in open(settings_path,"r"):
        key,val = line.strip().split(" ",1)
        settings[key] = [val]
    return settings

def is_empty(folder_path):
    files_list = list(os.scandir(folder_path))
    if len(files_list) == 0:
        return True
    else:
        return False

def get_pdfs(folder_path):
    pdfs = []
    for filename in os.scandir(folder_path):
        extension = os.path.splitext(filename)[1]
        if extension==".pdf":
            pdfs.append(filename.path)
    return pdfs

def get_csvs(folder_path):
    csvs = []
    folders_list = [folder_path]
    folders_list.extend(get_folders_r(folder_path))
    for folder in folders_list:
        files = os.scandir(folder)
        for file in files:
            if os.path.splitext(file.path)[1] == ".csv":
                csvs.append(file.path)
    return csvs
            
    for folder in folders_list:
        for file_name in os.scandir(folder):
            extension =  os.path.splitext(file_name)[1]
            if extension == ".csv":
                csvs.append(file_name)
    return csvs

def get_folders(folder_path, restrict_list):
    folders = []
    for item in os.scandir(folder_path):
        if item.path not in restrict_list:
            folders.append(item.path)
    return folders

def get_folders_r(path): #r implies recursive, gives exhaustive list of all folders and subfolders in a path
    folders = []
    for item in os.scandir(path):
        if item.is_dir and not item.is_file:
            folders.append(item.path)
            folders.extend(get_folders_r(item.path))
    return folders