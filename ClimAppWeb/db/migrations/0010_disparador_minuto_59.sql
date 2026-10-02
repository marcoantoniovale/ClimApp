-- La ingesta se dispara al minuto 59 de cada hora (pedido del usuario, 2026-10-01): p. ej. 21:59.
-- cron.schedule con un nombre existente reemplaza la programación de esa tarea.
select cron.schedule('climapp-ingesta', '59 * * * *', 'select ops.disparar_ingesta()');
