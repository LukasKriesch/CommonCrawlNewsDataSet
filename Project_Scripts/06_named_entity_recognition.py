# -*- coding: utf-8 -*-
"""
Script for performing Named Entity Recognition (NER) on German news articles.

Updated for improved clarity, robustness, and configurability.
"""
import os
import logging
import pandas as pd
from glob import glob
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import spacy
import re
from argparse import ArgumentParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Pre-compiled regex for date extraction
date_pattern = re.compile(r"\d{8}")

def get_entities(filepath, nlp, out_folder):
    """Extract named entities from a file and save results."""
    try:
        # Load data and drop rows without text
        data = pd.read_feather(filepath).dropna(subset=["text"])

        # Rename column if needed
        if 'parsed_url' in data.columns and 'hostname' not in data.columns:
            data.rename(columns={"parsed_url": "hostname"}, inplace=True)

        # Extract date from file path
        match = date_pattern.search(filepath)
        if match:
            extracted_date = match.group(0)
            data["date_crawled"] = pd.to_datetime(extracted_date)

        ents_loc = []

        # Process each text and extract entities
        for text in tqdm(data["text"], desc=f"Processing {os.path.basename(filepath)}", leave=False):
            doc = nlp(text)
            ents_loc.append([ent.text for ent in doc.ents if ent.label_ == 'city_names'])

        # Add extracted entities to the DataFrame
        data["loc"] = ents_loc

        # Select relevant columns
        data = data[['date', 'url', 'id', 'excerpt', 'tags',
                     'categories', 'title', 'text', 'hostname', 'date_crawled', "loc"]]
        data.reset_index(drop=True, inplace=True)

        # Save the processed file
        out_filepath = os.path.join(out_folder, os.path.basename(filepath))
        data.to_feather(out_filepath)
        logging.info(f"Saved: {out_filepath}")

    except Exception as e:
        logging.error(f"Error processing file {filepath}: {e}")

def main(input_folder, output_folder, model_path):
    """Main function to perform NER on all files."""
    files = glob(os.path.join(input_folder, "*.feather"))
    parsed_files = {os.path.basename(f) for f in glob(os.path.join(output_folder, "*.feather"))}
    files_to_process = [f for f in files if os.path.basename(f) not in parsed_files]

    if not files_to_process:
        logging.info("No new files to process. Exiting.")
        return

    os.makedirs(output_folder, exist_ok=True)
    nlp = spacy.load(model_path)

    logging.info(f"Starting NER processing on {len(files_to_process)} files.")
    process_func = lambda filepath: get_entities(filepath, nlp, output_folder)

    # Use multiprocessing for efficient processing
    with Pool(processes=min(len(files_to_process), cpu_count())) as pool:
        for _ in tqdm(pool.imap_unordered(process_func, files_to_process), total=len(files_to_process), desc="Processing files"):
            pass

if __name__ == "__main__":
    parser = ArgumentParser(description="Perform Named Entity Recognition (NER) on news articles.")
    parser.add_argument("input_folder", type=str, help="Folder containing filtered feather files.")
    parser.add_argument("output_folder", type=str, help="Folder to save NER-processed files.")
    parser.add_argument("model_path", type=str, help="Path to the spaCy model.")
    args = parser.parse_args()

    main(args.input_folder, args.output_folder, args.model_path)
