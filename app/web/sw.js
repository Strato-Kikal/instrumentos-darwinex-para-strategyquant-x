"use strict";
// Service worker de Instrumentos SQX. Guarda solo la interfaz para que abra rápido y se pueda
// instalar. Los datos (api/) nunca se guardan: siempre se consultan en el momento.
const CACHE = "instrumentos-sqx-v5";
const INTERFAZ = ["./", "index.html", "estilos.css", "app.js", "manifest.webmanifest",
  "iconos/icono.svg", "iconos/icono-192.png", "iconos/icono-512.png", "iconos/apple-touch-icon.png"];

self.addEventListener("install", (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(INTERFAZ)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ev) => {
  ev.waitUntil(caches.keys()
    .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (ev) => {
  const peticion = ev.request;
  const url = new URL(peticion.url);
  if (peticion.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) {
    ev.respondWith(fetch(peticion).catch(() => new Response(JSON.stringify({
      error: { codigo: "sin_conexion",
               mensaje: "Sin conexión: la aplicación necesita Internet para consultar las fuentes en el momento." },
    }), { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } })));
    return;
  }
  // Interfaz: primero la red (para recibir actualizaciones); sin red, la copia guardada.
  ev.respondWith(fetch(peticion).then((resp) => {
    if (resp.ok) {
      const copia = resp.clone();
      caches.open(CACHE).then((c) => c.put(peticion, copia));
    }
    return resp;
  }).catch(() => caches.match(peticion, { ignoreSearch: true }).then((r) => r || caches.match("index.html"))));
});
