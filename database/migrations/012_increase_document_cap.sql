-- Migration 012: Increase document cap to 100
-- Updates the BEFORE INSERT trigger to allow up to 100 documents per workspace.

CREATE OR REPLACE FUNCTION trg_teemo_documents_cap_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM teemo_documents
        WHERE workspace_id = NEW.workspace_id
    ) >= 100 THEN
        RAISE EXCEPTION 'Maximum 100 documents per workspace';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
