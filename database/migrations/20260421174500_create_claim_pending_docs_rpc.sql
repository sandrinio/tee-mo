-- Migration for EPIC-024: Native PostgreSQL Background Queue via RPC
-- Adds claim_pending_documents for atomic distributed locks using SKIP LOCKED

CREATE OR REPLACE FUNCTION claim_pending_documents(batch_size int default 20) 
RETURNS SETOF teemo_documents AS $$
BEGIN
  RETURN QUERY UPDATE teemo_documents
  SET sync_status = 'processing'
  WHERE id IN (
    SELECT id FROM teemo_documents 
    WHERE sync_status = 'pending' 
       OR (sync_status = 'error' AND updated_at < now() - interval '30 minutes')
       OR (sync_status = 'processing' AND updated_at < now() - interval '30 minutes')
    LIMIT batch_size 
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
END;
$$ LANGUAGE plpgsql;
