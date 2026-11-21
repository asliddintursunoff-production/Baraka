/** Chart helpers only. Money strings from the API are converted to numbers just to
 * position marks on a chart; every visible number comes formatted from the backend. */

export const toMln = (v: string): number => Number(v) / 1_000_000;
