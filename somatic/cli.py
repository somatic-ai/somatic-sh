"""Main CLI interface for Somatic"""

import os
import json
import time
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from loguru import logger
from dotenv import load_dotenv

from .config import load_config
from .models import SomaticConfig, WatcherState
from .watcher import DatabaseWatcher
from .embedder import Embedder
from .storage import Storage
from qdrant_client.models import PointStruct

# Load environment variables
load_dotenv()

# Initialize rich console
console = Console()


def get_state_path() -> Path:
    """Get path to state file"""
    return Path(".somatic") / "state.json"


def load_state() -> WatcherState:
    """Load watcher state from file"""
    state_path = get_state_path()
    if state_path.exists():
        try:
            with open(state_path, 'r') as f:
                data = json.load(f)
            return WatcherState(**data)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return WatcherState()
    return WatcherState()


def save_state(state: WatcherState):
    """Save watcher state to file"""
    state_path = get_state_path()
    state_path.parent.mkdir(exist_ok=True, parents=True)
    with open(state_path, 'w') as f:
        json.dump(state.model_dump(), f, indent=2)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Somatic - Automatic embedding generation for Postgres databases"""
    # Configure loguru
    logger.remove()
    logger.add(
        lambda msg: console.print(msg, markup=False, highlight=False),
        format="<dim>{time:HH:mm:ss}</dim> <level>{level: <8}</level> {message}",
        level="INFO"
    )


@cli.command()
def init():
    """Create a somatic.yml configuration template"""
    config_path = Path("somatic.yml")
    
    if config_path.exists():
        if not click.confirm("somatic.yml already exists. Overwrite?"):
            return
    
    template = """source:
  host: localhost
  port: 5432
  database: somatic_test
  user: postgres
  password: postgres

watch:
  table: documents
  columns:
    - title
    - content
  primary_key: id
  updated_at_column: updated_at

embeddings:
  provider: openai
  model: text-embedding-3-small
  template: "{columns}"

storage:
  qdrant_path: .qdrant
  collection_name: documents
