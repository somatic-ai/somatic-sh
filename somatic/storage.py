"""Qdrant vector storage operations"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from loguru import logger


class Storage:
    """Handles Qdrant storage operations"""
    
    def __init__(self, qdrant_path: str, collection_name: str, vector_size: int = 1536):
        """Initialize Qdrant client in embedded mode"""
        self.qdrant_path = Path(qdrant_path)
        self.qdrant_path.mkdir(exist_ok=True, parents=True)
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        logger.info(f"Initializing Qdrant at {self.qdrant_path}")
        self.client = QdrantClient(path=str(self.qdrant_path))
        
        # Create collection if it doesn't exist
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the collection exists"""
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists")
        except Exception:
            logger.info(f"Creating collection '{self.collection_name}'")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Collection '{self.collection_name}' created")
    
    def upsert(self, points: List[PointStruct]):
        """Upsert points into Qdrant"""
        if not points:
            return
        
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.debug(f"Upserted {len(points)} points")
        except Exception as e:
            logger.error(f"Failed to upsert points: {e}")
            raise
    
    def search(self, query_vector: List[float], limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Search for similar vectors"""
        import math
        
        try:
            # For local/embedded mode, Qdrant doesn't have search() method
            # Use scroll() to get all points and calculate cosine similarity manually
            scroll_filter = None
            if filter_dict:
                conditions = []
                for key, value in filter_dict.items():
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                scroll_filter = Filter(must=conditions)
            
            # Get all points with vectors
            all_points = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,  # Large limit to get all points
                with_vectors=True,
                with_payload=True,
                scroll_filter=scroll_filter
            )[0]
            
            # Calculate cosine similarity manually
            def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
                """Calculate cosine similarity between two vectors"""
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                magnitude1 = math.sqrt(sum(a * a for a in vec1))
                magnitude2 = math.sqrt(sum(a * a for a in vec2))
                return dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0.0
            
            # Score all points
            scored_points = []
            for point in all_points:
                if point.vector:
                    score = cosine_similarity(query_vector, point.vector)
                    # Create a result-like object with score attribute
                    class ScoredPoint:
                        def __init__(self, point, score):
                            self.id = point.id
                            self.score = score
                            self.payload = point.payload if hasattr(point, 'payload') else {}
                            self.vector = point.vector if hasattr(point, 'vector') else None
                    
                    scored_points.append(ScoredPoint(point, score))
            
            # Sort by score (highest first) and return top N
            scored_points.sort(key=lambda x: x.score, reverse=True)
            return scored_points[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise
    
    def delete_by_ids(self, ids: List[int]):
        """Delete points by IDs"""
        if not ids:
            return
        
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=ids
            )
            logger.info(f"Deleted {len(ids)} points")
        except Exception as e:
            logger.error(f"Failed to delete points: {e}")
            raise
