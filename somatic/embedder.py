"""Embedding generation with OpenAI and retry logic"""

import os
import time
from typing import List
from openai import OpenAI
from loguru import logger


class Embedder:
    """Handles embedding generation with retry logic"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """Initialize embedder with OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = 3
        self.base_delay = 1.0
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text
                )
                embedding = response.data[0].embedding
                logger.debug(f"Generated embedding (dimension: {len(embedding)})")
                return embedding
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to generate embedding after {self.max_retries} attempts: {e}")
                    raise
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        embeddings = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} texts)")
            
            batch_embeddings = []
            for text in batch:
                embedding = self.embed(text)
                batch_embeddings.append(embedding)
            
            embeddings.extend(batch_embeddings)
        
        return embeddings
