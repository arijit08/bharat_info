import os

output_path = "C:/Users/08arijit/Documents/Data Science and Machine Learning/Data projects/Bharata Info/resource/states/output"
folders = ["C:/Users/08arijit/Documents/Data Science and Machine Learning/Data projects/Bharata Info/resource/states/output/Uttar_Pradesh", "C:/Users/08arijit/Documents/Data Science and Machine Learning/Data projects/Bharata Info/resource/states/output/West_Bengal"]

import re
for folder in folders:
    files = os.scandir(folder)
    for file in files:
            filename = file.name
            match = re.match(r"^table-page-(\d+)-table-(\d)[.]csv$", filename)
            if match:
                    tablenum = match.group(2)
                    pagenum = match.group(1)
                    if tablenum == "2":
                            table1 = file.path.replace("table-2", "table-1")                                             
                            os.remove(table1)