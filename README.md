# bioalimentar-dashboard (repo de la rutina diaria)

Este repositorio existe únicamente para que la rutina programada en la nube de Claude Code
pueda regenerar y republicar el dashboard "Leads x Asesor" sin depender de que la computadora
de Santiago esté encendida.

- `dashboard_template.html` — plantilla del dashboard (HTML + CSS + JS), con dos placeholders
  (`/*__LEADS_DATA__*/` y `/*__LOGO_B64__*/`) que `refresh.py` reemplaza con datos reales.
- `refresh.py` — descarga los datos de Bitrix24, los agrega y genera `dashboard.html` final.
- `data/logo.png` — logo oficial de Bioalimentar.

**No se sube** el token del webhook de Bitrix24 a este repo — la rutina lo recibe por
variable de entorno (`BITRIX_WEBHOOK_BASE`) al momento de ejecutarse, no está escrito acá.

El proyecto completo, con más contexto y el histórico de decisiones, vive en la computadora
de Santiago en `bioalimentar-dashboard-2026/README.md`.
