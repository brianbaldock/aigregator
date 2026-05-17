// TIC TAC TOE — vs perfect-play minimax AI. Player is X, AI is O.
// Arrow keys move cursor, ENTER places, R resets, ESC exits.

let mountEl = null;
let onNavigate = null;
const STATE = {
  board: Array(9).fill(null),  // null | "X" | "O"
  cursor: 4,
  turn: "X",
  status: "Your move (X). Arrows to move, ENTER to place.",
  gameOver: false,
};

function reset() {
  STATE.board.fill(null);
  STATE.cursor = 4;
  STATE.turn = "X";
  STATE.status = "Your move (X). Arrows to move, ENTER to place.";
  STATE.gameOver = false;
}

function winner(b) {
  const lines = [
    [0,1,2],[3,4,5],[6,7,8],
    [0,3,6],[1,4,7],[2,5,8],
    [0,4,8],[2,4,6],
  ];
  for (const [a,b2,c] of lines) {
    if (b[a] && b[a] === b[b2] && b[a] === b[c]) return { who: b[a], line: [a,b2,c] };
  }
  if (b.every(x => x)) return { who: "DRAW" };
  return null;
}

function minimax(b, player) {
  const w = winner(b);
  if (w) {
    if (w.who === "O") return { score: 10 };
    if (w.who === "X") return { score: -10 };
    return { score: 0 };
  }
  const moves = [];
  for (let i = 0; i < 9; i++) {
    if (b[i]) continue;
    const next = b.slice(); next[i] = player;
    const res = minimax(next, player === "O" ? "X" : "O");
    moves.push({ idx: i, score: res.score });
  }
  if (player === "O") {
    return moves.reduce((best, m) => m.score > best.score ? m : best, { score: -Infinity });
  }
  return moves.reduce((best, m) => m.score < best.score ? m : best, { score: Infinity });
}

function aiMove() {
  const move = minimax(STATE.board, "O");
  if (move.idx != null) {
    STATE.board[move.idx] = "O";
    const w = winner(STATE.board);
    if (w) finish(w);
    else { STATE.turn = "X"; STATE.status = "Your move (X)."; render(); }
  }
}

function finish(w) {
  STATE.gameOver = true;
  if (w.who === "X") STATE.status = "★ YOU WIN ★ (statistically impossible — well done.) Press R to play again.";
  else if (w.who === "O") STATE.status = "WOPR WINS. Press R to play again.";
  else STATE.status = "DRAW. The only winning move... Press R to play again.";
  render();
}

function cellChar(i) {
  const v = STATE.board[i];
  if (v) return v;
  if (!STATE.gameOver && i === STATE.cursor) return "·";
  return " ";
}

function render() {
  // Build the board as a pre-formatted plain text block to avoid the
  // glow/text-shadow on bright spans throwing off character alignment.
  // 3 chars per cell, ASCII separators only.
  const ch = (i) => {
    const v = STATE.board[i];
    if (v) return v;
    if (!STATE.gameOver && i === STATE.cursor) return ".";
    return " ";
  };
  const row = (a,b,d) => ` ${ch(a)} | ${ch(b)} | ${ch(d)} `;
  const sep = "---+---+---";
  const board =
`  ${row(0,1,2)}
  ${sep}
  ${row(3,4,5)}
  ${sep}
  ${row(6,7,8)}`;
  mountEl.innerHTML = `<div class="bbs-screen">
<div class="bbs-header">TIC TAC TOE  ::  YOU vs WOPR</div>
<div class="bbs-row"> </div>
<pre class="bbs-board">${board}</pre>
<div class="bbs-row"> </div>
<div class="bbs-row bbs-bright">${STATE.status}</div>
<div class="bbs-row bbs-dim">Arrows: move  ·  ENTER: place  ·  R: reset  ·  ESC: back</div>
</div>`;
}

function moveCursor(dx, dy) {
  let x = STATE.cursor % 3;
  let y = Math.floor(STATE.cursor / 3);
  x = Math.max(0, Math.min(2, x + dx));
  y = Math.max(0, Math.min(2, y + dy));
  STATE.cursor = y * 3 + x;
  render();
}

function place() {
  if (STATE.gameOver) return;
  if (STATE.turn !== "X") return;
  if (STATE.board[STATE.cursor]) return;
  STATE.board[STATE.cursor] = "X";
  const w = winner(STATE.board);
  if (w) { finish(w); return; }
  STATE.turn = "O";
  STATE.status = "WOPR is thinking...";
  render();
  setTimeout(aiMove, 350);
}

function keyHandler(e) {
  if (e.key === "Escape") { onNavigate("/doors"); return true; }
  if (e.key === "r" || e.key === "R") { reset(); render(); return true; }
  if (STATE.gameOver) return true;
  if (e.key === "ArrowLeft")  { e.preventDefault(); moveCursor(-1, 0); return true; }
  if (e.key === "ArrowRight") { e.preventDefault(); moveCursor( 1, 0); return true; }
  if (e.key === "ArrowUp")    { e.preventDefault(); moveCursor( 0,-1); return true; }
  if (e.key === "ArrowDown")  { e.preventDefault(); moveCursor( 0, 1); return true; }
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); place(); return true; }
  // 1-9 keys → direct cell select
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 9) { STATE.cursor = n - 1; place(); return true; }
  return true;
}

export function start(mount, ctx, navigate) {
  mountEl = mount;
  onNavigate = navigate;
  reset();
  render();
  return { keyHandler };
}
