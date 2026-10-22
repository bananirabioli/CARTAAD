import messages from "./es-MX.json";

export const LOCALE = "es-MX";

type Params = Record<string, string | number | null | undefined>;

function lookup(key: string): unknown {
  let node: unknown = messages;
  for (const part of key.split(".")) {
    if (node && typeof node === "object" && part in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }
  return node;
}

/** Translate a dotted key from es-MX.json. Missing keys return the key itself (visible in UI). */
export function t(key: string, params?: Params): string {
  const value = lookup(key);
  if (typeof value !== "string") return key;
  if (!params) return value;
  return value.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = params[name];
    return v === undefined || v === null ? "" : String(v);
  });
}

/** Translate an enum value: tEnum("stance", "a_favor") → "A favor". Falls back to the raw value. */
export function tEnum(group: string, value: string | null | undefined): string {
  if (!value) return t("common.none");
  const label = lookup(`enums.${group}.${value}`);
  return typeof label === "string" ? label : value;
}

export function enumOptions(group: string): { value: string; label: string }[] {
  const node = lookup(`enums.${group}`);
  if (!node || typeof node !== "object") return [];
  return Object.entries(node as Record<string, string>).map(([value, label]) => ({ value, label }));
}

const dateFmt = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" });
// Day-precision values are stored as UTC midnight: format them in UTC to avoid off-by-one days.
const dayFmt = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeZone: "UTC" });
const numFmt = new Intl.NumberFormat(LOCALE);

export function fmtDate(value: string | null | undefined): string {
  return value ? dateFmt.format(new Date(value)) : t("common.none");
}

export function fmtDay(value: string | null | undefined): string {
  return value ? dayFmt.format(new Date(value)) : t("common.none");
}

export function fmtNum(value: number | null | undefined, digits?: number): string {
  if (value === null || value === undefined) return t("common.none");
  return digits === undefined ? numFmt.format(value) : value.toFixed(digits);
}
