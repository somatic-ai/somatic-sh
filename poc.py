#!/usr/bin/env python3
"""
Proof-of-concept script to validate the entire embedding pipeline:
1. Connect to Postgres
2. Fetch one row
3. Embed it with OpenAI
4. Store in Qdrant
5. Query it back to verify
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Load environment variables
load_dotenv()

def main():
    print("🔬 Running Somatic Proof-of-Concept...")
    
    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in .env file")
        sys.exit(1)
    
    openai_client = OpenAI(api_key=api_key)
    
    # Connect to Postgres
    print("\n📊 Connecting to Postgres...")
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "somatic_test"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        print("✅ Connected to Postgres")
    except Exception as e:
        print(f"❌ ERROR: Failed to connect to Postgres: {e}")
        sys.exit(1)
    
    # Fetch one row
    print("\n📖 Fetching a row from documents table...")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM documents LIMIT 1")
            row = cur.fetchone()
            if not row:
                print("❌ ERROR: No rows found in documents table")
                sys.exit(1)
            
            doc_id = row['id']
            title = row.get('title', '')
            content = row.get('content', '')
            print(f"✅ Fetched row ID: {doc_id}")
            print(f"   Title: {title[:50]}...")
            print(f"   Content: {content[:50]}...")
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch row: {e}")
        sys.exit(1)
    finally:
        conn.close()
    
    # Combine columns for embedding
    text_to_embed = f"{title}\n{content}".strip()
    print(f"\n📝 Text to embed ({len(text_to_embed)} chars): {text_to_embed[:100]}...")
    
    # Generate embedding with OpenAI
    print("\n🤖 Generating embedding with OpenAI...")
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text_to_embed
        )
        embedding = response.data[0].embedding
        print(f"✅ Generated embedding (dimension: {len(embedding)})")
    except Exception as e:
        print(f"❌ ERROR: Failed to generate embedding: {e}")
        sys.exit(1)
    
    # Initialize Qdrant client (embedded mode)
    print("\n💾 Initializing Qdrant (embedded mode)...")
    qdrant_path = Path(".qdrant")
    qdrant_path.mkdir(exist_ok=True)
    
    try:
        client = QdrantClient(path=str(qdrant_path))
        collection_name = "documents"
        
        # Create collection if it doesn't exist
        try:
            client.get_collection(collection_name)
            print(f"✅ Collection '{collection_name}' already exists")
        except:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=len(embedding),
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created collection '{collection_name}'")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize Qdrant: {e}")
        sys.exit(1)
    
    # Store in Qdrant
    print("\n💾 Storing embedding in Qdrant...")
    try:
        point = PointStruct(
            id=doc_id,
            vector=embedding,
            payload={
                "row_id": doc_id,
                "title": title,
                "content": content,
                "timestamp": row.get('updated_at', row.get('created_at'))
            }
        )
        client.upsert(
            collection_name=collection_name,
            points=[point]
        )
        print(f"✅ Stored embedding for row ID {doc_id}")
    except Exception as e:
        print(f"❌ ERROR: Failed to store in Qdrant: {e}")
        sys.exit(1)
    
    # Query it back
    print("\n🔍 Querying back from Qdrant...")
    try:
        results = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="row_id",
                        match=MatchValue(value=doc_id)
                    )
                ]
            ),
            limit=1,
            with_vectors=True,
            with_payload=True
        )
        
        if results[0]:
            found_point = results[0][0]
            print(f"✅ Found point ID: {found_point.id}")
            print(f"   Title: {found_point.payload.get('title', 'N/A')}")
            print(f"   Has vector: {found_point.vector is not None and len(found_point.vector) > 0}")
        else:
            print("❌ ERROR: Point not found in Qdrant")
            sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: Failed to query Qdrant: {e}")
        sys.exit(1)
    
    # Test search query
    print("\n🔍 Testing search query...")
    try:
        search_query = title.split()[0] if title else "test"
        search_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=search_query
        )
        search_embedding = search_response.data[0].embedding
        
        # For local/embedded mode, Qdrant doesn't have a direct search() method
        # Use scroll to get all points and calculate cosine similarity manually
        all_points = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_vectors=True,
            with_payload=True
        )[0]
        
        # Calculate cosine similarity manually
        import math
        def cosine_similarity(vec1, vec2):
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))
            return dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0
        
        scored_points = []
        for point in all_points:
            if point.vector:
                score = cosine_similarity(search_embedding, point.vector)
                scored_points.append((score, point))
        
        scored_points.sort(key=lambda x: x[0], reverse=True)
        
        if scored_points:
            result_score, result = scored_points[0]
            result_id = result.id
            result_payload = result.payload if hasattr(result, 'payload') else {}
            
            print(f"✅ Search query '{search_query}' found:")
            print(f"   ID: {result_id}")
            print(f"   Score: {result_score:.4f}")
            print(f"   Title: {result_payload.get('title', 'N/A')}")
        else:
            print("❌ ERROR: No search results found")
            sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: Failed to perform search: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n🎉 Proof-of-concept completed successfully!")
    print("   All components working: Postgres → OpenAI → Qdrant → Query")

if __name__ == "__main__":
    main()
