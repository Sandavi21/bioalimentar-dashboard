#!/usr/bin/env python3
"""
refresh.py
Version en Python (solo libreria estandar) de refresh.ps1, pensada para correr
en el sandbox de una rutina programada en la nube (Linux, sin PowerShell).

Que hace, en orden:
  1. Descarga todos los "deals" (negocios) creados en el anio configurado, de
     TODOS los pipelines, usando el metodo batch de Bitrix24.
  2. Descarga la lista de usuarios (asesores).
  3. Agrupa/agrega los datos por asesor + pipeline + mes + etapa, clasificando
     cada etapa en uno de 4 estados: asignado / negado / cerrado / descartado.
  4. Inyecta ese JSON agregado + el logo (logo.png) en dashboard_template.html
     y escribe el resultado final en dashboard.html.

Este script NO trae el token del webhook de Bitrix24 escrito adentro (a proposito,
para poder subirlo a un repo sin filtrar el token). Hay que pasarlo por la variable
de entorno BITRIX_WEBHOOK_BASE antes de correrlo:

  BITRIX_WEBHOOK_BASE="https://.../rest/ID/TOKEN" python3 refresh.py

Espera encontrar, en el mismo directorio:
  dashboard_template.html
  data/logo.png
Y escribe dashboard.html + data/aggregated.json en el mismo directorio.
"""
import base64
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("BITRIX_WEBHOOK_BASE")
if not BASE:
    raise SystemExit("Falta la variable de entorno BITRIX_WEBHOOK_BASE (URL del webhook de Bitrix24).")

ECUADOR_TZ = timezone(timedelta(hours=-5))
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def formatted_now_ecuador():
    now = datetime.now(ECUADOR_TZ)
    return f"{now.day} de {MESES_ES[now.month - 1]} de {now.year}, {now.strftime('%H:%M')} (Ecuador)"
ROOT = os.path.dirname(os.path.abspath(__file__))
YEAR_START = "2026-01-01T00:00:00"
YEAR_END = "2027-01-01T00:00:00"

CATEGORY_MAP = {
    "0": "BIO BALANCEADOS", "15": "LEADS", "27": "BiOALiMENTAR", "31": "IXINA",
    "33": "Comentarios", "35": "MASCOTAS", "39": "CLIENTES LIBRA",
    "41": "DISTRIBUIDORES", "45": "BIO HUEVOS", "47": "BIOEQUINOS",
}

