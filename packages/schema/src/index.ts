export * from "./generated";
export * from "./time";

/** Layer ids are `${sourceId}.${category}`; categories mirror models.ControlCategory / LineKind. */
export function splitLayerId(id: string): { sourceId: string; category: string } {
  const i = id.indexOf(".");
  return { sourceId: id.slice(0, i), category: id.slice(i + 1) };
}
