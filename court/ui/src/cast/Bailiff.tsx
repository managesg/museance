import { useId } from 'react';
import './bailiff.css';

type Mood = 'idle' | 'locking';

const TITLE: Record<Mood, string> = {
  idle: 'The Bailiff, a tortoise in a peaked cap, holding his key ring and an open padlock',
  locking: 'The Bailiff turning his key in the padlock as the shackle snaps shut',
};

// Art data in the 380x520 viewBox; floor line at y 494.
// Locking swings each arm 26deg at the shoulder: the fist (132 345) and the keyhole (210 347) both land on (172 330).
const SHELL = 'M190 190C272 188 332 236 342 316C348 380 330 430 300 456C262 466 118 466 80 456C50 430 32 380 38 316C48 236 108 192 190 190Z';
const SHELL_SHADE = 'M272 204C316 226 338 266 342 316C348 380 330 430 300 456L290 452C318 424 334 378 330 318C327 272 306 232 272 204Z';
const SHELL_INNER = 'M190 206C262 204 316 246 324 316C330 372 316 416 290 442C256 452 124 452 90 442C64 416 50 372 56 316C64 246 118 208 190 206Z';
const SHELL_INNER_SHADE = 'M262 220C300 238 320 270 324 316C330 372 316 416 290 442L280 440C304 414 316 372 312 318C309 278 292 246 262 220Z';
// Seams and rim ticks are drawn only where the shell shows past the jacket.
const SHELL_SEAMS = 'M96 290L65 281M90 370L56 363M284 290L315 281M290 370L324 363M150 214L134 240M230 214L246 240';
// Rim ticks sit on matched points of the inner and outer curves, so none crosses the outline.
const SHELL_TICKS =
  'M246 214L253 200M294 246L308 237M317 286L334 282M324 363L341 370M314 405L328 417M66 405L52 417M56 363L39 370M63 287L46 282M86 248L72 238M134 216L127 201';

const LEG_L = 'M118 446C116 462 114 476 110 488C124 497 166 497 180 488C178 474 176 460 174 446Z';
const LEG_R = 'M262 446C264 462 266 476 270 488C256 497 214 497 200 488C202 474 204 460 206 446Z';
const LEG_SHADE = 'M174 446C176 460 178 474 180 488C176 492 170 495 164 496C168 480 167 462 164 446ZM262 446C264 460 266 474 270 488C266 492 260 495 254 496C258 480 257 462 254 446Z';
const LEG_SCALES = 'M126 462q7 5 14 0M148 468q7 5 14 0M128 476q7 5 14 0M214 462q7 5 14 0M236 468q7 5 14 0M216 476q7 5 14 0';
const NAILS = [124, 145, 166, 214, 235, 256].map((x) => `M${x - 6} 487C${x - 6} 495 ${x + 6} 495 ${x + 6} 487Z`).join('');

const JACKET = 'M190 226C232 226 266 234 280 250C298 272 306 324 304 378C302 418 294 444 286 460C250 468 130 468 94 460C86 444 78 418 76 378C74 324 82 272 100 250C114 234 148 226 190 226Z';
const JACKET_SHADE = 'M268 240C274 243 277 246 280 250C298 272 306 324 304 378C302 418 294 444 286 460C278 462 270 463 262 464C280 430 288 384 286 330C285 292 280 262 268 240Z';
const BELT = 'M77 400C140 410 240 410 303 400L303 418C240 428 140 428 77 418Z';
const BUCKLE = 'M179 400H201Q205 400 205 404V422Q205 426 201 426H179Q175 426 175 422V404Q175 400 179 400Z';
const BUTTONS = [166, 214].flatMap((x) => [272, 306, 340, 374].map((y) => [x, y] as const));
const NECK = 'M158 196C156 212 152 228 148 246H232C228 228 224 212 222 196Z';
const NECK_SHADE = 'M210 200C214 214 218 230 220 246H232C228 228 224 212 222 196Z';
const COLLAR = 'M146 232C170 242 210 242 234 232L238 254C212 264 168 264 142 254Z';

const HEAD = 'M190 102C234 102 258 126 258 158C258 192 230 214 190 214C150 214 122 192 122 158C122 126 146 102 190 102Z';
const HEAD_SHADE = 'M236 112C250 124 258 140 258 158C258 192 230 214 190 214C224 204 244 184 246 156C247 138 243 124 236 112Z';
const MOUTH = 'M150 187C168 186 180 186 190 189C200 186 212 186 230 187';
const CAP_CROWN = 'M128 106C114 94 110 78 120 68C148 56 232 56 260 68C270 78 266 94 252 106Z';
const CAP_CROWN_SHADE = 'M236 60C250 62 256 64 260 68C270 78 266 94 252 106H238C248 92 250 74 236 60Z';
const CAP_BAND = 'M132 102C170 108 210 108 248 102L250 124C210 130 170 130 130 124Z';
const CAP_STRAP = 'M136 117C170 123 210 123 244 117';
const CAP_VISOR = 'M128 122C160 132 220 132 252 122C256 134 238 147 190 148C142 147 124 134 128 122Z';
const BADGE = 'M181 72H199Q200 72 200 73V85C200 92 195 96 190 98C185 96 180 92 180 85V73Q180 72 181 72Z';
const BADGE_KEYHOLE = 'M190 79.5A3 3 0 0 1 191.8 84.6L192.6 90H187.4L188.2 84.6A3 3 0 0 1 190 79.5Z';

