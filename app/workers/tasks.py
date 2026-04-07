import os
import asyncio
from typing import List
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded, Retry
import pymupdf

# For ChromaDB and OpenAI
import chromadb
from openai import OpenAI
from app.core.config import settings
from app.services.document import update_document_status
from app.db import SessionLocal

# Initialize ChromaDB client (local persistent)
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Initialize Embedding Model. We will use OpenAI for embeddings.
# Requires OPENAI_API_KEY environment variable.
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Simple length-based chunking with overlap."""
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += (chunk_size - overlap)
        
    return chunks


async def _process_document_async(document_id: str, file_path: str, kb_id: str):
    """Async core logic for processing to allow DB interactions."""
    async with SessionLocal() as db:
        try:
            # 1. Update status to PROCESSING
            await update_document_status(db, document_id, "processing")
            
            # 2. Extract text
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            doc = pymupdf.open(file_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            
            # 3. Chunk text
            chunks = chunk_text(full_text)
            print(f"[{document_id}] Extracted {len(chunks)} chunks.")
            
            if chunks:
                # 4. Generate Embeddings
                embeddings = []
                batch_size = 500
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    response = openai_client.embeddings.create(
                        input=batch,
                        model="text-embedding-3-small"
                    )
                    embeddings.extend([data.embedding for data in response.data])
                
                # 5. Save to ChromaDB
                collection_name = f"kb_{kb_id.replace('-', '_')}"
                collection = chroma_client.get_or_create_collection(name=collection_name)
                
                ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
                metadatas = [{"document_id": document_id, "kb_id": kb_id} for _ in chunks]
                
                collection.upsert(
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
            
            # 6. Update status to COMPLETED
            await update_document_status(db, document_id, "completed")
            print(f"[{document_id}] Successfully processed.")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[{document_id}] Failed with error: {error_msg}")
            await update_document_status(db, document_id, "failed", error_msg=error_msg)
            raise


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id: str, file_path: str, kb_id: str):
    """Celery task to handle async document processing."""
    print(f"Job received for document: {document_id}")
    try:
        # We need to run the async db operations in a sync context
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(_process_document_async(document_id, file_path, kb_id))
        
    except (ConnectionError, TimeoutError) as e:
        # Retry for network-like errors
        raise self.retry(exc=e, countdown=5)
    except Exception as e:
        # Other exceptions are already caught and DB updated in the async function
        pass
