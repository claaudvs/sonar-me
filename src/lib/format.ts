const dateFmt = new Intl.DateTimeFormat("es", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "6 nov 2026, 10:42" */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const parts = Object.fromEntries(dateFmt.formatToParts(d).map((p) => [p.type, p.value]));
  const month = parts.month.replace(".", "");
  return `${parts.day} ${month} ${parts.year}, ${parts.hour}:${parts.minute}`;
}
