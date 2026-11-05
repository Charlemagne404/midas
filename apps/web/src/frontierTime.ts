export const preciseUtcTime = (value: string | null | undefined) => {
  if (!value) return 'Not recorded';
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return instant.toLocaleString();
  const fraction = /\.(\d+)(?=Z$|[+-]\d{2}:\d{2}$)/i.exec(value)?.[1];
  return `${instant.toISOString().slice(0, 19)}${fraction ? `.${fraction}` : ''} UTC`;
};
