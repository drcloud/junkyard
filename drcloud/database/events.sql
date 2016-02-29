BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;
SET LOCAL search_path TO drcloud, public;


CREATE TABLE cloud_req (
  request       uuid PRIMARY KEY REFERENCES request
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  cloud         fqdn,
  provider      text NOT NULL CHECK (octet_length(provider) <= 2^10),
  tokens        jsonobj,
  options       jsonobj
);
CREATE INDEX "cloud_req/cloud" ON cloud_req (cloud);
CREATE TRIGGER request_notification AFTER INSERT ON cloud_req
   FOR EACH ROW EXECUTE PROCEDURE request_notification();

CREATE TABLE service_req (
  request       uuid PRIMARY KEY REFERENCES request
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  service       fqdn,
  cloud         fqdn,
  nodes         integer NOT NULL CHECK (nodes >= 0),
  profile       text NOT NULL,
  options       jsonobj,
  CHECK (dns_contains(cloud, service))
);
CREATE INDEX "service_req/service" ON service_req (service);
CREATE INDEX "service_req/cloud" ON service_req (cloud);
CREATE TRIGGER request_notification AFTER INSERT ON service_req
   FOR EACH ROW EXECUTE PROCEDURE request_notification();

CREATE TABLE route_req (
  request       uuid PRIMARY KEY REFERENCES request
                     ON DELETE CASCADE ON UPDATE CASCADE
                     DEFERRABLE INITIALLY DEFERRED,
  entrypoint    dns,
  within        fqdn,
  upstream      fqdn,
  mode          text NOT NULL CHECK (mode IN ('add', 'remove', 'drain'))
);
CREATE INDEX "route_req/entrypoint" ON route_req (entrypoint);
CREATE INDEX "route_req/within" ON route_req (within);
CREATE INDEX "route_req/upstream" ON route_req (upstream);
CREATE INDEX "route_req/mode" ON route_req (mode);
CREATE TRIGGER request_notification AFTER INSERT ON route_req
   FOR EACH ROW EXECUTE PROCEDURE request_notification();


END;
