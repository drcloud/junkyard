BEGIN;

CREATE SCHEMA IF NOT EXISTS correlation_code;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

SET LOCAL search_path TO correlation_code, public;


CREATE TABLE client (
  client        text PRIMARY KEY NOT NULL,
  pid           integer,
  asof          timestamptz NOT NULL
);


INSERT INTO request VALUES ('a3bc1244/O1XNLH3', ...);
INSERT INTO request VALUES ('a3bc1244@O1XNLH3', ...);
INSERT INTO request VALUES ('a3bc1244O1XNLH3', ...);

