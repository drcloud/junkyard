BEGIN;

CREATE SCHEMA IF NOT EXISTS dns;
COMMENT ON SCHEMA dns IS 'Types for modeling DNS names.';
SET LOCAL search_path TO dns, public;

DO $$
BEGIN
  CREATE DOMAIN wildcard AS text NOT NULL DEFAULT '*'
   CHECK (VALUE ~ '(?x)
                   ^(
                      ( [*] | ([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?) )
                     ( [.]
                      ( [*] | ([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?) )
                     ){0,126}
                    )?
                   [.]?$' AND length(VALUE) <= 253);
EXCEPTION WHEN duplicate_object THEN
  RAISE LOG 'Already created domain wildcard.';
END
$$;
COMMENT ON DOMAIN wildcard IS
 'A domain mame pattern (valid LDH domain name or name with * components).';

DO $$
BEGIN
  CREATE DOMAIN ldh AS wildcard DEFAULT '.' CHECK (position('*' in VALUE) < 1);
EXCEPTION WHEN duplicate_object THEN
  RAISE LOG 'Already created domain ldh.';
END
$$;
COMMENT ON DOMAIN ldh IS
 'A valid LDH domain name. Syntax derived from RFCs 1035 and 1123.';

DO $$
BEGIN
  CREATE DOMAIN fqdn AS ldh;
EXCEPTION WHEN duplicate_object THEN
  RAISE LOG 'Already created domain fqdn.';
END
$$;
COMMENT ON DOMAIN fqdn IS
 'A fully qualified domain name. This type is backed by plain LDH but has '
 'different concatenation rules.';

DO $$
BEGIN
  CREATE DOMAIN component AS ldh DEFAULT '' CHECK (position('.' in VALUE) < 1);
EXCEPTION WHEN duplicate_object THEN
  RAISE LOG 'Already created domain component.';
END
$$;
COMMENT ON DOMAIN component IS 'A single domain component.';

CREATE OR REPLACE FUNCTION contains(shorter dns.ldh, longer dns.ldh)
RETURNS boolean AS $$
  SELECT right(longer, length(shorter) + 1) = '.'||shorter
$$ LANGUAGE sql IMMUTABLE STRICT;

CREATE OPERATOR >= (
  procedure = dns.contains,
  leftarg   = dns.ldh,
  rightarg  = dns.ldh
);

CREATE OR REPLACE FUNCTION concat(dns.wildcard, dns.wildcard)
RETURNS dns.wildcard AS $$
  SELECT (trim(trailing '.' FROM $1)::text||'.'||$2::text)::dns.wildcard
$$ LANGUAGE sql IMMUTABLE STRICT;

END;
