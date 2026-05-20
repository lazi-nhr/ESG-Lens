#!/usr/bin/env python3
"""
Database statistics and content summary script.
Provides extensive information about indexed documents, companies, and embeddings.
"""
import sys
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import get_db_connection
from app.core.errors import DatabaseError

# Colors for output
BOLD = '\033[1m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


def print_header(text):
    """Print a formatted section header."""
    print(f"\n{BOLD}{CYAN}{'='*80}{NC}")
    print(f"{BOLD}{CYAN}{text:^80}{NC}")
    print(f"{BOLD}{CYAN}{'='*80}{NC}\n")


def print_subheader(text):
    """Print a formatted subsection header."""
    print(f"{BOLD}{BLUE}{text}{NC}")
    print(f"{BLUE}{'-'*80}{NC}")


def get_database_stats():
    """Get comprehensive database statistics."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print_header("DATABASE CONTENT SUMMARY")
        print(f"{YELLOW}Generated:{NC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # === OVERALL STATISTICS ===
        print_subheader("📊 OVERALL STATISTICS")
        
        cur.execute("SELECT COUNT(*) as total FROM documents;")
        total_docs = cur.fetchone()['total']
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT company) as companies,
                COUNT(DISTINCT year) as years,
                COUNT(DISTINCT report_title) as report_types
            FROM documents;
        """)
        counts = cur.fetchone()
        
        stats_data = [
            ["Total Document Chunks", f"{total_docs:,}"],
            ["Unique Companies", f"{counts['companies']}"],
            ["Years Represented", f"{counts['years']}"],
            ["Report Types", f"{counts['report_types']}"],
        ]
        print(tabulate(stats_data, tablefmt="simple", disable_numparse=True))
        
        # === COMPANY BREAKDOWN ===
        print_subheader("🏢 DOCUMENTS BY COMPANY")
        
        cur.execute("""
            SELECT 
                company,
                COUNT(*) as chunks,
                COUNT(DISTINCT year) as years,
                MIN(year) as first_year,
                MAX(year) as last_year,
                COUNT(DISTINCT report_title) as report_types
            FROM documents
            WHERE company IS NOT NULL
            GROUP BY company
            ORDER BY COUNT(*) DESC;
        """)
        
        companies = cur.fetchall()
        if companies:
            company_data = []
            for c in companies:
                company_data.append([
                    c['company'],
                    f"{c['chunks']:,}",
                    c['years'],
                    c['first_year'],
                    c['last_year'],
                    c['report_types']
                ])
            
            headers = ["Company", "Chunks", "Years", "First Year", "Last Year", "Report Types"]
            print(tabulate(company_data, headers=headers, tablefmt="grid"))
            print(f"\n{GREEN}✓{NC} {len(companies)} companies indexed\n")
        else:
            print(f"{YELLOW}⚠ No companies found{NC}\n")
        
        # === YEAR DISTRIBUTION ===
        print_subheader("📅 DOCUMENTS BY YEAR")
        
        cur.execute("""
            SELECT 
                year,
                COUNT(*) as chunks,
                COUNT(DISTINCT company) as companies
            FROM documents
            WHERE year IS NOT NULL
            GROUP BY year
            ORDER BY year DESC;
        """)
        
        years = cur.fetchall()
        if years:
            year_data = []
            for y in years:
                year_data.append([
                    y['year'],
                    f"{y['chunks']:,}",
                    y['companies']
                ])
            
            headers = ["Year", "Chunks", "Companies"]
            print(tabulate(year_data, headers=headers, tablefmt="grid"))
            print()
        
        # === REPORT TYPE DISTRIBUTION ===
        print_subheader("📄 DOCUMENTS BY REPORT TYPE")
        
        cur.execute("""
            SELECT 
                report_title,
                COUNT(*) as chunks,
                COUNT(DISTINCT company) as companies
            FROM documents
            WHERE report_title IS NOT NULL
            GROUP BY report_title
            ORDER BY COUNT(*) DESC
            LIMIT 20;
        """)
        
        reports = cur.fetchall()
        if reports:
            report_data = []
            for r in reports:
                report_data.append([
                    r['report_title'],
                    f"{r['chunks']:,}",
                    r['companies']
                ])
            
            headers = ["Report Type", "Chunks", "Companies"]
            print(tabulate(report_data, headers=headers, tablefmt="grid"))
            print()
        
        # === COMPANY + YEAR MATRIX ===
        print_subheader("🗂️  DOCUMENT MATRIX (Company x Year)")
        
        cur.execute("""
            SELECT 
                company,
                year,
                COUNT(*) as chunks
            FROM documents
            WHERE company IS NOT NULL AND year IS NOT NULL
            GROUP BY company, year
            ORDER BY company, year DESC;
        """)
        
        matrix = cur.fetchall()
        if matrix:
            # Build a pivot-like display
            matrix_data = []
            current_company = None
            
            for m in matrix:
                if current_company != m['company']:
                    if current_company is not None:
                        matrix_data.append([''] * 3)  # Separator
                    current_company = m['company']
                
                matrix_data.append([
                    m['company'],
                    m['year'],
                    f"{m['chunks']:,}"
                ])
            
            headers = ["Company", "Year", "Chunks"]
            print(tabulate(matrix_data, headers=headers, tablefmt="simple"))
            print()
        
        # === EMBEDDING STATISTICS ===
        print_subheader("🔍 EMBEDDING STATISTICS")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_embeddings,
                COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
                COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embeddings
            FROM documents;
        """)
        
        emb_stats = cur.fetchone()
        embedding_data = [
            ["Documents with Embeddings", f"{emb_stats['with_embeddings']:,}"],
            ["Documents without Embeddings", f"{emb_stats['without_embeddings']:,}"],
            ["Total", f"{emb_stats['total_embeddings']:,}"],
        ]
        print(tabulate(embedding_data, tablefmt="simple", disable_numparse=True))
        
        embedding_pct = (emb_stats['with_embeddings'] / emb_stats['total_embeddings'] * 100) if emb_stats['total_embeddings'] > 0 else 0
        print(f"\n{GREEN}✓{NC} {embedding_pct:.1f}% of documents have embeddings\n")
        
        # === CONTENT STATISTICS ===
        print_subheader("📝 CONTENT STATISTICS")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_chunks,
                ROUND(AVG(LENGTH(content))::numeric, 0)::int as avg_length,
                MIN(LENGTH(content)) as min_length,
                MAX(LENGTH(content)) as max_length,
                ROUND(AVG(array_length(string_to_array(content, ' '), 1))::numeric, 0)::int as avg_words
            FROM documents
            WHERE content IS NOT NULL;
        """)
        
        content_stats = cur.fetchone()
        content_data = [
            ["Total Chunks", f"{content_stats['total_chunks']:,}"],
            ["Avg Chunk Length", f"{content_stats['avg_length']:,} chars"],
            ["Min Chunk Length", f"{content_stats['min_length']:,} chars"],
            ["Max Chunk Length", f"{content_stats['max_length']:,} chars"],
            ["Avg Words per Chunk", f"{content_stats['avg_words']:,}"],
        ]
        print(tabulate(content_data, tablefmt="simple", disable_numparse=True))
        print()
        
        # === TOP 10 LARGEST DOCUMENTS ===
        print_subheader("📊 TOP 10 LARGEST DOCUMENTS")
        
        cur.execute("""
            SELECT 
                company,
                report_title,
                year,
                LENGTH(content) as size_chars,
                array_length(string_to_array(content, ' '), 1) as word_count
            FROM documents
            WHERE content IS NOT NULL
            ORDER BY LENGTH(content) DESC
            LIMIT 10;
        """)
        
        largest = cur.fetchall()
        if largest:
            largest_data = []
            for l in largest:
                largest_data.append([
                    l['company'] or 'N/A',
                    l['report_title'] or 'N/A',
                    l['year'] or 'N/A',
                    f"{l['size_chars']:,}",
                    f"{l['word_count']:,}"
                ])
            
            headers = ["Company", "Report Type", "Year", "Size (chars)", "Words"]
            print(tabulate(largest_data, headers=headers, tablefmt="grid"))
            print()
        
        # === MISSING DATA ===
        print_subheader("⚠️  DATA QUALITY CHECK")
        
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN company IS NULL THEN 1 END) as missing_company,
                COUNT(CASE WHEN report_title IS NULL THEN 1 END) as missing_title,
                COUNT(CASE WHEN year IS NULL THEN 1 END) as missing_year,
                COUNT(CASE WHEN content IS NULL THEN 1 END) as missing_content,
                COUNT(CASE WHEN embedding IS NULL THEN 1 END) as missing_embedding
            FROM documents;
        """)
        
        quality = cur.fetchone()
        quality_data = [
            ["Missing Company", f"{quality['missing_company']:,}"],
            ["Missing Report Title", f"{quality['missing_title']:,}"],
            ["Missing Year", f"{quality['missing_year']:,}"],
            ["Missing Content", f"{quality['missing_content']:,}"],
            ["Missing Embedding", f"{quality['missing_embedding']:,}"],
        ]
        print(tabulate(quality_data, tablefmt="simple", disable_numparse=True))
        
        if quality['missing_company'] > 0 or quality['missing_title'] > 0 or quality['missing_year'] > 0:
            print(f"\n{YELLOW}⚠️  Some documents have missing metadata{NC}\n")
        else:
            print(f"\n{GREEN}✓ All documents have complete metadata{NC}\n")
        
        # === DATABASE CONNECTION INFO ===
        print_subheader("🔌 DATABASE CONNECTION")
        
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"PostgreSQL Version: {version[0].split(',')[0]}\n")
        
        # Close connection
        cur.close()
        conn.close()
        
        print_header("✅ REPORT COMPLETE")
        
    except Exception as e:
        print(f"\n{YELLOW}Error:{NC} {str(e)}\n")
        raise DatabaseError(str(e))


if __name__ == "__main__":
    try:
        get_database_stats()
    except Exception as e:
        print(f"\n{YELLOW}Failed to generate database summary:{NC}")
        print(f"{str(e)}\n")
        sys.exit(1)
