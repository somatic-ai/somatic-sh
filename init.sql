-- Create documents table for testing
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on updated_at for efficient querying
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at);

-- Insert some test data
INSERT INTO documents (title, content) VALUES
    ('Introduction to Python', 'Python is a high-level programming language known for its simplicity and readability.'),
    ('Machine Learning Basics', 'Machine learning is a subset of artificial intelligence that enables systems to learn from data.'),
    ('Database Management', 'Database management systems help organize and retrieve large amounts of data efficiently.')
ON CONFLICT DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
