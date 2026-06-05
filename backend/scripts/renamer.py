#!/usr/bin/env python3
"""renamer.py

Convert the renamer notebook into a runnable script.

Usage:
  python renamer.py --root /path/to/rename --mode rename
  python renamer.py --root /path/to/rename --mode cleanup
  python renamer.py --root /path/to/rename --mode validate

The script attempts to load a local LLM for better title/year extraction but
falls back to filename-based heuristics when unavailable.
"""

import os
import re
import json
import argparse
from pathlib import Path

try:
    import torch
    from transformers import pipeline, GenerationConfig
except Exception:
    torch = None
    pipeline = None
    GenerationConfig = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


def unique_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    candidate = path
    i = 1
    while os.path.exists(candidate):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return candidate


def load_llm(model_id: str):
    if pipeline is None or torch is None:
        return None

    device = "cuda" if torch.cuda.is_available() else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    try:
        pipe = pipeline(
            "text-generation",
            model=model_id,
            device_map="auto" if device == "cpu" else device,
            model_kwargs={"torch_dtype": getattr(torch, "bfloat16", None) or getattr(torch, "float16", None)},
        )
        gen_config = GenerationConfig(max_new_tokens=100, temperature=0.1, do_sample=True)
        return (pipe, gen_config)
    except Exception as e:
        print(f"Warning: could not load model {model_id}: {e}")
        return None


def get_metadata_from_llm(pipe_gen, filename: str, content_snippet: str, company: str):
    pipe, gen_config = pipe_gen
    prompt = (
        "You are an expert file renamer. Extract the document title and year from the filename and content. "
        "Return ONLY a JSON object with keys \"title\" and \"year\". Example: {\"title\": \"Annual Report\", \"year\": \"2024\"}.\n"
        f"File: {filename}\nContent snippet: {content_snippet[:400]}"
    )
    try:
        out = pipe(prompt, generation_config=gen_config, return_full_text=False)
        text = out[0].get('generated_text') if isinstance(out, list) else str(out)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                print("LLM returned malformed JSON; falling back")
    except Exception as e:
        print(f"LLM extraction failed: {e}")

    # Fallback heuristics
    year_match = re.search(r"(20\d{2})", filename) or re.search(r"(20\d{2})", content_snippet)
    year = year_match.group(1) if year_match else "2024"
    # Title: filename without extension and company
    title = os.path.splitext(filename)[0]
    title = re.sub(re.escape(company), "", title, flags=re.I)
    title = title.replace("_", " ").replace("-", " ")
    title = " ".join(title.split()).strip()
    if not title:
        title = "Report"
    return {"title": title.title(), "year": year}


def process_folders(root_dir: str, pipe_gen=None):
    root = Path(root_dir)
    if not root.exists():
        print(f"Root folder does not exist: {root}")
        return

    for company in sorted(p.name for p in root.iterdir() if p.is_dir()):
        company_path = root / company
        for filename in sorted(os.listdir(company_path)):
            if not filename.lower().endswith('.pdf'):
                continue
            file_path = company_path / filename

            clean_filename = re.sub(f"(?i){re.escape(company)}", "", filename).replace("_", " ").replace("-", " ")

            snippet = ""
            if fitz is not None:
                try:
                    doc = fitz.open(str(file_path))
                    if len(doc) > 0:
                        snippet = doc[0].get_text()
                except Exception:
                    snippet = ""

            data = get_metadata_from_llm(pipe_gen, clean_filename, snippet, company) if pipe_gen else get_metadata_from_llm((None, None), clean_filename, snippet, company)

            title = data.get('title', 'Report')
            year = data.get('year', '2024')
            title = title.replace(company, "").strip(" _")
            clean_title = " ".join(title.split())
            new_name = f"{company}_{clean_title}_{year}.pdf"
            new_path = company_path / new_name
            if new_path.exists():
                new_path = Path(unique_path(str(new_path)))
                print(f"Target exists for {filename}. Using unique name: {new_path.name}")
            print(f"Renaming: {filename} -> {new_path.name}")
            try:
                os.rename(str(file_path), str(new_path))
            except Exception as e:
                print(f"Failed to rename {file_path}: {e}")


