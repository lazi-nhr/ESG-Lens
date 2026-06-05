"""Seed PostgreSQL database with PDFs from data folder."""
import sys
import shutil
from pathlib import Path
import logging
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import init_db, get_db_connection
from app.db.repositories.documents_repo import DocumentRepository
from app.retrieval.embedder import create_embedding
from app.db.semantic_chunker import semantic_chunk_document
from app.core.config import SEMANTIC_SIMILARITY_THRESHOLD, MIN_CHUNK_TOKENS, MAX_CHUNK_TOKENS

# Setup logging - both console and file
log_file = Path(__file__).parent.parent.parent / "data" / "seed_db.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to: {log_file}")

# Data folder paths
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw_pdfs" / "new"
PROCESSED_DIR = DATA_DIR / "processed"


def ensure_processed_folder():
    """Create processed folder if it doesn't exist."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Processed folder ready: {PROCESSED_DIR}")


def move_to_processed(pdf_path: Path):
    """Move successfully processed PDF to processed folder."""
    try:
        destination = PROCESSED_DIR / pdf_path.name
        shutil.move(str(pdf_path), str(destination))
        logger.info(f"✓ Moved {pdf_path.name} to processed folder")
    except Exception as e:
        logger.error(f"Failed to move {pdf_path.name}: {e}")


def parse_filename(filename: str):
    """
    Parse PDF filename to extract company, report title, and year.
    Expected format: CompanyName_ReportType_Year.pdf
    
    Examples:
    - ABB_Sustainability Statement_2025.pdf → ('ABB', 'Sustainability Statement', 2025)
    - Adidas_Annual Report_2024.pdf → ('Adidas', 'Annual Report', 2024)
    - Bank of China_Sustainability Report_2025.pdf → ('Bank of China', 'Sustainability Report', 2025)
    """
    try:
        # Remove .pdf extension
        name_without_ext = filename.replace('.pdf', '')
        
        # Split by last underscore to extract year
        parts = name_without_ext.rsplit('_', 1)
        if len(parts) != 2:
            logger.warning(f"  ⚠ Could not parse filename: {filename}")
            return None, None, None
        
        left_part, year_str = parts
        
        # Try to convert year to integer
        try:
            year = int(year_str)
        except ValueError:
            logger.warning(f"  ⚠ Invalid year in filename {filename}: {year_str}")
            return None, None, None
        
        # Split company and report title by first underscore or space
        # Look for pattern: CompanyName_ReportType or CompanyName ReportType
        if '_' in left_part:
            company, report_title = left_part.split('_', 1)
        else:
            # Fallback: use the whole thing as company name
            company = left_part
            report_title = "Document"
        
        return company.strip(), report_title.strip(), year
        
    except Exception as e:
        logger.error(f"  ✗ Error parsing filename '{filename}': {e}")
        return None, None, None


def seed_database():
    """Load all PDFs from data folder into database."""
    logger.info("Initializing database...")
    init_db()
    logger.info("✅ Database initialized\n")
    
    # Ensure processed folder exists
    ensure_processed_folder()
    
    # Find all PDFs (excluding those in processed folder)
    pdf_files = [p for p in DATA_DIR.glob("**/*.pdf") if p.parent != PROCESSED_DIR]
    if not pdf_files:
        logger.warning(f"❌ No PDF files found in {DATA_DIR}")
        logger.info(f"   Create folder: {DATA_DIR}")
        return
    
    logger.info(f"Loading {len(pdf_files)} PDF(s) from {DATA_DIR}...\n")
    
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        logger.error("❌ PyPDF2 not installed. Install with: pip install PyPDF2")
        return
    
    conn = get_db_connection()
    successful = 0
    failed = 0
    
    try:
        total_chunks = 0
        
        # Progress bar for PDF processing
        pbar = tqdm(pdf_files, desc="Processing PDFs", unit="file", colour="green")
        
        for pdf_path in pbar:
            pbar.set_description(f"Processing: {pdf_path.name[:40]}")
            
            try:
                # Parse filename to extract metadata
                company, report_title, year = parse_filename(pdf_path.name)
                if company:
                    logger.debug(f"  Parsed: {company} | {report_title} | {year}")
                
                # Extract text from PDF
                reader = PdfReader(str(pdf_path))
                page_texts = [page.extract_text() for page in reader.pages]
                logger.debug(f"  Extracted {len(reader.pages)} pages")
                
                # Generate doc_id from filename
                doc_id = pdf_path.stem
                
                # Chunk the document using semantic chunking
                chunks = semantic_chunk_document(
                    page_texts,
                    doc_id,
                    embedding_fn=create_embedding,
                    similarity_threshold=SEMANTIC_SIMILARITY_THRESHOLD,
                    min_chunk_tokens=MIN_CHUNK_TOKENS,
                    max_chunk_tokens=MAX_CHUNK_TOKENS
                )
                logger.debug(f"  Created {len(chunks)} semantic chunks")
                
                # Insert chunks into database with progress bar
                chunks_inserted = 0
                chunk_pbar = tqdm(chunks, desc="  Embedding chunks", unit="chunk", leave=False, colour="blue")
                
                for chunk in chunk_pbar:
                    content = chunk.get("text", "")
                    if content.strip():
                        # Remove NUL bytes that can't be stored in PostgreSQL TEXT
                        content = content.replace("\x00", "")
                        if content.strip():  # Re-check after cleaning
                            embedding = create_embedding(content)
                            DocumentRepository.add(content, embedding, company, report_title, year)
                            chunks_inserted += 1
                            total_chunks += 1
                
                pbar.update()
                pbar.set_description(f"✓ {pdf_path.name[:40]}")
                logger.info(f"  ✓ Loaded {len(reader.pages)} pages, {chunks_inserted} chunks inserted")
                
                # Move to processed folder
                move_to_processed(pdf_path)
                successful += 1
                
            except Exception as e:
                logger.error(f"  ✗ Error processing {pdf_path.name}: {type(e).__name__}: {str(e)}", exc_info=True)
                failed += 1
                continue
        
        logger.info("\n✅ Seeding complete:")
        logger.info(f"   • Successful: {successful}")
        logger.info(f"   • Failed: {failed}")
        logger.info(f"   • Total chunks indexed: {total_chunks}")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()