// Mirrors /contracts/*.schema.json and CONTRACTS.md. Change only after a [CONTRACT] post.
export type Tier = 'A' | 'B' | 'C' | 'D';
export type Label = 'SEEN' | 'GUESSED' | 'FABRICATED';
export type LockStatus = 'LOCKED' | 'STRUCK' | 'UNSWORN' | 'FABRICATED';
export interface Evidence { id: string; app: string; tier: Tier; kind: 'page' | 'screenshot' | 'video' | 'issue' | 'doc'; source: string; text?: string; path?: string; license?: string; }
export interface SheetLine { id: string; screen: string; text: string; label: 'SEEN' | 'GUESSED'; citations: string[]; conflicts: string[]; }
export interface BehaviorSheet { app: string; lines: SheetLine[]; }
export interface ClaimTest { steps: string[]; observe: string; expect: string; }
export interface Claim { id: string; app: string; screen: string; text: string; test: ClaimTest; tier: Tier; label: Label; evidence?: string[]; confidence: number; bond: number; commit?: string; }
export interface Attack { id: string; app: string; screen: string; steps: string[]; observe: string; commit?: string; }
export interface Verdict { ref: string; kind: 'claim' | 'attack'; original: string; revival: string; claim_true?: boolean | null; match: boolean; flaky: boolean; shrunk_steps?: string[]; }
export interface Lock { claim_id: string; status: LockStatus; reason?: string; }
export interface LedgerEvent { seq: number; ts: string; type: string; payload: unknown; prev_hash: string; hash: string; }
export interface CaseFile { app: string; fidelity: number; brier: number; credibility_start: number; credibility_end: number; locked: string[]; struck: string[]; fabricated: string[]; unsworn: string[]; counts: Record<string, number>; }
// P3-only extension, not a shared contract: one repair of a struck claim as the stage shows it.
export interface Repair { struck_id: string; claim: Claim; verdict: Verdict; rollback: boolean; note: string; }
export interface CaseBundle {
  app: string; appLabel: string; source: 'fixture' | 'runs' | 'atlas';
  evidence: Evidence[]; sheet: BehaviorSheet | null; claims: Claim[]; attacks: Attack[]; verdicts: Verdict[];
  locks: Lock[]; ledger: LedgerEvent[]; caseFile: CaseFile | null; repairs: Repair[];
}
