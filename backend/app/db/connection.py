"""
Database connection and initialization.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from app.core.errors import DatabaseError


def get_db_connection():
    """Create a new database connection."""
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        raise DatabaseError(f"Failed to connect to database: {str(e)}")


def init_db():
    """Initialize the database with pgvector extension and create tables."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Enable pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Create documents table with vector embeddings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(768),
                company VARCHAR(255),
                report_title VARCHAR(500),
                year INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add new columns if they don't exist (for existing databases)
        cur.execute("""
            ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS company VARCHAR(255),
            ADD COLUMN IF NOT EXISTS report_title VARCHAR(500),
            ADD COLUMN IF NOT EXISTS year INTEGER;
        """)

        # Create index for vector similarity search
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx 
            ON documents USING hnsw (embedding vector_cosine_ops);
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise DatabaseError(str(e))


async def health_check() -> dict:
    """Check database connection health."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        if conn:
            conn.close()
        raise DatabaseError(f"Database health check failed: {str(e)}")
