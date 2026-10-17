import type { Vitals } from "@/api/consultations";

export type VitalKey = keyof Vitals;

/** Each vital in the order a clinician reads them, with its unit and the API's plausible range (spec §11). */
export const VITALS: {
  key: VitalKey;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: string;
}[] = [
  {
    key: "bp_systolic",
    label: "BP systolic",
    unit: "mmHg",
    min: 50,
    max: 300,
    step: "1",
  },
  {
    key: "bp_diastolic",
    label: "BP diastolic",
    unit: "mmHg",
    min: 20,
    max: 200,
    step: "1",
  },
  { key: "pulse", label: "Pulse", unit: "bpm", min: 20, max: 250, step: "1" },
  {
    key: "temperature_c",
    label: "Temperature",
    unit: "°C",
    min: 30,
    max: 45,
    step: "0.1",
  },
  { key: "spo2", label: "SpO₂", unit: "%", min: 50, max: 100, step: "1" },
  {
    key: "respiratory_rate",
    label: "Respiratory rate",
    unit: "/min",
    min: 4,
    max: 80,
    step: "1",
  },
  {
    key: "weight_kg",
    label: "Weight",
    unit: "kg",
    min: 0.5,
    max: 400,
    step: "0.1",
  },
  {
    key: "height_cm",
    label: "Height",
    unit: "cm",
    min: 30,
    max: 250,
    step: "0.1",
  },
];

const DECIMAL_KEYS = new Set<VitalKey>([
  "temperature_c",
  "weight_kg",
  "height_cm",
]);

export function toBody(values: Record<VitalKey, string>): Vitals {
  const body: Record<string, number | string> = {};
  for (const { key } of VITALS) {
    const raw = values[key].trim();
    if (!raw) continue;
    body[key] = DECIMAL_KEYS.has(key) ? raw : Number(raw);
  }
  return body as Vitals;
}

/** What the form checks before sending; the server checks the same and more (§11). */
export function vitalsProblem(values: Record<VitalKey, string>): string | null {
  const filled = VITALS.filter(({ key }) => values[key].trim() !== "");
  if (filled.length === 0) return "Enter at least one vital sign.";
  for (const { key, label, min, max } of filled) {
    const n = Number(values[key]);
    if (!Number.isFinite(n) || n < min || n > max)
      return `${label} must be between ${min} and ${max}.`;
  }
  const sys = values.bp_systolic.trim();
  const dia = values.bp_diastolic.trim();
  if (!!sys !== !!dia)
    return "Blood pressure needs both systolic and diastolic.";
  if (sys && dia && Number(dia) >= Number(sys))
    return "Diastolic pressure must be lower than systolic.";
  return null;
}
