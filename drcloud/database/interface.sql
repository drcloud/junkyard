--@ init ~
SET search_path TO drcloud, event, public;

--@ ready !
SELECT EXISTS (SELECT * FROM pg_namespace WHERE nspname = 'drcloud');

--@ listen ~
DO $$
DECLARE
  ident text;
BEGIN
  FOR ident IN SELECT unnest(%(ids)s::text[]) LOOP
    EXECUTE 'LISTEN '||quote_ident(ident);
  END LOOP;
END $$;

--@ refresh *
SELECT * FROM request
 WHERE by = COALESCE(%(user)s, session_user)
   AND t >= now() - '1 hour'::interval;

--@ sync !
WITH requests AS (INSERT INTO request (data)
                       SELECT unnest(%(requests)s) RETURNING *),
     events AS (SELECT *
                  FROM event NATURAL JOIN "request*event" NATURAL JOIN detail
                 WHERE event = ANY (%(ids)s) OR request = ANY (%(ids)s))
SELECT requests, events
  FROM LATERAL (SELECT json_agg(*) FROM requests) AS _(requests),
       LATERAL (SELECT json_agg(*) FROM events) AS __(events);

--@ server_time !
SELECT * FROM now();
