BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;

CREATE EXTENSION IF NOT EXISTS hstore SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

SET LOCAL search_path TO drcloud, public;


CREATE DOMAIN jsonobj AS jsonb NOT NULL DEFAULT '{}'
 CHECK (octet_length(VALUE::text) <= 2^16 AND jsonb_typeof(VALUE) = 'object');
COMMENT ON DOMAIN jsonobj IS 'A JSON document, up to 64KB in size.';


CREATE TABLE event (
  event         uuid PRIMARY KEY DEFAULT uuid_generate_v1(),
  t             timestamptz DEFAULT now(),
  by            text NOT NULL DEFAULT '' CHECK (octet_length(by) < 2^8),
  kind          text NOT NULL DEFAULT 'req'
                     CHECK (kind IN ('req', 'task', 'stat')),
  code          text NOT NULL CHECK (code ~ '^[?~!=+-]( [a-z][a-z0-9]*)+$'
                                     AND octet_length(code) <= 22),
                --- ? -> unknown
                --- ~ -> changing
                --- ! -> error, failure
                --- = -> stable, available, no change
                --- + -> okay, success
                --- - -> deleted, gone, defunct
  data          jsonobj
);
CREATE INDEX "event/t" ON event (t);
CREATE INDEX "event/by" ON event (by);
CREATE INDEX "event/by~" ON event (by text_pattern_ops);
CREATE INDEX "event/kind" ON event (kind);
CREATE INDEX "event/code" ON event (code);
CREATE INDEX "event/code~" ON event (code text_pattern_ops);
CREATE INDEX "event/data" ON event USING gin (data jsonb_path_ops);
COMMENT ON TABLE event IS 'Time series events.';

CREATE TABLE detail (
  event         uuid PRIMARY KEY REFERENCES event
                  ON DELETE CASCADE ON UPDATE CASCADE
                  DEFERRABLE INITIALLY DEFERRED,
  message       text NOT NULL DEFAULT '' CHECK (octet_length(message) <= 2^10),
  trace         text NOT NULL DEFAULT '' CHECK (octet_length(trace) <= 2^20)
);
CREATE INDEX "detail/message" ON detail (message);
CREATE INDEX "detail/message~" ON detail (message text_pattern_ops);
COMMENT ON TABLE detail IS
 'Detailed message and trace information for a time series event.';

CREATE TABLE led_to (
  event         uuid REFERENCES event
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  led_to        uuid REFERENCES event
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (event, led_to)
);
CREATE INDEX "led_to/event" ON led_to (event);
CREATE INDEX "led_to/led_to" ON led_to (led_to);
COMMENT ON TABLE led_to IS 'Relationship between events.';


--- These tables are all primary key -- they help us to keep track of identity
--- and can be easily joined with other tables.

CREATE TABLE cloud (
  cloud         dns.fqdn PRIMARY KEY
);

CREATE TABLE service (
  service       dns.fqdn PRIMARY KEY
);

CREATE TABLE route (
  entrypoint    dns.ldh,
  within        dns.fqdn,
  PRIMARY KEY (entrypoint, within)
);


CREATE TABLE "cloud*event" (
  cloud         dns.fqdn REFERENCES cloud
                         ON DELETE CASCADE ON UPDATE CASCADE
                         DEFERRABLE INITIALLY DEFERRED,
  event         uuid REFERENCES event
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (cloud, event)
);
COMMENT ON TABLE "cloud*event" IS 'Associate an event with a cloud.';

CREATE TABLE "service*event" (
  service       dns.fqdn REFERENCES service
                         ON DELETE CASCADE ON UPDATE CASCADE
                         DEFERRABLE INITIALLY DEFERRED,
  event         uuid REFERENCES event
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (service, event)
);
COMMENT ON TABLE "service*event" IS 'Associate an event with a service.';

CREATE TABLE "route*event" (
  entrypoint    dns.ldh,
  within        dns.fqdn,
  event         uuid REFERENCES event
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (entrypoint, within, event),
  FOREIGN KEY (entrypoint, within) REFERENCES route
                                   ON DELETE CASCADE ON UPDATE CASCADE
                                   DEFERRABLE INITIALLY DEFERRED
);
COMMENT ON TABLE "route*event" IS 'Associate an event with a route.';


