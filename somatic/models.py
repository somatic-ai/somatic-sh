"""Pydantic models for Somatic configuration and data structures"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PostgresSource(BaseModel):
    """Postgres database connection configuration"""
    host: str = Field(default="localhost", description="Postgres host")
    port: int = Field(default=5432, description="Postgres port")
    database: str = Field(description="Database name")
    user: str = Field(description="Database user")
    password: str = Field(description="Database password")


class WatchConfig(BaseModel):
    """Configuration for which table and columns to watch"""
    table: str = Field(description="Table name to watch")
    columns: List[str] = Field(description="Columns to embed")
    primary_key: str = Field(description="Primary key column name")
    updated_at_column: str = Field(default="updated_at", description="Timestamp column for tracking changes")


class EmbeddingsConfig(BaseModel):
    """Configuration for embedding generation"""
    provider: str = Field(default="openai", description="Embedding provider")
    model: str = Field(default="text-embedding-3-small", description="Model name")
    template: str = Field(
        default="{columns}",
        description="Template for combining columns. Use {columns} to insert joined columns."
    )


class StorageConfig(BaseModel):
    """Configuration for vector storage"""
    qdrant_path: str = Field(default=".qdrant", description="Local path for Qdrant")
    collection_name: str = Field(description="Qdrant collection name")


class SomaticConfig(BaseModel):
    """Main configuration model"""
    source: PostgresSource
    watch: WatchConfig
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    storage: StorageConfig

    @field_validator("embeddings")
    @classmethod
    def validate_embeddings(cls, v):
        """Ensure provider is openai (only one supported for now)"""
        if v.provider != "openai":
            raise ValueError("Only 'openai' provider is currently supported")
        return v


class WatcherState(BaseModel):
    """State tracking for the watcher"""
    last_sync_timestamp: Optional[str] = None
    last_sync_id: Optional[int] = None
