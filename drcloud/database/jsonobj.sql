BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;
SET LOCAL search_path TO drcloud, public;


CREATE DOMAIN jsonobj AS jsonb NOT NULL DEFAULT '{}'
 CHECK (octet_length(VALUE::text) <= 2^16 AND jsonb_typeof(VALUE) = 'object');
COMMENT ON DOMAIN jsonobj IS 'A JSON document, up to 64KB in size.';


END;
