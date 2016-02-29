BEGIN;

CREATE SCHEMA IF NOT EXISTS sm;

CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

SET LOCAL search_path TO sm, public;


CREATE DOMAIN hex4 AS text NOT NULL DEFAULT encode(gen_random_bytes(2), 'hex')
 CHECK (VALUE ~ '^[a-f0-9]{4}$');
COMMENT ON DOMAIN hex4 IS 'Four hexadecimal digits.';

CREATE DOMAIN status AS text NOT NULL DEFAULT '?'
 CHECK (VALUE ~ '^[?~!=+-]( [a-z][a-z0-9_]*)*$' AND length(VALUE) <= 18);
COMMENT ON DOMAIN status IS
 'Text representation of status. The descriptive word (optional) may be up to '
 '16 characters in length.';
--- ? -> unknown
--- ~ -> changing
--- ! -> error
--- = -> stable, available
--- + -> new, pending
--- - -> deleted, gone, defunct


CREATE TABLE sm (
  sm            uuid PRIMARY KEY NOT NULL DEFAULT uuid_generate_v4(),
  t             timestamptz NOT NULL DEFAULT now(),
  locked_till   timestamptz NOT NULL DEFAULT '-infinity'
);
COMMENT ON TABLE sm IS 'All state machines inherit from this table.';

CREATE INDEX "sm/t" ON sm (t);
CREATE INDEX "sm/locked_till" ON sm (was);

CREATE TABLE transition (
  transition    hex2,
  sm            uuid NOT NULL,
  end_t         timestamptz NOT NULL DEFAULT now(),   -- End time of transition
  duration      interval NOT NULL DEFAULT '0',
  was           status,
  "is"          status DEFAULT '+',
  PRIMARY KEY (sm, transition)
);
CREATE INDEX "transition/sm" ON transition (sm);
CREATE INDEX "transition/end_t" ON transition (end_t);
CREATE INDEX "transition/was" ON transition (was);
CREATE INDEX "transition/is" ON transition ("is");

END;
