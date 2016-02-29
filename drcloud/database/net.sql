BEGIN;

CREATE SCHEMA IF NOT EXISTS drcloud;
SET LOCAL search_path TO drcloud, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;


--- We keep the binding between a name and its subnet forever, even if the
--- underlying service or route has been deleted.
CREATE TABLE net (
  fqdn          fqdn PRIMARY KEY,
  net           cidr CHECK (family(net) = 6)                 -- TODO: Exclusion
);
CREATE INDEX "net/net" ON net (net);


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
