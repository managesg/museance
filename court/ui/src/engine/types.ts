import type { Attack, CaseBundle, Claim, Evidence, LedgerEvent, LockStatus, SheetLine, Verdict } from '../contracts';
export type Phase = 'dig' | 'read' | 'raise' | 'swear' | 'cross' | 'repair' | 'bench' | 'sentence';
export const PHASES: readonly Phase[] = ['dig', 'read', 'raise', 'swear', 'cross', 'repair', 'bench', 'sentence'];
export type CardStatus = 'sealed' | 'sworn' | 'under-cross' | LockStatus;
export interface CardView { claim: Claim; status: CardStatus; verdict: Verdict | null; bets: { trueCredits: number; falseCredits: number }; repairedFrom?: string; }
export type GhostMood = 'idle' | 'hopeful' | 'sad' | 'flicker' | 'relieved';
export type McCluskyMood = 'idle' | 'swearing' | 'nervous' | 'caught' | 'fainted' | 'relieved';
export type HootMood = 'idle' | 'writing' | 'attacking' | 'unimpressed' | 'satisfied';
export type FauxMood = 'hidden' | 'wave' | 'bow' | 'smug';
export type StenoMood = 'idle' | 'scribbling' | 'sealing';
export type GuyKind = 'calculator' | 'brush' | 'clock' | 'keycap';
export type GuyState = 'idle' | 'nervous' | 'glitch' | 'locked' | 'repaired' | 'fabricated';
export type ExhibitMode = 'dark' | 'evidence' | 'reading' | 'booting' | 'live' | 'cross';
export type Pastry = 'croissant' | 'bagel' | 'eclair' | 'pretzel' | 'canele' | 'kouign';
export interface LeaderRow { name: string; pastry: Pastry; credits: number; wins: number; losses: number; }
export interface BenchSuggestion { label: string; steps: string[]; }
export interface Measured { value: number; of: number; }
export interface Scores { credibilityStart: number; credibility: number; brier: number | null; fidelity: number | null; claimsMade: number; claimsSurvived: number; struck: number; unsworn: number; fabricated: number; rollbacks: number; falseStrikes: Measured | null; trapsCaught: Measured | null; }
export interface StageState {
  phase: Phase; beat: number; beats: number; playing: boolean;
  app: string; appLabel: string; source: CaseBundle['source'];
  evidenceShown: Evidence[]; sheetShown: SheetLine[]; wordCount: number;
  exhibits: { original: ExhibitMode; revival: ExhibitMode; originalSrc: string; revivalSrc: string };
  cards: CardView[]; focusId: string | null;
  attacks: { attack: Attack; opened: boolean; verdict: Verdict | null }[];
  divergence: { ref: string; original: string; revival: string; steps: string[] } | null;
  scores: Scores; stress: number;
  moods: { ghost: GhostMood; mcclusky: McCluskyMood; hoot: HootMood; faux: FauxMood; steno: StenoMood };
  guys: { screen: string; kind: GuyKind; glyph?: string; state: GuyState }[];
  ledgerTail: LedgerEvent[];
  subtitle: { who: 'McCLUSKY' | 'DR. HOOT' | 'THE CLERK'; text: string } | null;
  banner: string | null;
  bench: { open: boolean; last: Verdict | null; runs: number };
  leaderboard: LeaderRow[];
}
export interface Beat { phase: Phase; kind: string; ms: number; apply: (s: StageState) => StageState; }
