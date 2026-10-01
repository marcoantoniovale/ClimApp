"use client";

import { useState } from "react";

import type { Hora } from "@/lib/data";
import { cardinal, cielo, esNoche, fechaLocal, grados, hora, horaCorta, nombreDia } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";

const COL = 56;        // ancho de cada hora (px)
const TEMP_H = 64;     // alto de la banda de temperatura
const RAIN_H = 36;     // alto de la banda de probabilidad de lluvia
const PAD = 10;

/**
 * Pronóstico por hora: franja desplazable con dos gráficos de una serie cada uno y su propia
 * escala (sin doble eje): temperatura (línea) y probabilidad de lluvia (barras, 0–100 %).
 * La hora seleccionada (toque, mouse o teclado) muestra todos sus valores debajo.
 */
export default function HourlyForecast({ horas }: { horas: Hora[] }) {
  const [sel, setSel] = useState(0);
  if (horas.length === 0) return null;

  const temps = horas.map((h) => h.temperatura).filter((t): t is number => t != null);
  const min = Math.min(...temps);
  const max = Math.max(...temps);
  const span = Math.max(max - min, 4);
  const y = (t: number) => PAD + (1 - (t - min) / span) * (TEMP_H - 2 * PAD);
  const width = horas.length * COL;
  const points = horas
    .map((h, i) => (h.temperatura == null ? null : `${i * COL + COL / 2},${y(h.temperatura).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  const iMax = horas.findIndex((h) => h.temperatura === max);
  const iMin = horas.findIndex((h) => h.temperatura === min);
  const h = horas[sel];
  const hoy = fechaLocal(horas[0].hora);

  return (
    <section aria-labelledby="por-hora" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-4 sm:p-5">
      <h2 id="por-hora" className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Próximas 48 horas</h2>

      <div className="no-scrollbar -mx-1 overflow-x-auto px-1">
        <div style={{ width }} className="relative">
          {/* Encabezado: día, hora, ícono, temperatura */}
          <div className="flex" role="listbox" aria-label="Seleccionar hora">
            {horas.map((x, i) => {
              const dia = fechaLocal(x.hora);
              const nuevoDia = i === 0 || dia !== fechaLocal(horas[i - 1].hora);
              return (
                <button
                  key={x.hora}
                  type="button"
                  role="option"
                  aria-selected={i === sel}
                  aria-label={`${nombreDia(dia, hoy)} ${hora(x.hora)}: ${grados(x.temperatura)}, ${cielo(x.estado_cielo).texto}, lluvia ${x.precip_prob ?? "–"} %`}
                  onClick={() => setSel(i)}
                  onMouseEnter={() => setSel(i)}
                  onFocus={() => setSel(i)}
                  style={{ width: COL }}
                  className={`flex shrink-0 flex-col items-center rounded-xl pb-1 pt-1 text-center focus-visible:outline-2 focus-visible:outline-climapp-teal ${i === sel ? "bg-climapp-line/60" : ""}`}
                >
                  <span className="h-4 text-[10px] font-semibold uppercase text-climapp-teal">
                    {nuevoDia ? (i === 0 ? "Ahora" : nombreDia(dia, hoy)) : ""}
                  </span>
                  <span className="text-xs text-slate-400">{i === 0 ? "" : `${horaCorta(x.hora)} h`}</span>
                  <WeatherIcon code={x.estado_cielo} night={esNoche(x.hora)} size={28} className="my-1" />
                  <span className="text-sm font-medium text-slate-100">{grados(x.temperatura)}</span>
                </button>
              );
            })}
          </div>

          {/* Temperatura (una serie) */}
          <svg width={width} height={TEMP_H} aria-hidden="true" className="mt-1 block">
            <line x1={sel * COL + COL / 2} x2={sel * COL + COL / 2} y1={0} y2={TEMP_H} stroke="#475569" strokeWidth="1" />
            <polyline points={points} fill="none" stroke="var(--color-climapp-temp)" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
            {[iMax, iMin].map((i) => horas[i].temperatura != null && (
              <circle key={`m${i}`} cx={i * COL + COL / 2} cy={y(horas[i].temperatura!)} r="3"
                fill="var(--color-climapp-temp)" stroke="var(--color-climapp-card)" strokeWidth="2" />
            ))}
            {h.temperatura != null && (
              <circle cx={sel * COL + COL / 2} cy={y(h.temperatura)} r="5" fill="var(--color-climapp-temp)"
                stroke="var(--color-climapp-card)" strokeWidth="2" />
            )}
          </svg>

          {/* Probabilidad de lluvia (una serie, 0–100 %) */}
          <svg width={width} height={RAIN_H + 14} aria-hidden="true" className="block">
            <line x1="0" x2={width} y1={RAIN_H} y2={RAIN_H} stroke="var(--color-climapp-line)" strokeWidth="1" />
            {horas.map((x, i) => {
              const p = x.precip_prob ?? 0;
              const bh = (p / 100) * (RAIN_H - 4);
              return p >= 5 ? (   // bajo 5 % no se dibuja: una barra mínima sugeriría lluvia
                <g key={x.hora}>
                  <path
                    d={`M${i * COL + 16},${RAIN_H} v${-Math.max(bh - 4, 0)} q0,-4 4,-4 h${COL - 40} q4,0 4,4 v${Math.max(bh - 4, 0)} z`}
                    fill="var(--color-climapp-rain)"
                  />
                  {p >= 30 && (
                    <text x={i * COL + COL / 2} y={RAIN_H - bh - 3} textAnchor="middle" fontSize="10" fill="#cbd5e1">{p}%</text>
                  )}
                </g>
              ) : null;
            })}
            <text x="2" y={RAIN_H + 12} fontSize="10" fill="#94a3b8">Prob. de lluvia</text>
          </svg>
        </div>
      </div>

      {/* Detalle de la hora seleccionada (capa de hover/toque) */}
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 rounded-2xl bg-climapp-bg/60 p-3 text-sm sm:grid-cols-4" aria-live="polite">
        <div className="col-span-2 font-semibold text-slate-100 sm:col-span-4">
          {nombreDia(fechaLocal(h.hora), hoy)} {hora(h.hora)} · {cielo(h.estado_cielo).texto}
        </div>
        <Item label="Temperatura" value={`${grados(h.temperatura)} (modelos ${grados(h.rango[0])} a ${grados(h.rango[1])})`} />
        <Item label="Sensación" value={grados(h.sensacion_termica)} />
        <Item label="Lluvia" value={`${h.precip_prob ?? "–"} % · ${h.precipitacion ?? 0} mm`} />
        <Item label="Viento" value={`${h.viento ?? "–"} km/h ${cardinal(h.viento_dir)}${h.rafaga != null ? ` · ráf. ${h.rafaga}` : ""}`} />
        <Item label="Humedad" value={`${h.humedad ?? "–"} %`} />
      </dl>
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 sm:block">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-slate-100">{value}</dd>
    </div>
  );
}