STAGE_NAMES = {
    "0": {"NEW": "Lead (prospecto)", "UC_A4CDA3": "Aceptación Ley Datos", "PREPARATION": "Gestión Lead", "PREPAYMENT_INVOICE": "Asignación Distribuidor", "EXECUTING": "Asignación Asesor Comercial", "UC_AJP7PG": "Visita Programada Asesor", "UC_F84LPS": "Negociación Asesor Comercial", "UC_XW1HAN": "Lead No Calificado", "UC_N62RU8": "LNC x Datos", "UC_78KBLT": "Documentación", "UC_Y7A4D5": "Apertura Cliente", "WON": "Negocio Ganado", "LOSE": "Negocio Perdido"},
    "15": {"NEW": "Lead (prospecto)", "UC_SLCXVT": "Tránsito", "UC_RWN3I6": "LNQ", "UC_VRLSB7": "Nombre", "UC_9O9AVY": "Concurso Arma tu Manada", "UC_ZBPZJ1": "Burguer Show", "WON": "Conversión PV/BAAS", "LOSE": "Venta Perdida PV", "APOLOGY": "Venta Perdida BAAS"},
    "27": {"NEW": "Lead", "PREPARATION": "Solicitud de Trabajo", "UC_E400T9": "Colaboradores", "EXECUTING": "Pasantías/Tesis", "PREPAYMENT_INVOIC": "Proveedores", "FINAL_INVOICE": "Visitas Planta", "UC_BFN16P": "Quejas y Reclamos", "UC_1ZCA8V": "Comentarios", "UC_A0E4EF": "Donaciones", "WON": "Cerrado Ganado", "LOSE": "Cerrado Perdido", "APOLOGY": "Analizar la Falla"},
    "31": {"NEW": "Prospecto", "UC_NJ8YO6": "Interacción FB/IG", "UC_AW8PHN": "Conversaciones WhatsApp", "PREPARATION": "Intentando Contactar", "PREPAYMENT_INVOIC": "Contactado", "UC_X87RTK": "Interés", "UC_Y4OG4G": "Agendado", "UC_XW2ER4": "Visita Realizada", "UC_7GGY6R": "Revisión Planos", "UC_PE93AY": "Diseño por Presentar", "UC_2MC0DQ": "Primera Presentación", "UC_7L8Y6J": "Segunda Presentación", "FINAL_INVOICE": "Tercera Presentación", "UC_IJYLGA": "Análisis Comercial", "UC_XN3WR5": "Reunión Cierre", "UC_4L6BCW": "Cerrado Contrato", "3": "Descartado No Contactado", "UC_9M2DL1": "Descartado No Perfil", "4": "Descartado (Tiempo Entrega)", "5": "Asignado Tienda Guayaquil", "6": "Asignado Tienda Cumbayá", "7": "Interés Electrodomésticos", "UC_PS93FP": "Proyecto Presentado No Ganado", "WON": "Proyecto Ganado", "LOSE": "Proyecto Perdido"},
    "33": {"NEW": "Comentario", "PREPARATION": "Crear Documentos", "PREPAYMENT_INVOIC": "Factura", "EXECUTING": "En Progreso", "FINAL_INVOICE": "Factura Final", "WON": "Cerrado Ganado", "LOSE": "Cerrado Perdido", "APOLOGY": "Analizar la Falla"},
    "35": {"UC_0IX14J": "Aceptación Ley Datos", "NEW": "Lead Prospecto", "PREPARATION": "Gestión", "PREPAYMENT_INVOIC": "Asignación Distribuidor", "UC_ZW34R1": "Asignación Asesor Comercial", "UC_482EN6": "Negociación", "EXECUTING": "BAAS", "FINAL_INVOICE": "Lead No Calificado", "UC_R41WBI": "Comentarios", "WON": "Negocio Ganado", "LOSE": "Venta Perdida"},
    "39": {"PREPAYMENT_INVOIC": "Todos los Clientes", "PREPARATION": "Clientes Mascotas", "NEW": "Clientes Pecuario", "EXECUTING": "Clientes Actualizados", "FINAL_INVOICE": "Factura Final", "WON": "Cerrado Ganado", "LOSE": "Cerrado Perdido", "APOLOGY": "Analizar la Falla"},
    "41": {"NEW": "Asesores Comerciales (Dis)", "UC_4FJV9X": "Asesores Comerciales (Bio)", "WON": "Cerrado Ganado", "LOSE": "Cerrado Perdido", "APOLOGY": "Analizar la Falla"},
    "45": {"NEW": "Con los Huevos en la Cancha", "UC_CIAC7H": "Burguer Show", "PREPARATION": "Aceptación de Datos", "PREPAYMENT_INVOIC": "Gestión", "UC_58UEV8": "Ganador Contactado", "UC_W75R78": "Reclamos", "EXECUTING": "Asesor Comercial", "FINAL_INVOICE": "Reposiciones Quejas", "UC_IWIML8": "LNQ", "WON": "Cerrado Ganado", "LOSE": "Cerrado Perdido", "APOLOGY": "Analizar la Falla"},
    "47": {"NEW": "Leads", "UC_2O6P96": "Contactado", "UC_M7I0KU": "Asignado a Distribuidor", "PREPARATION": "Asignado Asesor Comercial", "UC_TCU9Q1": "LNQ", "WON": "Negociación Ganada", "LOSE": "Negociación Perdida", "APOLOGY": "Analizar la Falla"},
}


def bitrix_call(method, payload=None, http_method="GET"):
    url = f"{BASE}/{method}.json"
    if http_method == "GET":
        req = urllib.request.Request(url)
    else:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_bucket(code):
    return {"WON": "cerrado", "LOSE": "negado", "APOLOGY": "descartado"}.get(code, "asignado")