def cleanup_filenames(root_dir: str):
    for root, dirs, files in os.walk(root_dir):
        for filename in files:
            if not filename.lower().endswith('.pdf'):
                continue
            company = os.path.basename(root)
            old_path = os.path.join(root, filename)
            new_name = filename

            pattern_double_comp = rf"^{re.escape(company)}(?:_{re.escape(company)})+_"
            new_name = re.sub(pattern_double_comp, f"{company}_", new_name)

            year_match = re.match(r"^(.*?)([ _])(\d{4})_(\d{4})\.pdf$", new_name)
            if year_match and year_match.group(3) == year_match.group(4):
                new_name = f"{year_match.group(1)}_{year_match.group(3)}.pdf"

            if new_name != filename:
                new_path = os.path.join(root, new_name)
                if os.path.exists(new_path):
                    new_path = unique_path(new_path)
                    print(f"Target exists for {filename}. Using unique name: {os.path.basename(new_path)}")
                print(f"Cleaning: {filename} -> {os.path.basename(new_path)}")
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    print(f"Failed to rename {old_path} -> {new_path}: {e}")


def validate_and_summarize_filenames(root_dir: str):
    template_pattern = re.compile(r"^(.+?)_(.+?)_(\d{4})\.pdf$")

    total_files = 0
    valid_files = 0
    invalid_files = []
    company_counts = {}
    document_counts = {}

    company_year_docs = {}
    all_years = set()

    all_companies = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

    for root, dirs, files in os.walk(root_dir):
        company = os.path.basename(root)
        for filename in files:
            if not filename.lower().endswith('.pdf'):
                continue
            total_files += 1
            match = template_pattern.match(filename)
            if match:
                valid_files += 1
                parsed_company = match.group(1)
                document_title = match.group(2).strip()
                year = match.group(3)

                all_years.add(year)
                company_counts[parsed_company] = company_counts.get(parsed_company, 0) + 1
                document_key = f"{document_title} ({year})"
                document_counts[document_key] = document_counts.get(document_key, 0) + 1

                company_year_docs.setdefault(parsed_company, {}).setdefault(year, set()).add(document_title.lower())
            else:
                invalid_files.append((company, filename))

    print("Filename validation summary")
    print(f"Total PDF files: {total_files}")
    print(f"Files matching COMPANY_DOCUMENT_TITLE_YEAR: {valid_files}")
    print(f"Files not matching template: {len(invalid_files)}")

    if invalid_files:
        print("\nNon-matching files:")
        for company, filename in invalid_files:
            print(f"- {company}: {filename}")

    print("\nFiles by company:")
    for company in sorted(company_counts):
        print(f"- {company}: {company_counts[company]}")

    print("\nDocuments found:")
    for document_key in sorted(document_counts):
        print(f"- {document_key}: {document_counts[document_key]}")

    print("\nMissing documents by company and year (Annual Report / Sustainability Report):")
    years_sorted = sorted(all_years)
    if not years_sorted:
        print("No yeared documents found to check.")
        return

    for company in sorted(all_companies):
        missing_annual = []
        missing_sust = []
        for y in years_sorted:
            docs = company_year_docs.get(company, {}).get(y, set())
            has_annual = any("annual" in d for d in docs)
            has_sust = any("sustainab" in d or "esg" in d or "non-financial" in d for d in docs)
            if not has_annual:
                missing_annual.append(y)
            if not has_sust:
                missing_sust.append(y)

        if missing_annual or missing_sust:
            print(f"\n- {company}:")
            if missing_annual:
                print(f"  Missing Annual Report for years: {', '.join(missing_annual)}")
            else:
                print("  Has Annual Report for all years")
            if missing_sust:
                print(f"  Missing Sustainability Report for years: {', '.join(missing_sust)}")
            else:
                print("  Has Sustainability Report for all years")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', '-r', default=os.path.expanduser('~/Downloads/rename'), help='Root folder containing company subfolders')
    parser.add_argument('--mode', '-m', choices=['rename', 'cleanup', 'validate'], default='validate', help='Operation mode')
    parser.add_argument('--model', default='Qwen/Qwen2.5-1.5B-Instruct', help='Local model id to use for LLM extraction')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM usage and use heuristics only')
    args = parser.parse_args()

    pipe_gen = None
    if not args.no_llm:
        print('Attempting to load local LLM (may be slow)...')
        pipe_gen = load_llm(args.model)
        if pipe_gen is None:
            print('LLM not available; continuing with heuristics.')

    if args.mode == 'rename':
        process_folders(args.root, pipe_gen)
    elif args.mode == 'cleanup':
        cleanup_filenames(args.root)
    else:
        validate_and_summarize_filenames(args.root)


if __name__ == '__main__':
    main()
