const relative = new Intl.RelativeTimeFormat('fr-FR', { numeric: 'auto' });
const absolute = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
];

/** « il y a 3 heures » : repérer d'un coup d'œil une source figée, mieux qu'une date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "à l'instant";
}

export function fullDate(iso: string): string {
  return absolute.format(new Date(iso));
}
