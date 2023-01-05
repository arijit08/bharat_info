import platform
from tempfile import TemporaryDirectory
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import PyPDF2

settings = {}
poppler_path = ""
output_path = ""
base_path = os.path.dirname(os.path.realpath(__file__))

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


def read_pdf_ocr(pdf_path):

    image_file_list = []

    pdf_file = Path(pdf_path)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    text_file = os.path.join(base_path, output_path, pdf_name+".txt")

    ''' Main execution point of the program'''
    with TemporaryDirectory() as tempdir:
        # Create a temporary directory to hold our temporary images.
 
        """
        Part #1 : Converting PDF to images
        """
 
        if platform.system() == "Windows":
            pdf_pages = convert_from_path(
                pdf_file, 500, poppler_path=poppler_path
            )
        else:
            pdf_pages = convert_from_path(pdf_file, 500)
        # Read in the PDF file at 500 DPI
 
        # Iterate through all the pages stored above
        for page_enumeration, page in enumerate(pdf_pages, start=1):
            # enumerate() "counts" the pages for us.
 
            # Create a file name to store the image
            filename = f"{tempdir}\page_{page_enumeration:03}.jpg"
 
            # Declaring filename for each page of PDF as JPG
            # For each page, filename will be:
            # PDF page 1 -> page_001.jpg
            # PDF page 2 -> page_002.jpg
            # PDF page 3 -> page_003.jpg
            # ....
            # PDF page n -> page_00n.jpg
 
            # Save the image of the page in system
            page.save(filename, "JPEG")
            image_file_list.append(filename)
 
        """
        Part #2 - Recognizing text from the images using OCR
        """
        if(not os.path.isdir(os.path.join(base_path,output_path))):
            os.makedirs(os.path.join(base_path,output_path))
        with open(text_file, "a+") as output_file:
            # Open the file in append mode so that
            # All contents of all images are added to the same file
 
            # Iterate from 1 to total number of pages
            for image_file in image_file_list:
 
                # Set filename to recognize text from
                # Again, these files will be:
                # page_1.jpg
                # page_2.jpg
                # ....
                # page_n.jpg
 
                # Recognize the text as string in image using pytesserct
                text = str(((pytesseract.image_to_string(Image.open(image_file)))))
 
                # The recognized text is stored in variable text
                # Any string processing may be applied on text
                # Here, basic formatting has been done:
                # In many PDFs, at line ending, if a word can't
                # be written fully, a 'hyphen' is added.
                # The rest of the word is written in the next line
                # Eg: This is a sample text this word here GeeksF-
                # orGeeks is half on first line, remaining on next.
                # To remove this, we replace every '-\n' to ''.
                text = text.replace("-\n", "")
 
                # Finally, write the processed text to the file.
                output_file.write(text)
 
            # At the end of the with .. output_file block
            # the file is closed after writing all the text.
        # At the end of the with .. tempdir block, the
        # TemporaryDirectory() we're using gets removed!       
    # End of main function!




def read_pdf(pdf_path):
    my_dict = {}
   
    with open(pdf_path,"rb") as file:
        file_name = os.path.splitext(os.path.basename(pdf_path))[0]
        if(not os.path.isdir(os.path.join(base_path,output_path))):
            os.makedirs(os.path.join(base_path,output_path))
        with open(os.path.join(base_path,output_path, file_name +'.txt'),"w+", encoding='utf-8') as output:
            pdf = PyPDF2.PdfReader(file)
            for page in range(len(pdf.pages)):
                page_obj = pdf.pages[page] # Extract the page
                text = page_obj.extract_text() # Extract text from page
                # my_dict[pdf_file] = text
                output.write(text)



  

      # image = page_obj.asImage()  # Create an image from page
      # # Save image to a file
      # image.save('page{}.jpg'.format(page))

