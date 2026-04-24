import asyncio
import logging
import os
from datetime import datetime, timezone

from src.db.session import get_session, make_engine, make_session_factory
from src.repositories.paper import PaperRepository
from src.services.chunker import TextChunker
from src.services.jina.client import JinaClient
from src.services.pdf_parser.parser import PDFProcessor
from src.services.qdrant.client import QdrantService

logger = logging.getLogger(__name__)

# Max papers to process per daily run — keeps each run bounded even if backlog grows.
PDF_BATCH_SIZE = 50


def process_and_index_papers() -> dict:
    """Download PDFs for unprocessed papers, parse with docling, chunk, and index into Qdrant.

    Processes up to PDF_BATCH_SIZE papers per run. Papers that fail PDF processing
    remain pdf_processed=False and are retried on the next daily run.
    """
    engine = make_engine(os.environ["DATABASE_URL"])
    session_factory = make_session_factory(engine)
    qdrant = QdrantService(url=os.environ["QDRANT_URL"])
    qdrant.setup_collection()

    processor = PDFProcessor()
    chunker = TextChunker()
    jina = JinaClient(api_key=os.environ["JINA_API_KEY"])

    processed = 0
    failed = 0

    with get_session(session_factory) as session:
        repo = PaperRepository(session)
        papers = repo.get_unprocessed(limit=PDF_BATCH_SIZE)

        logger.info(f"Processing {len(papers)} unprocessed papers")

        for paper in papers:
            pdf_content = processor.process(paper.arxiv_id, paper.pdf_url)

            if pdf_content is None:
                # process() already logged the error; leave pdf_processed=False for retry
                failed += 1
                continue

            # Persist extracted text to Postgres
            paper.raw_text = pdf_content.raw_text
            paper.sections = [{"title": s.title, "content": s.content} for s in pdf_content.sections]
            paper.parser_used = "docling"
            paper.parser_metadata = pdf_content.parser_metadata
            paper.pdf_processed = True
            paper.pdf_processing_date = datetime.now(timezone.utc)
            repo.update(paper)

            # Chunk and index into Qdrant with BM25 + dense embeddings
            chunks = chunker.chunk_paper(
                title=paper.title,
                abstract=paper.abstract,
                arxiv_id=paper.arxiv_id,
                paper_id=str(paper.id),
                sections=pdf_content.sections,
                raw_text=pdf_content.raw_text,
            )

            if chunks:
                chunk_texts = [c.text for c in chunks]
                dense_embeddings = asyncio.run(jina.embed_passages(chunk_texts))
                qdrant.index_chunks(chunks, dense_embeddings=dense_embeddings)

            processed += 1
            logger.info(f"Processed {paper.arxiv_id}: {len(chunks)} chunks indexed")

    logger.info(f"Batch complete — processed: {processed}, failed: {failed}")
    return {"processed": processed, "failed": failed}
