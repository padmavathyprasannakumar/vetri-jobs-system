import fitz
from docx import Document
import os
import io
import tempfile



def extract_resume_text(file):
    """
    file: a Django FieldFile (e.g. resume.file) - NOT a filesystem
    path. Using file.path breaks the moment the project uses a
    non-local storage backend (Cloudinary, S3, etc): those backends
    have no local path at all and file.path raises
    NotImplementedError. Reading the bytes through file.open()/
    .read() instead goes through Django's Storage API, which works
    identically whether the file lives on local disk or on
    Cloudinary.
    """

    text = ""

    extension = os.path.splitext(
        file.name
    )[1].lower()

    file.open("rb")

    try:

        data = file.read()

    finally:

        file.close()



    # =========================
    # PDF FILE
    # =========================

    if extension == ".pdf":


        pdf = fitz.open(
            stream=data,
            filetype="pdf",
        )


        for page in pdf:

            text += page.get_text()

        pdf.close()



    # =========================
    # DOCX FILE
    # =========================

    elif extension == ".docx":


        document = Document(
            io.BytesIO(data)
        )


        for paragraph in document.paragraphs:

            text += paragraph.text + "\n"




    # =========================
    # DOC FILE
    # =========================

    elif extension == ".doc":


        text = extract_doc_file(
            data
        )



    else:

        raise Exception(
            "Unsupported resume format"
        )



    return text




def extract_doc_file(data):
    """
    data: raw bytes of a legacy .doc file. antiword only accepts a
    real filesystem path, so the bytes are written to a short-lived
    local temp file first - this works regardless of where the
    original file actually lives (local disk or Cloudinary), since
    it's just a scratch copy for antiword to read.
    """

    import subprocess


    with tempfile.NamedTemporaryFile(suffix=".doc") as tmp:

        tmp.write(data)

        tmp.flush()

        result = subprocess.run(

            [
                "antiword",
                tmp.name
            ],

            capture_output=True,

            text=True

        )


    return result.stdout
