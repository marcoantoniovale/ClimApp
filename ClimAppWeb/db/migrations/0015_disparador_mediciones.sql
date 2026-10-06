-- Disparador de las mediciones cada 15 min (flujo mediciones.yml: lluvia DMC → Redis + renovar la web).
-- El cron propio de GitHub casi no dispara en este repositorio (2026-10-04/06: la ingesta horaria se lanzó
-- por "schedule" solo 10 veces en 2 días, con hasta 40 min de atraso; las mediciones, ninguna vez en la
-- primera hora). Igual que la ingesta (0006), Supabase pide a GitHub que ejecute el flujo, con el mismo
-- token del Vault ('github_actions_token', permiso Actions: read and write sobre ClimApp).
--
-- El flujo sigue obedeciendo la variable del repositorio MEDICIONES_15MIN: si no vale "si", la corrida
-- queda omitida (sin consumo). Para detener el disparador: select cron.unschedule('climapp-mediciones');

create or replace function ops.disparar_mediciones() returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
    token text;
begin
    select decrypted_secret into token from vault.decrypted_secrets where name = 'github_actions_token';
    if token is null then
        raise warning 'ops.disparar_mediciones: falta el secreto github_actions_token en el Vault';
        return null;
    end if;
    return net.http_post(
        url := 'https://api.github.com/repos/marcoantoniovale/ClimApp/actions/workflows/mediciones.yml/dispatches',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || token,
            'Accept', 'application/vnd.github+json',
            'X-GitHub-Api-Version', '2022-11-28',
            'User-Agent', 'climapp-supabase-cron'),
        body := jsonb_build_object('ref', 'main')
    );
end;
$$;

revoke execute on function ops.disparar_mediciones() from public, anon, authenticated;

-- Minutos 14, 29 y 44 (la ingesta completa corre al 59). Chile tiene desfase entero con UTC.
select cron.schedule('climapp-mediciones', '14,29,44 * * * *', 'select ops.disparar_mediciones()');
