import fitz
from docx import Document
import os



def extract_resume_text(file):

    text = ""

    extension = os.path.splitext(
        file.name
    )[1].lower()



    # =========================
    # PDF FILE
    # =========================

    if extension == ".pdf":


        pdf = fitz.open(
            file.path
        )


        for page in pdf:

            text += page.get_text()



    # =========================
    # DOCX FILE
    # =========================

    elif extension == ".docx":


        document = Document(
            file.path
        )


        for paragraph in document.paragraphs:

            text += paragraph.text + "\n"




    # =========================
    # DOC FILE
    # =========================

    elif extension == ".doc":


        text = extract_doc_file(
            file.path
        )



    else:

        raise Exception(
            "Unsupported resume format"
        )



    return text




def extract_doc_file(path):

    import subprocess


    result = subprocess.run(

        [
            "antiword",
            path
        ],

        capture_output=True,

        text=True

    )


    return result.stdout