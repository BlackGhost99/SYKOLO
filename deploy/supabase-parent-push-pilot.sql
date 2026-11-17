-- Supabase-only infrastructure migration; run after endpoint is deployed.
-- No credential shared via source, SQL text or dashboard.
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

CREATE SCHEMA IF NOT EXISTS yem_push_private;
REVOKE ALL ON SCHEMA yem_push_private FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS yem_push_private.dispatch_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    ticket_digest text,
    ticket_expires timestamptz,
    running_until timestamptz NOT NULL DEFAULT '-infinity',
    last_request_id bigint
);
ALTER TABLE yem_push_private.dispatch_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE yem_push_private.dispatch_state FROM PUBLIC, anon, authenticated;
INSERT INTO yem_push_private.dispatch_state(singleton) VALUES (true) ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION yem_push_private.schedule_dispatch(force_check boolean DEFAULT false)
RETURNS bigint LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $$
DECLARE
    ticket text;
    req bigint;
BEGIN
    -- No HTTP wake-up without an eligible device. No student data crosses HTTP.
    IF NOT EXISTS (
        SELECT 1 FROM public.institutions_parentpushdevice d
        JOIN public.accounts_user u ON u.id = d.parent_id
        WHERE d.valid_until > now() AND u.is_active AND NOT u.is_superuser
    ) THEN RETURN NULL; END IF;

    IF NOT force_check AND extract(minute FROM now()) <> 0 AND NOT EXISTS (
        SELECT 1 FROM public.institutions_parentpushdevice d
        JOIN public.accounts_user u ON u.id = d.parent_id
        JOIN public.institutions_schoolfamilynotification n ON n.parent_id = d.parent_id
        LEFT JOIN public.institutions_parentpushdelivery p ON p.device_id = d.id AND p.notice_id = n.id
        WHERE d.valid_until > now() AND u.is_active AND NOT u.is_superuser
          AND n.destination = 'parent' AND n.read_at IS NULL
          AND n.created_at >= greatest(d.registered_at, now() - interval '8 hours')
          AND (p.id IS NULL OR (p.state = 'pending' AND p.next_try <= now()))
    ) THEN RETURN NULL; END IF;

    ticket := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
    UPDATE yem_push_private.dispatch_state
       SET ticket_digest = encode(sha256(convert_to(ticket, 'UTF8')), 'hex'),
           ticket_expires = now() + interval '4 minutes'
     WHERE singleton AND running_until <= now()
       AND (ticket_expires IS NULL OR ticket_expires <= now());
    IF NOT FOUND THEN RETURN NULL; END IF;

    req := net.http_post(
        url := 'https://yem-api.onrender.com/internal/yem-parent-push',
        body := '{}'::jsonb,
        headers := jsonb_build_object('Content-Type', 'application/json', 'Authorization', 'Bearer ' || ticket),
        timeout_milliseconds := 120000
    );
    UPDATE yem_push_private.dispatch_state SET last_request_id = req WHERE singleton;
    RETURN req;
END $$;
REVOKE ALL ON FUNCTION yem_push_private.schedule_dispatch(boolean) FROM PUBLIC, anon, authenticated;

-- Do not expose the pg_net queue containing short-lived request headers.
REVOKE SELECT ON net.http_request_queue FROM PUBLIC, anon, authenticated;
REVOKE SELECT ON net._http_response FROM PUBLIC, anon, authenticated;

-- A real due durable message triggers work; an hourly scan covers computed
-- finance/admission events. The scheduler does not ping an idle no-device pilot.
SELECT cron.schedule('yem-parents-push-pilot', '*/5 * * * *',
    $$SELECT yem_push_private.schedule_dispatch(false)$$);