"""
    
    with open(config_path, 'w') as f:
        f.write(template)
    
    console.print(f"[green]✓[/green] Created {config_path}")
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  1. Edit somatic.yml with your database settings")
    console.print("  2. Create .env file with OPENAI_API_KEY")
    console.print("  3. Run 'somatic sync' to sync all data")


@cli.command()
@click.option("--config", "-c", help="Path to somatic.yml")
def sync(config: Optional[str]):
    """Sync all rows from the watched table and generate embeddings"""
    try:
        # Load configuration
        somatic_config = load_config(config)
        
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]ERROR:[/red] OPENAI_API_KEY not found in .env file")
            raise click.Abort()
        
        # Initialize components
        watcher = DatabaseWatcher(somatic_config)
        embedder = Embedder(api_key, somatic_config.embeddings.model)
        
        # Determine vector size (text-embedding-3-small is 1536)
        vector_size = 1536
        storage = Storage(
            somatic_config.storage.qdrant_path,
            somatic_config.storage.collection_name,
            vector_size
        )
        
        # Fetch all rows
        console.print("[cyan]Fetching all rows...[/cyan]")
        rows = watcher.fetch_all_rows()
        
        if not rows:
            console.print("[yellow]No rows found to sync[/yellow]")
            watcher.close()
            return
        
        console.print(f"[green]Found {len(rows)} rows to sync[/green]")
        
        # Process rows with progress bar
        failed_rows = []
        points = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Syncing rows...", total=len(rows))
            
            for row in rows:
                try:
                    # Format row for embedding
                    text_to_embed = watcher.format_row_for_embedding(row)
                    
                    # Generate embedding
                    embedding = embedder.embed(text_to_embed)
                    
                    # Create point
                    primary_key = row[somatic_config.watch.primary_key]
                    point = PointStruct(
                        id=primary_key,
                        vector=embedding,
                        payload={
                            "row_id": primary_key,
                            **{col: row.get(col) for col in somatic_config.watch.columns},
                            "timestamp": row.get(somatic_config.watch.updated_at_column)
                        }
                    )
                    points.append(point)
                    
                    # Batch upsert every 100 points
                    if len(points) >= 100:
                        storage.upsert(points)
                        points = []
                    
                except Exception as e:
                    logger.error(f"Failed to process row {row.get(somatic_config.watch.primary_key)}: {e}")
                    failed_rows.append(row)
                
                progress.update(task, advance=1)
            
            # Upsert remaining points
            if points:
                storage.upsert(points)
        
        watcher.close()
        
        if failed_rows:
            console.print(f"[yellow]Warning: {len(failed_rows)} rows failed to process[/yellow]")
        
        console.print(f"[green]✓[/green] Successfully synced {len(rows) - len(failed_rows)} rows")
        
        # Update state with latest timestamp
        if rows:
            latest_timestamp = rows[-1].get(somatic_config.watch.updated_at_column)
            if latest_timestamp:
                state = WatcherState(
                    last_sync_timestamp=str(latest_timestamp),
                    last_sync_id=rows[-1].get(somatic_config.watch.primary_key)
                )
                save_state(state)
        
    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")
        logger.exception("Sync failed")
        raise click.Abort()


@cli.command()
@click.option("--config", "-c", help="Path to somatic.yml")
@click.option("--interval", "-i", default=5, help="Polling interval in seconds")
def watch(config: Optional[str], interval: int):
    """Watch for database changes and automatically update embeddings"""
    try:
        # Load configuration
        somatic_config = load_config(config)
        
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]ERROR:[/red] OPENAI_API_KEY not found in .env file")
            raise click.Abort()
        
        # Initialize components
        watcher = DatabaseWatcher(somatic_config)
        embedder = Embedder(api_key, somatic_config.embeddings.model)
        
        vector_size = 1536
        storage = Storage(
            somatic_config.storage.qdrant_path,
            somatic_config.storage.collection_name,
            vector_size
        )
        
        console.print(f"[cyan]Watching for changes (polling every {interval}s)...[/cyan]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        
        try:
            while True:
                # Load current state
                state = load_state()
                
                # Fetch new rows
                new_rows = watcher.fetch_new_rows(state.last_sync_timestamp)
                
                if new_rows:
                    console.print(f"[green]Found {len(new_rows)} new/updated rows[/green]")
                    
                    points = []
                    for row in new_rows:
                        try:
                            # Format row for embedding
                            text_to_embed = watcher.format_row_for_embedding(row)
                            
                            # Generate embedding
                            embedding = embedder.embed(text_to_embed)
                            
                            # Create point
                            primary_key = row[somatic_config.watch.primary_key]
                            point = PointStruct(
                                id=primary_key,
                                vector=embedding,
                                payload={
                                    "row_id": primary_key,
                                    **{col: row.get(col) for col in somatic_config.watch.columns},
                                    "timestamp": row.get(somatic_config.watch.updated_at_column)
                                }
                            )
                            points.append(point)
                        except Exception as e:
                            logger.error(f"Failed to process row {row.get(somatic_config.watch.primary_key)}: {e}")
                    
                    # Upsert points
                    if points:
                        storage.upsert(points)
                        console.print(f"[green]✓[/green] Processed {len(points)} rows")
                        
                        # Update state with latest timestamp
                        latest_timestamp = new_rows[-1].get(somatic_config.watch.updated_at_column)
                        if latest_timestamp:
                            state.last_sync_timestamp = str(latest_timestamp)
                            state.last_sync_id = new_rows[-1].get(somatic_config.watch.primary_key)
                            save_state(state)
                else:
                    console.print("[dim]No changes detected[/dim]", end="\r")
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping watcher...[/yellow]")
        finally:
            watcher.close()
    
    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")
        logger.exception("Watch failed")
        raise click.Abort()


@cli.command()
@click.argument("search")
@click.option("--config", "-c", help="Path to somatic.yml")
@click.option("--limit", "-l", default=5, help="Number of results to return")
def query(search: str, config: Optional[str], limit: int):
    """Search for similar content using embeddings"""
    try:
        # Load configuration
        somatic_config = load_config(config)
        
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]ERROR:[/red] OPENAI_API_KEY not found in .env file")
            raise click.Abort()
        
        # Initialize components
        embedder = Embedder(api_key, somatic_config.embeddings.model)
        vector_size = 1536
        storage = Storage(
            somatic_config.storage.qdrant_path,
            somatic_config.storage.collection_name,
            vector_size
        )
        
        console.print(f"[cyan]Searching for:[/cyan] {search}")
        
        # Generate embedding for search query
        search_embedding = embedder.embed(search)
        
        # Search in Qdrant
        results = storage.search(search_embedding, limit=limit)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        # Display results in a table
        table = Table(title=f"Search Results (Top {len(results)})")
        table.add_column("ID", style="cyan")
        table.add_column("Score", style="green")
        
        # Add columns from watch config
        for col in somatic_config.watch.columns:
            table.add_column(col.title(), style="yellow")
        
        for result in results:
            row_data = [str(result.id), f"{result.score:.4f}"]
            payload = result.payload
            for col in somatic_config.watch.columns:
                value = payload.get(col, "N/A")
                # Truncate long values
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                row_data.append(str(value))
            table.add_row(*row_data)
        
        console.print()
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")
        logger.exception("Query failed")
        raise click.Abort()
