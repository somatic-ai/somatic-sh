"""Postgres database watcher and data fetching"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from loguru import logger

from .models import SomaticConfig, WatcherState


class DatabaseWatcher:
    """Watches Postgres database for changes"""
    
    def __init__(self, config: SomaticConfig):
        """Initialize database connection"""
        self.config = config
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        source = self.config.source
        try:
            self.conn = psycopg2.connect(
                host=source.host,
                port=source.port,
                database=source.database,
                user=source.user,
                password=source.password
            )
            logger.info(f"Connected to Postgres at {source.host}:{source.port}/{source.database}")
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")
    
    def fetch_all_rows(self) -> List[Dict[str, Any]]:
        """Fetch all rows from the watched table"""
        watch = self.config.watch
        columns_str = ", ".join([watch.primary_key] + watch.columns + [watch.updated_at_column])
        
        query = f"SELECT {columns_str} FROM {watch.table} ORDER BY {watch.primary_key}"
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
                logger.info(f"Fetched {len(rows)} rows from {watch.table}")
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch rows: {e}")
            raise
    
    def fetch_new_rows(self, last_timestamp: Optional[str] = None, last_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch rows that have been updated since last_timestamp"""
        watch = self.config.watch
        columns_str = ", ".join([watch.primary_key] + watch.columns + [watch.updated_at_column])
        
        if last_timestamp:
            query = f"""
                SELECT {columns_str}
                FROM {watch.table}
                WHERE {watch.updated_at_column} > %s
                ORDER BY {watch.updated_at_column}
            """
            params = (last_timestamp,)
        else:
            # If no timestamp, fetch all (initial sync case)
            query = f"SELECT {columns_str} FROM {watch.table} ORDER BY {watch.updated_at_column}"
            params = None
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                rows = cur.fetchall()
                logger.debug(f"Fetched {len(rows)} new rows from {watch.table}")
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch new rows: {e}")
            raise
    
    def format_row_for_embedding(self, row: Dict[str, Any]) -> str:
        """Format a row into text for embedding"""
        watch = self.config.watch
        embeddings = self.config.embeddings
        
        # Extract column values
        column_values = []
        for col in watch.columns:
            value = row.get(col, "")
            if value:
                column_values.append(str(value))
        
        # Combine columns
        combined = "\n".join(column_values)
        
        # Apply template if provided
        if embeddings.template and "{columns}" in embeddings.template:
            return embeddings.template.format(columns=combined)
        else:
            return combined
