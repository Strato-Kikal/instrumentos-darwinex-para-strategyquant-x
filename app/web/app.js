"use strict";
// Instrumentos SQX: interfaz. La consulta de fuentes, la validación y el PDF se hacen en el servidor
// (api/instrumento), porque Darwinex y el BCE no permiten que un navegador lea sus datos desde otra web.

const TABLA1 = ["nombre", "tipo", "pip_tick", "point_value", "no_pip_tick", "spread",
                "spread_instantaneo", "slippage", "min_dist", "order_mult", "order_step"];
const TABLA2 = ["modelo_comision", "comision", "tipo_swap", "swap_largo", "swap_corto", "triple_swap",
                "rollover", "cobro_swap"];
const PEND = "PENDIENTE DE VERIFICAR";

const $ = (id) => document.getElementById(id);
let ultimo = null;

function el(etiqueta, clase, texto) {
  const e = document.createElement(etiqueta);
  if (clase) e.className = clase;
  if (texto !== undefined && texto !== null) e.textContent = texto;
  return e;
}

function mensaje(tipo, texto, sugerencias) {
  const caja = $("mensaje");
  caja.replaceChildren();
  if (!texto) return;
  const div = el("div", `aviso ${tipo}`, texto);
  div.setAttribute("role", tipo === "error" ? "alert" : "status");
  if (sugerencias && sugerencias.length) {
    const s = el("div", "sugerencias");
    for (const sug of sugerencias) {
      const b = el("button", "", sug);
      b.type = "button";
      b.addEventListener("click", () => { $("simbolo").value = sug; consultar(sug); });
      s.append(b);
    }
    div.append(s);
  }
  caja.append(div);
}

function casillas(destino, campos, detalle, textos) {
  const porCampo = Object.fromEntries(detalle.map((f) => [f.campo, f]));
  const ul = el("ul", "casillas");
  for (const c of campos) {
    const f = porCampo[c];
    if (!f) continue;
    const li = el("li");
    const det = el("details");
    const sum = el("summary");
    const pend = f.valor === PEND;
    const texto = (textos && textos[c]) ? String(textos[c]).replace(/\n/g, " · ") : f.valor;
    sum.append(el("span", "nombre", f.casilla),
               el("span", "valor" + (pend ? " pend" : ""), texto));
    const meta = el("span", "meta");
    meta.append(el("span", `origen o-${f.tipo}`, f.origen));
    sum.append(meta);
    det.append(sum, el("p", "explicacion", f.explicacion));
    li.append(det);
    ul.append(li);
  }
  destino.replaceChildren(ul);
}

function mostrar(r) {
  ultimo = r;
  const completa = r.estado === "COMPLETA";
  const estado = $("estado");
  estado.className = `tarjeta estado ${completa ? "completa" : "incompleta"}`;
  const destino = r.ticker_darwinex !== r.simbolo ? ` → Darwinex ${r.ticker_darwinex}` : "";
  estado.replaceChildren(
    el("span", "titulo", `${r.simbolo}${destino} · ${r.estado_texto}`),
    el("span", "linea", `${r.clase} · consultado el ${r.consulta_utc} UTC`),
  );
  if (!completa) {
    estado.append(el("span", "linea", "No uses esas casillas en StrategyQuant hasta completarlas."));
  }
  const p = r.perfil;
  $("perfil").textContent = `${p.nombre} · Bróker ${p.broker} · ${p.plataforma} · Cuenta en ${p.divisa_cuenta} · ` +
    `Datos ${p.datos.proveedor} («${p.datos.broker_profile_descarga}») clonados a «${p.datos.zona_clon}».`;
  casillas($("tabla1"), TABLA1, r.detalle, r.textos);
  casillas($("tabla2"), TABLA2, r.detalle, r.textos);

  const pruebas = $("pruebas");
  pruebas.replaceChildren();
  if (r.pendientes.length) pruebas.append(el("li", "aviso-linea", `Faltan datos: ${r.faltan.join(", ")}.`));
  for (const t of r.pruebas_sqx) pruebas.append(el("li", "", t));
  pruebas.append(el("li", "", "Compara también cada valor con MT5 → Observación del mercado → Especificación."));

  const cons = $("consultas");
  cons.replaceChildren();
  for (const c of r.consultas) {
    const li = el("li", c.estado === "correcto" ? "" : "fallo",
      `${c.fuente}: ${c.estado}${c.hora_utc ? ` (${c.hora_utc} UTC)` : ""}${c.detalle ? ` · ${c.detalle}` : ""}`);
    cons.append(li);
  }
  const notas = $("notas");
  notas.replaceChildren();
  for (const l of r.spread_lineas) notas.append(el("li", l.includes("PENDIENTE") ? "aviso-linea" : "", l));
  for (const a of r.avisos) notas.append(el("li", "aviso-linea", a));
  for (const n of r.tabla.notas) notas.append(el("li", "", n));
  $("bloque-notas").hidden = !notas.children.length;

  $("resultado").hidden = false;
  $("descargar").textContent = "Descargar PDF";
}

async function consultar(texto) {
  const simbolo = (texto || "").trim();
  if (!simbolo) {
    mensaje("error", "Escribe un símbolo, por ejemplo EURUSD.");
    $("simbolo").focus();
    return;
  }
  if (navigator.onLine === false) {
    mensaje("error", "No hay conexión a Internet. La aplicación necesita consultar las fuentes en el momento.");
    return;
  }
  const boton = $("obtener");
  boton.disabled = true;
  $("resultado").hidden = true;
  mensaje("cargando", `Consultando Darwinex, el feed de precios y el BCE para ${simbolo.toUpperCase()}…`);
  const q = new URLSearchParams({ simbolo });
  const medio = $("spread_medio").value.trim();
  const hasta = $("datos_hasta").value.trim();
  if (medio) q.set("spread_medio", medio);
  if (hasta) q.set("datos_hasta", hasta);
  try {
    const resp = await fetch(`api/instrumento?${q}`, { cache: "no-store" });
    let datos = null;
    try { datos = await resp.json(); } catch (e) { datos = null; }
    if (!resp.ok || !datos || datos.error) {
      const err = (datos && datos.error) || {};
      mensaje("error", err.mensaje || `El servidor respondió con el código ${resp.status}.`, err.sugerencias);
      return;
    }
    mensaje(null);
    mostrar(datos);
    history.replaceState(null, "", `?simbolo=${encodeURIComponent(datos.simbolo)}`);
  } catch (e) {
    mensaje("error", "No se pudo contactar con el servidor de la aplicación. Comprueba la conexión e inténtalo de nuevo.");
  } finally {
    boton.disabled = false;
  }
}

function descargarPdf() {
  if (!ultimo || !ultimo.pdf) return;
  const binario = atob(ultimo.pdf.base64);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = ultimo.pdf.nombre;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  $("descargar").textContent = `PDF descargado: ${ultimo.pdf.nombre}`;
}

document.addEventListener("DOMContentLoaded", () => {
  $("consulta").addEventListener("submit", (ev) => { ev.preventDefault(); consultar($("simbolo").value); });
  $("descargar").addEventListener("click", descargarPdf);
  const inicial = new URLSearchParams(location.search).get("simbolo");
  if (inicial) { $("simbolo").value = inicial; consultar(inicial); }
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
});
