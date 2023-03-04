# Bharat Info
 This project aims to take *authentic* data from different (typically government) sources, which describes India's demography, geography, sociography, etc., and load into a combined data warehouse for visualisation and analytics
 
 Datasets currently planned to include:
 1. National Family Health Survey (NFHS 5) (MoHFW) - Done 100%
 2. Census 2011 (MoH) [Waiting for 2021 to be released]
 3. National Crime Records Bureau (NCRB 2023) (MoH)
 4. Forest Survey of India (FSI 2023) (MoEFCC)
 
 The data is unfortunately not clean at all, there are typos in the tables which make automatic extraction difficult, the data is typically published in PDF files which makes extraction a complete nightmare
 
 This project is coded in Python, utilising its many libraries for collection, wrangling, cleaning, processing, loading, etc.
 
 The stack:
 1. Scraping using Selenium
 2. Extracting tables from pdfs using Camelot
 3. OCR using PyTesseract
 4. Cleaning using Re (Regex), Numpy and Pandas
 5. Load to Pandas dataframe and save as .csv files
 
 The project is planned to shift to PySpark soon. Currently the scale of data does not warrant distributed systems, but as more and more datasets are added, and considering the objective of this project is to create a super database where one can join any table with any other table (and find, for instance, the correlation of crime with deforestation, or that of vehicles owned with cases of Diabetes
