"""Seed PostgreSQL database with PDFs from data folder."""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import init_db, get_db_connection
from app.db.repositories.documents_repo import DocumentRepository
from app.retrieval.embedder import create_embedding
from app.db.chunker import chunk_document

# Data folder path
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw_pdfs"


def seed_database():
    """Load all PDFs from data folder into database."""
    print("Initializing database...")
    init_db()
    print("✅ Database initialized\n")
    
    # Find all PDFs
    pdf_files = list(DATA_DIR.glob("**/*.pdf"))
    if not pdf_files:
        print(f"❌ No PDF files found in {DATA_DIR}")
        print(f"   Create folder: {DATA_DIR}")
        return
    
    print(f"Loading {len(pdf_files)} PDF(s) from {DATA_DIR}...\n")
    
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("❌ PyPDF2 not installed. Install with: pip install PyPDF2")
        return
    
    conn = get_db_connection()
    try:
        total_chunks = 0
        
        for pdf_path in pdf_files:
            print(f"  Processing {pdf_path.name}...")
            
            try:
                # Extract text from PDF
                reader = PdfReader(str(pdf_path))
                page_texts = [page.extract_text() for page in reader.pages]
                
                # Generate doc_id from filename
                doc_id = pdf_path.stem
                
                # Chunk the document using NLTK-based chunker
                chunks = chunk_document(
                    page_texts,
                    doc_id,
                    base_tokens=384,
                    overlap_tokens=64
                )
                
                # Insert chunks into database
                for chunk in chunks:
                    content = chunk.get("text", "")
                    if content.strip():
                        embedding = create_embedding(content)
                        doc_id_inserted = DocumentRepository.add(content, embedding)
                        total_chunks += 1
                
                print(f"    ✓ Loaded {len(reader.pages)} pages, {len(chunks)} chunks")
            except Exception as e:
                print(f"    ✗ Error: {e}")
                continue
        
        print(f"\n✅ Successfully indexed {total_chunks} chunks from {len(pdf_files)} PDF(s)")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()