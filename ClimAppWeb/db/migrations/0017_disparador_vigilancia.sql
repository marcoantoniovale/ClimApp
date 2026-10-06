-- Disparador de la vigilancia (flujo vigilancia.yml: GET /api/health; si algo está atrasado la corrida
-- falla y GitHub avisa por correo). Igual que 0006 y 0015: Supabase pide a GitHub que ejecute el flujo con
-- el token del Vault ('github_actions_token'), porque el "schedule" de GitHub casi no dispara aquí.
-- Para detenerlo: select cron.unschedule('climapp-vigilancia');

create or replace function ops.disparar_vigilancia() returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
    token text;
begin
    select decrypted_secret into token from vault.decrypted_secrets where name = 'github_actions_token';
    if token is null then
        raise warning 'ops.disparar_vigilancia: falta el secreto github_actions_token en el Vault';
        return null;
    end if;
    return net.http_post(
        url := 'https://api.github.com/repos/marcoantoniovale/ClimApp/actions/workflows/vigilancia.yml/dispatches',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || token,
            'Accept', 'application/vnd.github+json',
            'X-GitHub-Api-Version', '2022-11-28',
            'User-Agent', 'climapp-supabase-cron'),
        body := jsonb_build_object('ref', 'main')
    );
end;
$$;

revoke execute on function ops.disparar_vigilancia() from public, anon, authenticated;

-- Minuto 37: lejos de la ingesta (59) y de las mediciones (14, 29, 44).
select cron.schedule('climapp-vigilancia', '37 * * * *', 'select ops.disparar_vigilancia()');
