import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
import openai
import dicttoxml
import pandas as pd
import json
import re
import time
from dotenv import load_dotenv
import os
import logging

openai.api_key= os.getenv("OPENAI_API_KEY")
# If Tesseract is not in your PATH, specify the full path to the executable
# pytesseract.pytesseract.tesseract_cmd = r'/path/to/tesseract'

def get_pdf_files(folder_path):
    pdf_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith('.pdf')
    ]
    return pdf_files

def extract_text_directly(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        logging.error(f"Error extracting text directly from {pdf_path}: {e}")
    return text

def extract_text_with_ocr(pdf_path):
    text = ""

    try:
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image)  # Adjust language as needed
    except Exception as e:
        logging.error(f"Error extracting text with OCR from {pdf_path}: {e}")
    return text

def extract_text(pdf_path):
    text = extract_text_directly(pdf_path)
    if not text.strip():
        logging.info(f"No text extracted directly from {pdf_path}. Using OCR...")
        s=time.time()
        text = extract_text_with_ocr(pdf_path)
        print(time.time()-s)
    return text

def extract_information_with_gpt(text):
    prompt = f"""
Vous êtes un assistant qui extrait des informations à partir d'une facture. 
Veuillez extraire les informations suivantes et les fournir au format JSON:

- Type de document (facture, note de crédit, note de débit, autre)
- Date du document
- Nom et adresse du fournisseur
- Numéro de TVA du fournisseur (format belge ou étranger)
- Numéro de document
- Numéro de bon de commande
- Devise
- Taux de TVA (multiples)
- Montant total HTVA
- Montant total TVA
- Montant total TTC
- Communication structurée

Texte de la facture:
{text}
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            n=1,
            stop=None,
            temperature=0
        )
        content = response.choices[0].message.content
        # Extract JSON from the response
        json_text = re.search(r'\{.*\}', content, re.DOTALL)
        if json_text:
            data = json.loads(json_text.group())
        else:
            # If JSON is not found, attempt to parse the entire content
            data = json.loads(content)
    except Exception as e:
        logging.error(f"Error extracting information with GPT from text: {e}")
        data = {}
    return data

def generate_xml(data, output_path):
    xml = dicttoxml.dicttoxml(data, custom_root='Invoice', attr_type=False)
    with open(output_path, 'wb') as f:
        f.write(xml)

def generate_excel(all_data, output_path):
    df = pd.DataFrame(all_data)
    df.to_excel(output_path, index=False)

def process_invoices(folder_path, output_folder):
    pdf_files = get_pdf_files(folder_path)
    all_data = []

    for pdf_file in pdf_files[:20]:
        logging.info(f"Processing {pdf_file}...")
        text = extract_text(pdf_file)
        if not text.strip():
            logging.warning(f"Failed to extract text from {pdf_file}. Skipping.")
            continue
        data = extract_information_with_gpt(text)
        print(data)
        if not data:
            logging.warning(f"Failed to extract information from {pdf_file}. Skipping.")
            continue

        # Prepare output paths
        base_filename = os.path.splitext(os.path.basename(pdf_file))[0]
        xml_output_path = os.path.join(output_folder, f"{base_filename}.xml")

        # Save XML per invoice
        generate_xml(data, xml_output_path)
        logging.info(f"XML saved to {xml_output_path}")

        # Add filename to data for reference
        data['Fichier'] = base_filename
        all_data.append(data)

    if all_data:
        # Generate Excel summarizing all invoices
        excel_output_path = os.path.join(output_folder, 'invoices_summary.xlsx')
        generate_excel(all_data, excel_output_path)
        logging.info(f"Excel summary saved to {excel_output_path}")
    else:
        logging.warning("No data extracted from any invoices.")

# Processing a single invoice (used for /upload endpoint)
def process_invoice(pdf_file, output_folder):
    logging.info(f"Processing single file {pdf_file}...")
   
    text = extract_text(pdf_file)
    if not text.strip():
        logging.warning(f"Failed to extract text from {pdf_file}. Skipping.")
        return {"error": f"Failed to extract text from {pdf_file}"}

    data = extract_information_with_gpt(text)
    if not data:
        logging.warning(f"Failed to extract information from {pdf_file}. Skipping.")
        return {"error": f"Failed to extract information from {pdf_file}"}

    # Prepare output paths
    base_filename = os.path.splitext(os.path.basename(pdf_file))[0]
    xml_output_path = os.path.join(output_folder, f"{base_filename}.xml")
    excel_output_path = os.path.join(output_folder, 'invoices_summary.xlsx')

    # Save XML per invoice
    generate_xml(data, xml_output_path)
    logging.info(f"XML saved to {xml_output_path}")

    # Add filename to data for reference
    data['Fichier'] = base_filename

    # Generate Excel summary (just for this invoice)
    all_data = [data]
    generate_excel(all_data, excel_output_path)
    logging.info(f"Excel summary saved to {excel_output_path}")

    return {"message": "Processing successful", "data": data}