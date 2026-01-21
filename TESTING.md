# Testing Guide for Somatic MVP

## Quick Test Steps

### 1. Start Postgres Database

```bash
docker-compose up -d
```

This starts Postgres with:
- Database: `somatic_test`
- User: `postgres`
- Password: `postgres`
- Port: `5432`
- Test table: `documents` with 3 sample rows

### 2. Verify Database is Running

```bash
docker-compose ps
```

You should see the postgres container running.

### 3. Create/Verify Configuration

If you haven't already, create `somatic.yml`:

```bash
poetry run somatic init
```

This creates a `somatic.yml` with the correct settings for the test database.

### 4. Test Proof-of-Concept (Optional but Recommended)

```bash
poetry run python poc.py
```

This validates the entire pipeline: Postgres → OpenAI → Qdrant → Query.

### 5. Sync All Existing Data

```bash
poetry run somatic sync
```

This will:
- Fetch all rows from the `documents` table
- Generate embeddings for each row
- Store them in Qdrant
- Create/update `.somatic/state.json` with the latest timestamp

You should see a progress bar and "Successfully synced 3 rows" (or however many rows exist).

### 6. Test Watch Command

In one terminal, start the watcher:

```bash
poetry run somatic watch
```

You should see:
```
Watching for changes (polling every 5s)...
Press Ctrl+C to stop

[dim]No changes detected[/dim]
```

### 7. Make Changes to Test Detection

**In another terminal**, connect to Postgres and make changes:

```bash
# Option A: Using psql (if installed)
psql -h localhost -U postgres -d somatic_test -c "INSERT INTO documents (title, content) VALUES ('New Test Document', 'This is a test to verify watch mode is working correctly.');"

# Option B: Using docker exec
docker-compose exec postgres psql -U postgres -d somatic_test -c "INSERT INTO documents (title, content) VALUES ('New Test Document', 'This is a test to verify watch mode is working correctly.');"

# Option C: Update an existing row
docker-compose exec postgres psql -U postgres -d somatic_test -c "UPDATE documents SET content = 'Updated content here' WHERE id = 1;"
```

### 8. Observe Watch Mode Detecting Changes

Within 5-10 seconds, you should see in the watch terminal:

```
Found 1 new/updated rows
✓ Processed 1 rows
[dim]No changes detected[/dim]
```

### 9. Test Search Query

In a third terminal (or stop watch with Ctrl+C), test search:

```bash
poetry run somatic query "machine learning"
```

You should see results with:
- Document IDs
- Similarity scores
- Title and content columns

### 10. Clean Up (Optional)

```bash
# Stop Postgres
docker-compose down

# Remove Qdrant data
rm -rf .qdrant

# Remove state
rm -rf .somatic
```

## Expected Behavior

### Sync Command
- ✅ Shows progress bar
- ✅ Processes all rows
- ✅ Creates embeddings for each row
- ✅ Stores in Qdrant
- ✅ Updates state file

### Watch Command
- ✅ Polls every 5 seconds (default)
- ✅ Detects new rows within 5-10 seconds
- ✅ Detects updated rows when `updated_at` changes
- ✅ Processes changes automatically
- ✅ Updates state file after each batch
- ✅ Continues watching until Ctrl+C

### Query Command
- ✅ Returns top 5 results by default
- ✅ Shows similarity scores
- ✅ Displays relevant columns from config
- ✅ Results are semantically similar to query

## Troubleshooting

### "OPENAI_API_KEY not found"
- Create a `.env` file with `OPENAI_API_KEY=your_key_here`

### "Failed to connect to Postgres"
- Ensure docker-compose is running: `docker-compose ps`
- Check connection settings in `somatic.yml`

### "No changes detected" but you know there are changes
- Check that `updated_at` column exists and is being updated
- Verify the trigger is working: `SELECT * FROM documents ORDER BY updated_at DESC;`
- Check state file: `cat .somatic/state.json`

### Watch mode not detecting changes
- Make sure you ran `somatic sync` first to establish baseline
- Verify the `updated_at` trigger is working
- Check database timezone matches application

## Test Scenarios

### Scenario 1: New Row Detection
1. Start watch mode
2. Insert a new row
3. Verify it's detected and embedded within 10 seconds

### Scenario 2: Updated Row Detection
1. Start watch mode  
2. Update an existing row's content
3. Verify the updated_at timestamp changes
4. Verify it's detected and re-embedded

### Scenario 3: Multiple Changes
1. Start watch mode
2. Insert 3-5 rows in quick succession
3. Verify all are detected and processed

### Scenario 4: Resume After Restart
1. Run sync to establish state
2. Insert some rows
3. Stop watch mode
4. Start watch mode again
5. Insert more rows
6. Verify only new rows are processed (not old ones)
