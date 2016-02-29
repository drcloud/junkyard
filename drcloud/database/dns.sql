BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;
SET LOCAL search_path TO drcloud, public;


CREATE DOMAIN dns_glob AS text NOT NULL DEFAULT '*'
 CHECK (VALUE ~ '(?x)
                 ^(
                    ( [*] | ([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?) )
                   ( [.]
                    ( [*] | ([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?) )
                   ){0,126}
                  )?
                 [.]?$' AND length(VALUE) <= 253);
COMMENT ON DOMAIN dns_glob IS
 'A domain mame pattern (valid LDH domain name or name with * components).';

CREATE DOMAIN dns AS dns_glob DEFAULT '.' CHECK (position('*' in VALUE) < 1);
COMMENT ON DOMAIN dns IS
 'A valid LDH domain name. Syntax derived from RFCs 1035 and 1123.';

CREATE DOMAIN fqdn AS dns;
COMMENT ON DOMAIN fqdn IS
 'A fully qualified domain name. This type is backed by plain LDH but has '
 'different concatenation rules.';

CREATE DOMAIN component AS dns DEFAULT '' CHECK (position('.' in VALUE) < 1);
COMMENT ON DOMAIN component IS 'A single domain component.';

CREATE FUNCTION dns_contains(shorter dns, longer dns)
RETURNS boolean AS $$
  SELECT right(longer, length(shorter) + 1) = '.'||shorter
$$ LANGUAGE sql IMMUTABLE STRICT SET search_path FROM CURRENT;

CREATE FUNCTION dns_concat(dns_glob, dns_glob)
RETURNS dns_glob AS $$
  SELECT (trim(trailing '.' FROM $1)::text||'.'||$2::text)::dns_glob
$$ LANGUAGE sql IMMUTABLE STRICT SET search_path FROM CURRENT;


END;
