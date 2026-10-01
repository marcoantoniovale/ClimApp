-- Disparador confiable de la ingesta (opción A, autorizada por el usuario el 2026-10-01):
-- pg_cron (Supabase) pide a GitHub que ejecute el flujo "Ingesta" cada hora. El cron propio de
-- GitHub Actions se retrasa o salta corridas sin aviso (2026-10-01: ninguna corrida programada en
-- 2 h); queda como respaldo.
--
-- El token de GitHub (fine-grained, solo el repositorio ClimApp, permiso Actions: read and write)
-- lo guarda el usuario en el Vault de Supabase con el nombre 'github_actions_token'; no está en el
-- código. La función vive en el esquema "ops", que la API REST de Supabase no expone.

create extension if not exists pg_cron;
create extension if not exists pg_net;

create schema if not exists ops;
revoke all on schema ops from public, anon, authenticated;

create or replace function ops.disparar_ingesta() returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
    token text;
begin
    select decrypted_secret into token from vault.decrypted_secrets where name = 'github_actions_token';
    if token is null then
        raise warning 'ops.disparar_ingesta: falta el secreto github_actions_token en el Vault';
        return null;
    end if;
    return net.http_post(
        url := 'https://api.github.com/repos/marcoantoniovale/ClimApp/actions/workflows/ingesta.yml/dispatches',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || token,
            'Accept', 'application/vnd.github+json',
            'X-GitHub-Api-Version', '2022-11-28',
            'User-Agent', 'climapp-supabase-cron'),
        body := jsonb_build_object('ref', 'main', 'inputs', jsonb_build_object('comando', 'auto'))
    );
end;
$$;

revoke execute on function ops.disparar_ingesta() from public, anon, authenticated;

-- Minuto 5 de cada hora (el cron de GitHub usa el minuto 17; si ambos corren, el segundo no
-- descarga nada: "auto" solo trae corridas nuevas).
select cron.schedule('climapp-ingesta', '5 * * * *', 'select ops.disparar_ingesta()');
