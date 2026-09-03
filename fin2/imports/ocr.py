"""Small boundary around the external Tesseract OCR process."""
import os,shutil,subprocess
from pathlib import Path

def executable():
    found=shutil.which('tesseract')
    fallback=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Tesseract-OCR'/'tesseract.exe'
    return found or (str(fallback) if os.name=='nt' and fallback.is_file() else None)

def available():return executable() is not None

def extract(body,language='por'):
    command=executable()
    if not command:raise ValueError('OCR indisponível: instale o Tesseract com o idioma português')
    arguments=[command,'stdin','stdout','-l',language,'--psm','6']
    local_data=Path(os.environ.get('LOCALAPPDATA',''))/'Fin2'/'tessdata'
    if os.name=='nt' and (local_data/f'{language}.traineddata').is_file():
        arguments.extend(['--tessdata-dir',str(local_data)])
    try:
        result=subprocess.run(arguments,input=body,
          capture_output=True,timeout=30,check=False)
    except subprocess.TimeoutExpired:raise ValueError('O OCR excedeu o limite de 30 segundos') from None
    if result.returncode:raise ValueError('O Tesseract não conseguiu ler o comprovante')
    return result.stdout.decode('utf-8','replace')
