BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;
SET LOCAL search_path TO drcloud, public;


CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;


CREATE TABLE request (
  request       uuid PRIMARY KEY DEFAULT uuid_generate_v1(),
  at            timestamptz DEFAULT now(),
  by            text NOT NULL DEFAULT session_user
                     CHECK (octet_length(by) < 2^8),
  locator       text NOT NULL DEFAULT ''
);
CREATE INDEX "request/at" ON request (t);
CREATE INDEX "request/by" ON request (by);
CREATE INDEX "request/by~" ON request (by text_pattern_ops);
CREATE INDEX "request/locator" ON request (locator);
CREATE INDEX "request/locator~" ON request (locator text_pattern_ops);
COMMENT ON TABLE request IS
 'Requests represent system input and can be associated with an application '
 'level booking code.';


CREATE TABLE status (
  status        uuid PRIMARY KEY DEFAULT uuid_generate_v1(),
  asof          timestamptz DEFAULT now(),
  poster        text NOT NULL DEFAULT session_user
                     CHECK (octet_length(by) < 2^8),
  code          text NOT NULL CHECK (code ~ '^[?~!=+-]( [a-z][a-z0-9]*)+$'
                                     AND octet_length(code) <= 22)
                --- ? -> unknown
                --- ~ -> changing
                --- ! -> error, failure
                --- = -> new, stable, available, no change
                --- + -> okay, success
                --- - -> deleted, gone, defunct
);
CREATE INDEX "status/asof" ON status (t);
CREATE INDEX "status/poster" ON status (poster);
CREATE INDEX "status/poster~" ON status (poster text_pattern_ops);
CREATE INDEX "status/code" ON status (code);
CREATE INDEX "status/code~" ON status (code text_pattern_ops);
COMMENT ON TABLE status IS
 'Status update events are reports from the system on observed state.';


CREATE TABLE detail (
  status        uuid PRIMARY KEY REFERENCES status
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  message       text NOT NULL DEFAULT '' CHECK (octet_length(message) <= 2^10),
  trace         text NOT NULL DEFAULT '' CHECK (octet_length(trace) <= 2^20),
  metadata      jsonobj
);
CREATE INDEX "detail/message" ON detail (message);
CREATE INDEX "detail/message~" ON detail (message text_pattern_ops);
COMMENT ON TABLE detail IS
 'Detailed message and trace information for a status event.';


CREATE TABLE "request*status" (
  request       uuid NOT NULL REFERENCES request
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  status        uuid NOT NULL REFERENCES status
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (request, status)
);
CREATE INDEX "request*status/request" ON "request*status" (request);
CREATE INDEX "request*status/status" ON "request*status" (status);
COMMENT ON TABLE "request*status" IS 'Associate requests with status events.';


--- Triggers & Listeners ------------------------------------------------------

CREATE FUNCTION request_notification() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('request', TG_TABLE_NAME||'/'||NEW.request);
  PERFORM pg_notify(TG_TABLE_NAME, ''||NEW.request);
END
$$ LANGUAGE plpgsql;

CREATE FUNCTION status_notification() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('status', TG_TABLE_NAME||'/'||NEW.status);
  PERFORM pg_notify(TG_TABLE_NAME, ''||NEW.status);
END
$$ LANGUAGE plpgsql;

CREATE FUNCTION request_status_notification() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('request*status', NEW.request||'/'||NEW.status);
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER request_status_notification AFTER INSERT ON "request*status"
   FOR EACH ROW EXECUTE PROCEDURE request_status_notification();
COMMENT ON TRIGGER request_status_notification ON "request*status" IS
 'Send a notification when a request has a status update.';


END;