def fetch_all_deals():
    count_body = {"filter": {">=DATE_CREATE": YEAR_START, "<DATE_CREATE": YEAR_END}, "select": ["ID"]}
    total = bitrix_call("crm.deal.list", count_body, "POST")["total"]
    print(f"   Total: {total} registros")

    page_size = 50
    num_pages = (total + page_size - 1) // page_size
    all_deals = []
    select_fields = ["ID", "ASSIGNED_BY_ID", "STAGE_ID", "CATEGORY_ID", "DATE_CREATE", "OPPORTUNITY", "CLOSEDATE"]

    def build_cmd(start):
        params = [("order[ID]", "ASC"), ("filter[>=DATE_CREATE]", YEAR_START), ("filter[<DATE_CREATE]", YEAR_END)]
        params += [("select[]", f) for f in select_fields]
        params.append(("start", str(start)))
        qs = urllib.parse.urlencode(params)
        return f"crm.deal.list?{qs}"

    page_index = 0
    while page_index < num_pages:
        cmd = {}
        for _ in range(50):
            if page_index >= num_pages:
                break
            cmd[f"c{page_index}"] = build_cmd(page_index * page_size)
            page_index += 1
        resp = bitrix_call("batch", {"halt": 0, "cmd": cmd}, "POST")
        result = resp["result"]["result"]
        for key in result:
            all_deals.extend(result[key])
        print(f"   {page_index} / {num_pages} paginas, {len(all_deals)} filas")
    return all_deals


def fetch_all_users():
    all_users = []
    start = 0
    while start is not None:
        url = f"{BASE}/user.get.json?start={start}"
        with urllib.request.urlopen(url, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
        all_users.extend(resp["result"])
        start = resp.get("next")
    print(f"   {len(all_users)} usuarios")
    return all_users


def main():
    print("1-2/4 Descargando deals y usuarios de Bitrix24...")
    deals = fetch_all_deals()
    users = fetch_all_users()

    print("3/4 Agregando datos...")
    user_map = {}
    for u in users:
        name = f"{u.get('NAME','')} {u.get('LAST_NAME','')}".strip()
        user_map[str(u["ID"])] = name if name else f"Usuario {u['ID']}"

    agg = {}
    for d in deals:
        adv_id = str(d.get("ASSIGNED_BY_ID"))
        adv_name = user_map.get(adv_id, f"Usuario {adv_id}")
        cat_id = str(d.get("CATEGORY_ID"))
        cat_name = CATEGORY_MAP.get(cat_id, f"Pipeline {cat_id}")
        month = d["DATE_CREATE"][:7]
        code = re.sub(r"^C\d+:", "", d.get("STAGE_ID", ""))
        stage_name = STAGE_NAMES.get(cat_id, {}).get(code, code)
        bucket = get_bucket(code)
        try:
            opp = float(d["OPPORTUNITY"]) if d.get("OPPORTUNITY") else 0.0
        except ValueError:
            opp = 0.0
        key = (adv_id, cat_id, month, code)
        if key not in agg:
            agg[key] = {
                "advisor_id": adv_id, "advisor_name": adv_name,
                "category_id": cat_id, "category_name": cat_name,
                "month": month, "stage_code": code, "stage_name": stage_name,
                "bucket": bucket, "count": 0, "opportunity_sum": 0.0,
            }
        agg[key]["count"] += 1
        agg[key]["opportunity_sum"] += opp

    result = sorted(agg.values(), key=lambda r: (r["advisor_name"], r["category_name"], r["month"], r["bucket"]))
    print(f"   {len(result)} filas agregadas")

    with open(os.path.join(ROOT, "data", "aggregated.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("4/4 Regenerando dashboard.html...")
    with open(os.path.join(ROOT, "dashboard_template.html"), "r", encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(ROOT, "data", "logo.png"), "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("ascii")

    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    final = (template.replace("/*__LEADS_DATA__*/", compact)
                      .replace("/*__LOGO_B64__*/", logo_b64)
                      .replace("/*__GENERATED_AT__*/", formatted_now_ecuador()))
    with open(os.path.join(ROOT, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(final)

    print(f"Listo. dashboard.html actualizado en {ROOT}")


if __name__ == "__main__":
    main()