const SLEEVE_R = 'M142 250C134 236 98 238 94 258C90 288 102 318 112 334C122 344 142 342 150 332C150 304 148 274 142 250Z';
const SLEEVE_R_SHADE = 'M137 244C140 246 141 248 142 250C148 274 150 304 150 332C146 337 141 340 135 342C141 314 142 284 137 244Z';
const SLEEVE_L = 'M238 250C246 236 282 238 286 258C290 288 278 318 268 334C258 344 238 342 230 332C230 304 232 274 238 250Z';
const SLEEVE_L_SHADE = 'M286 258C290 288 278 318 268 334C264 338 259 341 253 342C266 320 274 292 274 260C274 252 271 245 266 240C278 242 285 249 286 258Z';
const FIST = 'M122 331C133 324 149 330 149 344C150 357 139 363 128 360C119 357 114 350 115 341C115 336 118 333 122 331Z';
const FIST_SHADE = 'M144 333C148 336 149 340 149 344C150 357 139 363 128 360C139 355 146 347 144 333Z';
// The palm sits behind the padlock and only the thumb crosses its face, so the lock stays readable when the fist arrives.
const LOCK_HAND = 'M240 326C252 320 268 328 267 344C266 358 254 363 244 360C236 357 232 350 232 342C232 334 235 329 240 326Z';
const LOCK_HAND_SHADE = 'M260 329C265 333 267 338 267 344C266 358 254 363 244 360C256 355 263 345 260 329Z';
const THUMB = 'M247 329C241 326 232 328 230 334C229 339 234 342 240 340C243 339 246 337 247 334Z';

// The short leg ends inside the body when shut; the long leg stays hidden behind it when the shackle lifts.
const SHACKLE = 'M191 318V296A19 19 0 0 1 229 296V345';
const LOCK_BODY = 'M187 312H233Q244 312 244 323V363Q244 374 233 374H187Q176 374 176 363V323Q176 312 187 312Z';
const LOCK_SHADE = 'M235 312.6Q244 314 244 323V363Q244 374 233 374H198Q230 368 232 340Q233 324 235 312.6Z';
const KEYHOLE = 'M210 336.5A6 6 0 0 1 213.7 347.2L215.5 357.5H204.5L206.3 347.2A6 6 0 0 1 210 336.5Z';
const GLINT = 'M0 -14C1.6 -3.2 3.2 -1.6 14 0C3.2 1.6 1.6 3.2 0 14C-1.6 3.2 -3.2 1.6 -14 0C-3.2 -1.6 -1.6 -3.2 0 -14Z';

// A key bow with its hole, hung from its top at 0 0.
const KEY_BOW = 'M0 0C6.5 0 11 5 11 11.5C11 18 6.5 23 0 23C-6.5 23 -11 18 -11 11.5C-11 5 -6.5 0 0 0ZM0 7.2A4.3 4.3 0 1 0 0 15.8A4.3 4.3 0 1 0 0 7.2Z';

function Key({ n, x, y, r, len }: { n: number; x: number; y: number; r: number; len: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${r})`}>
      <g className={`bailiff-key bailiff-key--${n}`} strokeWidth={3.5}>
        <path d={`M-4.5 22H4.5V${len - 17}H15V${len - 11}H10V${len - 6}H15V${len}H-4.5Z`} fill="var(--brass)" />
        <path d="M-7 22H7V29H-7Z" fill="var(--brass-deep)" strokeWidth={3} />
        <path d={KEY_BOW} fill="var(--brass)" fillRule="evenodd" />
      </g>
    </g>
  );
}

function Eye({ cx, clip }: { cx: number; clip: string }) {
  const cy = 152;
  const eye = `M${cx - 15} ${cy}C${cx - 15} ${cy - 9} ${cx - 8} ${cy - 13} ${cx} ${cy - 13}C${cx + 9} ${cy - 13} ${cx + 15} ${cy - 8} ${cx + 15} ${cy}C${cx + 15} ${cy + 9} ${cx + 8} ${cy + 12} ${cx} ${cy + 12}C${cx - 8} ${cy + 12} ${cx - 15} ${cy + 8} ${cx - 15} ${cy}Z`;
  return (
    <>
      <clipPath id={clip}>
        <path d={eye} />
      </clipPath>
      <g clipPath={`url(#${clip})`}>
        <path d={eye} fill="var(--paper)" stroke="none" />
        <g className="bailiff-pupil" stroke="none">
          <circle cx={cx + 1} cy={cy + 3} r={6.5} fill="var(--ink)" />
          <circle cx={cx - 1.5} cy={cy + 1.5} r={1.8} fill="var(--paper)" />
        </g>
        {/* Flat lid at half mast: the deadpan. The blink only slides it down. */}
        <g className="bailiff-lid">
          <path d={`M${cx - 20} ${cy - 30}H${cx + 20}V${cy - 1}H${cx - 20}Z`} fill="var(--bailiff-skin-deep)" stroke="none" />
          <path d={`M${cx - 20} ${cy - 1}H${cx + 20}`} fill="none" strokeWidth={4} />
        </g>
      </g>
      <path d={eye} fill="none" strokeWidth={3.5} />
    </>
  );
}

