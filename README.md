# Somatic MVP

A Python CLI tool that watches a Postgres database and automatically generates/updates embeddings when data changes.

## Features

- 🔄 **Automatic Sync**: Sync all data from a Postgres table and generate embeddings
- 👀 **Watch Mode**: Continuously poll for database changes and update embeddings in real-time
- 🔍 **Vector Search**: Query your data using natural language with semantic search
- 🚀 **Fast**: Batch processing with progress bars
- 💾 **Local Storage**: Uses Qdrant in embedded mode (no server required)

## Installation

### Prerequisites

- Python 3.11+
- Poetry for dependency management

### Setup

1. Clone the repository and install dependencies:

```bash
poetry install
```

2. Create a `.env` file with your OpenAI API key:

```bash
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=somatic_test
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

3. (Optional) Start a test Postgres instance with Docker:

```bash
docker-compose up -d
```

This will create a `documents` table with sample data.

## Quick Start

1. **Initialize configuration**:

```bash
poetry run somatic init
```

This creates a `somatic.yml` configuration file. Edit it with your database settings.

2. **Sync all data**:

```bash
poetry run somatic sync
```

This fetches all rows from the watched table, generates embeddings, and stores them in Qdrant.

3. **Watch for changes**:

```bash
poetry run somatic watch
```

This continuously polls the database for changes and automatically updates embeddings.

4. **Search**:

```bash
poetry run somatic query "machine learning"
```

This searches for similar content using semantic search.

## Configuration

The `somatic.yml` file defines:

- **source**: Postgres connection details
- **watch**: Table name, columns to embed, primary key, and timestamp column
- **embeddings**: Provider (OpenAI), model, and template for combining columns
- **storage**: Qdrant path and collection name

Example configuration:

```yaml
source:
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
```

## Proof of Concept

Before building the full CLI, you can test the entire flow with the proof-of-concept script:

```bash
poetry run python poc.py
```

This script:
1. Connects to Postgres
2. Fetches one row
3. Generates an embedding with OpenAI
4. Stores it in Qdrant
5. Queries it back to verify

## Commands

### `somatic init`

Creates a `somatic.yml` configuration template.

### `somatic sync`

Syncs all rows from the watched table and generates embeddings. Shows a progress bar and processes rows in batches.

### `somatic watch [--interval SECONDS]`

Continuously watches for database changes and automatically updates embeddings. Default polling interval is 5 seconds.

### `somatic query <search> [--limit N]`

Searches for similar content using semantic search. Returns top results with scores.

## Project Structure

```
somatic/
├── cli.py          # Click CLI commands
├── config.py       # Configuration loading
├── embedder.py     # Embedding generation with retry logic
├── models.py       # Pydantic models
├── storage.py      # Qdrant operations
└── watcher.py      # Postgres watching and data fetching
```

## Error Handling

- **Retry Logic**: OpenAI API calls are retried up to 3 times with exponential backoff
- **Connection Failures**: Graceful error messages for database and API connection failures
- **Failed Rows**: Failed rows are logged and skipped, allowing the process to continue

## Success Criteria

- ✅ Sync 1000 rows in under 2 minutes
- ✅ Watch mode detects changes within 10 seconds
- ✅ Query returns relevant results with semantic search

## Development

### Running the Proof of Concept

```bash
poetry run python poc.py
```

### Running Tests

The proof-of-concept script validates the entire pipeline. Ensure you have:

1. Postgres running (use `docker-compose up -d`)
2. `.env` file with `OPENAI_API_KEY`

## License

MIT
