"""
Document repository: CRUD and vector search operations.
"""
from typing import List, Dict

from app.db.connection import get_db_connection
from app.core.config import DEFAULT_TOP_K
from app.core.errors import DatabaseError


class DocumentRepository:
    """Handle all document database operations."""

    @staticmethod
    def add(content: str, embedding: str, company: str = None, report_title: str = None, year: int = None) -> int:
        """Add a document with its embedding and metadata. Returns document ID."""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO documents (content, embedding, company, report_title, year) 
                   VALUES (%s, %s, %s, %s, %s) RETURNING id;""",
                (content, embedding, company, report_title, year)
            )
            doc_id = cur.fetchone()["id"]
            conn.commit()
            return doc_id
        except Exception as e:
            raise DatabaseError(f"Error adding document: {str(e)}")
        finally:
            if conn:
                cur.close()
                conn.close()

    @staticmethod
    def list_all() -> List[Dict]:
        """Retrieve all documents."""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, content, company, report_title, year, created_at FROM documents ORDER BY id;")
            documents = cur.fetchall()
            return documents
        except Exception as e:
            raise DatabaseError(f"Error listing documents: {str(e)}")
        finally:
            if conn:
                cur.close()
                conn.close()

    @staticmethod
    def search_by_similarity(query_embedding: str, top_k: int = DEFAULT_TOP_K, company: str = None) -> List[Dict]:
        """Retrieve documents most similar to the query embedding.
        
        Args:
            query_embedding: Vector embedding of the query.
            top_k: Number of documents to retrieve.
            company: Optional company filter (e.g., 'ABB', 'Roche').
        
        Returns: List of documents with similarity scores.
        """
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Build dynamic WHERE clause based on company filter
            where_clause = "WHERE embedding IS NOT NULL"
            params = [query_embedding, query_embedding]
            
            if company:
                where_clause += " AND company = %s"
                params.append(company)
            
            query = f"""
                SELECT id, content, company, report_title, year,
                       1 - (embedding <=> %s::vector) as similarity
                FROM documents
                {where_clause}
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            params.append(top_k)
            
            cur.execute(query, params)
            results = cur.fetchall()
            return results
        except Exception as e:
            raise DatabaseError(f"Error searching documents: {str(e)}")
        finally:
            if conn:
                cur.close()
                conn.close()
