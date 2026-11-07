// Where everything stands on the 1920x1080 design canvas, as [x, y, w, h] in design px.
import type { CSSProperties } from 'react';

export const STAGE_W = 1920;
export const STAGE_H = 1080;

export type Zone = readonly [x: number, y: number, w: number, h: number];

export const ZONES = {
  rail: [0, 0, 1920, 84],
  original: [56, 110, 500, 440],
  revival: [1364, 110, 500, 440],
  ghost: [820, 90, 280, 330],
  // Faux pops up at the revival frame's left edge, clear of its plate and of the tag the lens hangs to the right.
  faux: [1236, 236, 240, 430],
  // The left wing is narrower than McClusky, the meter and the candle side by side: the candle stands
  // back against the wall, the meter in front, and McClusky's wig top clears the exhibit's plate.
  candle: [16, 420, 160, 300],
  meter: [0, 610, 240, 340],
  mcclusky: [200, 466, 370, 466],
  // The tape hangs on the wainscot under the revival; Hoot stands left of it with his head below the plate.
  ledger: [1560, 548, 360, 220],
  hoot: [1292, 548, 280, 400],
  steno: [1740, 730, 170, 250],
  cards: [560, 430, 800, 520],
  subtitles: [460, 904, 1000, 64],
  // While the bench console (960 wide, from x 928) is open, the clerk speaks from the left of it.
  subtitlesBeside: [24, 904, 880, 64],
  numbers: [0, 984, 1920, 96],
} as const satisfies Record<string, Zone>;

// One floor slot per app screen, alternating left and right of the table, inner slots first.
export const GUY_SLOTS: readonly Zone[] = [
  [432, 836, 112, 140],
  [1338, 830, 112, 140],
  [306, 846, 112, 140],
  [1462, 840, 112, 140],
  [180, 852, 112, 140],
  [1586, 850, 112, 140],
];

export const place = ([x, y, w, h]: Zone): CSSProperties => ({ left: x, top: y, width: w, height: h });