export function Bailiff({ mood }: { mood: Mood }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  return (
    <svg
      className={`bailiff bailiff--${mood}`}
      viewBox="0 0 380 520"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
      aria-labelledby={`${uid}-title`}
    >
      <title id={`${uid}-title`}>{TITLE[mood]}</title>
      <ellipse cx={190} cy={494} rx={152} ry={14} fill="var(--floor-shadow)" />

      <g stroke="var(--ink)" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        <path d={SHELL} fill="var(--wood-light)" stroke="none" />
        <path d={SHELL_SHADE} fill="var(--wood)" stroke="none" />
        <path d={SHELL_INNER} fill="var(--terracotta)" stroke="none" />
        <path d={SHELL_INNER_SHADE} fill="var(--terracotta-deep)" stroke="none" />
        <path d={SHELL_INNER} fill="none" strokeWidth={3.5} />
        <path d={SHELL_SEAMS + SHELL_TICKS} fill="none" strokeWidth={3.5} />
        <path d={SHELL} fill="none" />

        <path d={LEG_L + LEG_R} fill="var(--owl-cream)" stroke="none" />
        <path d={LEG_SHADE} fill="var(--bailiff-skin-deep)" stroke="none" />
        <path d={LEG_SCALES} fill="none" stroke="var(--bailiff-skin-deep)" strokeWidth={3} />
        <path d={LEG_L + LEG_R} fill="none" />
        <path d={NAILS} fill="var(--paper-deep)" strokeWidth={3} />

        <path d={JACKET} fill="var(--slate-deep)" stroke="none" />
        <path d={JACKET_SHADE} fill="var(--bailiff-deep)" stroke="none" />
        <path d={JACKET} fill="none" />
        <path d="M190 262V401M190 425V465" fill="none" strokeWidth={3.5} />
        <path d={BELT} fill="var(--bailiff-deep)" strokeWidth={4.5} />
        <path d={BUCKLE} fill="var(--brass)" strokeWidth={4} />
        <path d="M183 407H197V419H183Z" fill="var(--bailiff-deep)" strokeWidth={3} />
        <g fill="var(--brass)" strokeWidth={3.5}>
          {BUTTONS.map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r={6.5} />
          ))}
        </g>

        <path d={NECK} fill="var(--owl-cream)" stroke="none" />
        <path d={NECK_SHADE} fill="var(--bailiff-skin-deep)" stroke="none" />
        <path d={NECK} fill="none" />
        <path d="M164 222Q190 229 216 222M159 232Q190 240 221 232" fill="none" strokeWidth={3} />
        <path d={COLLAR} fill="var(--slate-deep)" strokeWidth={4.5} />
        <g fill="var(--brass)" strokeWidth={3}>
          <circle cx={156} cy={249} r={4} />
          <circle cx={224} cy={249} r={4} />
        </g>

        <g className="bailiff-head">
          <path d={HEAD} fill="var(--owl-cream)" stroke="none" />
          <path d={HEAD_SHADE} fill="var(--bailiff-skin-deep)" stroke="none" />
          <g fill="var(--bailiff-skin-deep)" stroke="none">
            <ellipse cx={138} cy={178} rx={6} ry={4} />
            <ellipse cx={150} cy={198} rx={4} ry={3} />
            <ellipse cx={232} cy={196} rx={5} ry={3.5} />
          </g>
          <path d={HEAD} fill="none" />
          <Eye cx={162} clip={`${uid}-l`} />
          <Eye cx={218} clip={`${uid}-r`} />
          <path d="M150 169Q162 174 174 169M206 169Q218 174 230 169" fill="none" strokeWidth={2.5} />
          <g fill="var(--ink)" stroke="none">
            <circle cx={184} cy={172} r={2.2} />
            <circle cx={196} cy={172} r={2.2} />
          </g>
          <path d={MOUTH} fill="none" strokeWidth={4.5} />
          <path d="M172 202Q190 206 208 202" fill="none" stroke="var(--bailiff-skin-deep)" strokeWidth={3} />

          <path d={CAP_CROWN} fill="var(--slate-deep)" stroke="none" />
          <path d={CAP_CROWN_SHADE} fill="var(--bailiff-deep)" stroke="none" />
          <path d={CAP_CROWN} fill="none" />
          <path d={BADGE} fill="var(--brass)" strokeWidth={3.5} />
          <path d={BADGE_KEYHOLE} fill="var(--ink)" stroke="none" />
          <path d={CAP_BAND} fill="var(--bailiff-deep)" strokeWidth={4.5} />
          <path d={CAP_STRAP} fill="none" strokeWidth={8} />
          <path d={CAP_STRAP} fill="none" stroke="var(--brass)" strokeWidth={3.5} />
          <g fill="var(--brass)" strokeWidth={3}>
            <circle cx={136} cy={117} r={4} />
            <circle cx={244} cy={117} r={4} />
          </g>
          <path d={CAP_VISOR} fill="var(--penguin)" strokeWidth={4.5} />
          <path d="M148 136C170 141 210 141 232 136" fill="none" stroke="var(--bailiff-sheen)" strokeWidth={3} />
        </g>

        <g className="bailiff-arm-l">
          <path d={SLEEVE_L} fill="var(--slate-deep)" stroke="none" />
          <path d={SLEEVE_L_SHADE} fill="var(--bailiff-deep)" stroke="none" />
          <path d={SLEEVE_L} fill="none" />
          <path d="M231 322C242 330 258 330 268 322" fill="none" stroke="var(--brass)" strokeWidth={4} />
          <g className="bailiff-lock-plumb">
            <g className="bailiff-shackle" fill="none">
              <path d={SHACKLE} strokeWidth={15} />
              <path d={SHACKLE} stroke="var(--ghost-shade)" strokeWidth={8} />
            </g>
            <path d={LOCK_HAND} fill="var(--owl-cream)" stroke="none" />
            <path d={LOCK_HAND_SHADE} fill="var(--bailiff-skin-deep)" stroke="none" />
            <path d={LOCK_HAND} fill="none" strokeWidth={4.5} />
            <path d={LOCK_BODY} fill="var(--brass)" stroke="none" />
            <path d={LOCK_SHADE} fill="var(--brass-deep)" stroke="none" />
            <path d={LOCK_BODY} fill="none" strokeWidth={4.5} />
            <path d="M177 325H243" fill="none" strokeWidth={3} />
            <g fill="var(--ink)" stroke="none">
              <circle cx={184} cy={318.5} r={2.2} />
              <circle cx={236} cy={318.5} r={2.2} />
              <path d={KEYHOLE} />
            </g>
            <path d={THUMB} fill="var(--owl-cream)" strokeWidth={4} />
            <g transform="translate(238 272)">
              <path className="bailiff-glint" d={GLINT} fill="var(--flame-core)" strokeWidth={3} />
            </g>
          </g>
        </g>

        <g className="bailiff-arm-r">
          <path d={SLEEVE_R} fill="var(--slate-deep)" stroke="none" />
          <path d={SLEEVE_R_SHADE} fill="var(--bailiff-deep)" stroke="none" />
          <path d={SLEEVE_R} fill="none" />
          <path d="M112 322C122 330 138 330 149 322" fill="none" stroke="var(--brass)" strokeWidth={4} />
          <g className="bailiff-twist">
            {/* Two counter-rotations keep the ring hanging plumb through the swing and the turn. */}
            <g className="bailiff-plumb-arm">
              <g className="bailiff-plumb-twist">
                <g className="bailiff-ring-sway">
                  <Key n={1} x={119.4} y={395} r={20} len={60} />
                  <Key n={3} x={144.6} y={395} r={-20} len={56} />
                  <Key n={2} x={132} y={399} r={0} len={68} />
                  <circle cx={132} cy={377} r={22} fill="none" strokeWidth={11} />
                  <circle cx={132} cy={377} r={22} fill="none" stroke="var(--brass)" strokeWidth={5} />
                </g>
              </g>
            </g>
            <path d={KEY_BOW} transform="translate(157 330)" fill="var(--brass)" fillRule="evenodd" strokeWidth={3.5} />
            <path d={FIST} fill="var(--owl-cream)" stroke="none" />
            <path d={FIST_SHADE} fill="var(--bailiff-skin-deep)" stroke="none" />
            <path d={FIST} fill="none" strokeWidth={4.5} />
            <path d="M116 343Q123 346 130 342M118 352Q125 355 131 351M139 332C145 336 147 343 143 348" fill="none" strokeWidth={3} />
          </g>
        </g>
      </g>
    </svg>
  );
}