--- We keep the binding between a name and its subnet forever, even if the
--- underlying service or route has been deleted.
CREATE TABLE net (
  fqdn          dns.fqdn PRIMARY KEY,
  net           cidr CHECK (family(net) = 6)                 -- TODO: Exclusion
);
CREATE INDEX "net/net" ON net (net);

--- The cloud table stores information about where we're deploying services.
--- All the services in a cloud must have names that are below the cloud's DNS
--- name, and the names of clouds must be unique.
CREATE TABLE cloud_conf (
  cloud         dns.fqdn PRIMARY KEY REFERENCES cloud
                                     ON DELETE CASCADE ON UPDATE CASCADE
                                     DEFERRABLE INITIALLY DEFERRED,
  provider      text NOT NULL CHECK (octet_length(provider) <= 2^10),
  tokens        jsonobj,
  options       jsonobj,
  FOREIGN KEY (cloud) REFERENCES net ON DELETE CASCADE ON UPDATE CASCADE
                                     DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX "cloud_conf/provider" ON cloud_conf (provider);

CREATE TABLE service_conf (
  service       dns.fqdn PRIMARY KEY REFERENCES service
                                     ON DELETE CASCADE ON UPDATE CASCADE
                                     DEFERRABLE INITIALLY DEFERRED,
  cloud         dns.fqdn REFERENCES cloud ON DELETE CASCADE ON UPDATE CASCADE
                                          DEFERRABLE INITIALLY DEFERRED,
  nodes         integer NOT NULL CHECK (nodes >= 0),
  profile       text NOT NULL,
  options       jsonobj,
  CHECK (dns.contains(cloud, service)),
  FOREIGN KEY (service) REFERENCES net ON DELETE CASCADE ON UPDATE CASCADE
                                       DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX "service_conf/cloud" ON service_conf (cloud);

CREATE TABLE route_upstream (
  entrypoint    dns.ldh,
  within        dns.fqdn,
  upstream      dns.fqdn,
  weight        numeric(5, 2) NOT NULL DEFAULT 1
                              CHECK (weight BETWEEN 100 AND 0.01),
  PRIMARY KEY (entrypoint, within, upstream),
  FOREIGN KEY (entrypoint, within) REFERENCES route
                                   ON DELETE CASCADE ON UPDATE CASCADE
                                   DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE route_conf (
  entrypoint    dns.ldh,
  within        dns.fqdn,
  program       text NOT NULL DEFAULT '' CHECK (octet_length(program) <= 2^16),
  options       jsonobj
);


CREATE FUNCTION net(cloud) RETURNS net AS $$
  SELECT * FROM net WHERE fqdn = $1.cloud;
$$ LANGUAGE sql STABLE STRICT SET search_path FROM CURRENT;
--- Cloud net ranges should allow for at least 2^64 nodes below them.
ALTER TABLE cloud ADD CHECK (masklen((net(cloud.*)).net) <= 64);

CREATE FUNCTION net(service) RETURNS net AS $$
  SELECT * FROM net WHERE fqdn = $1.service;
$$ LANGUAGE sql STABLE STRICT SET search_path FROM CURRENT;
--- Service net ranges should allow for at least 2^8 nodes below them.
ALTER TABLE service ADD CHECK (masklen((net(service.*)).net) <= 120);

--- Creates a random subnet.
CREATE FUNCTION subnet(base cidr, size integer DEFAULT 8) RETURNS cidr AS $$
DECLARE
  hex  text;
  txt  text := '';
  bits integer := 128 - (size + masklen(base));
BEGIN
  IF bits <= 0 OR NOT bits % 4 = 0 THEN
    RAISE EXCEPTION 'Need more than 0 bits in aligned 4 bit increments to '
                    'generate a subnet.';
  END IF;
  hex := encode(gen_random_bytes((bits + 4) / 8), 'hex');
  hex := substr(hex, 1, bits / 4);
  FOR b IN 1..128 LOOP
    IF b % 4 = 0 THEN
      IF b BETWEEN masklen(base) + 1 AND masklen(base) + bits THEN
        txt := txt || substr(hex, (b - masklen(base)) / 4, 1);
      ELSE
        txt := txt || '0';
      END IF;
    END IF;
    IF b > 1 AND (b - 1) % 16 = 0 THEN
      txt := txt || ':';
    END IF;
  END LOOP;
  txt := txt || '/' || (128 - size);
  RAISE INFO 'txt: %', txt;
  RETURN cidr(txt) | base;
END
$$ LANGUAGE plpgsql;

END;
