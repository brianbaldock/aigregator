// GATOR RUN — Chrome-dino-style endless runner. You're a pixel gator
// sprinting across server racks, jumping gaps and obstacles (firewalls,
// captchas). Space/Up to jump, ESC to quit. Speeds up over time.

let mountEl = null;
let onNavigate = null;
let canvas = null;
let ctx = null;
let raf = null;

const W = 640;
const H = 200;

const game = {
  running: false,
  gameOver: false,
  score: 0,
  best: parseInt(localStorage.getItem("gator.best") || "0", 10),
  speed: 4,
  spawnTimer: 0,
  obstacles: [],
  gator: { x: 60, y: 0, vy: 0, w: 40, h: 28, onGround: true },
  groundY: H - 30,
};

function reset() {
  game.running = true;
  game.gameOver = false;
  game.score = 0;
  game.speed = 4;
  game.spawnTimer = 60;
  game.obstacles = [];
  game.gator.y = 0;
  game.gator.vy = 0;
  game.gator.onGround = true;
}

function spawnObstacle() {
  // Two flavors: gap (skipped — visual ground break) or pillar (firewall/captcha block)
  const kind = Math.random() < 0.4 ? "gap" : "block";
  if (kind === "gap") {
    game.obstacles.push({ type: "gap", x: W + 20, w: 60 + Math.random() * 40 });
  } else {
    const tall = Math.random() < 0.3;
    game.obstacles.push({
      type: "block",
      x: W + 20,
      w: 22 + Math.random() * 16,
      h: tall ? 50 : 30,
      label: pick(["FW", "RACK", "CAPTCHA", "404", "AUTH", "DDoS"]),
    });
  }
}

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

function jump() {
  if (game.gator.onGround && !game.gameOver) {
    game.gator.vy = -11;
    game.gator.onGround = false;
  } else if (game.gameOver) {
    reset();
  }
}

function tick() {
  if (!game.running) return;

  // Physics
  if (!game.gameOver) {
    game.gator.vy += 0.55;
    game.gator.y += game.gator.vy;
    if (game.gator.y >= 0) {
      game.gator.y = 0;
      game.gator.vy = 0;
      game.gator.onGround = true;
    }

    game.score++;
    if (game.score % 500 === 0) game.speed += 0.5;

    // Spawn
    game.spawnTimer--;
    if (game.spawnTimer <= 0) {
      spawnObstacle();
      game.spawnTimer = 60 + Math.floor(Math.random() * 60) - Math.floor(game.speed * 2);
      game.spawnTimer = Math.max(28, game.spawnTimer);
    }

    // Move obstacles + collision
    for (const o of game.obstacles) o.x -= game.speed;
    game.obstacles = game.obstacles.filter(o => o.x + o.w > -10);

    for (const o of game.obstacles) {
      const gx = game.gator.x;
      const gy = game.groundY + game.gator.y - game.gator.h;
      const gw = game.gator.w;
      const gh = game.gator.h;
      if (o.type === "block") {
        const ox = o.x, oy = game.groundY - o.h, oh = o.h, ow = o.w;
        if (gx < ox + ow && gx + gw > ox && gy < oy + oh && gy + gh > oy) {
          die();
        }
      } else if (o.type === "gap") {
        // Gator falls if hovering over gap and not airborne above it
        const overGap = gx + gw / 2 > o.x && gx + gw / 2 < o.x + o.w;
        if (overGap && game.gator.onGround) {
          die();
        }
      }
    }
  }

  draw();
  raf = requestAnimationFrame(tick);
}

function die() {
  game.gameOver = true;
  if (game.score > game.best) {
    game.best = game.score;
    localStorage.setItem("gator.best", String(game.best));
  }
}

function draw() {
  // Sky / background
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, W, H);

  // Distant racks (parallax)
  ctx.fillStyle = "#0a3a1a";
  for (let i = 0; i < 8; i++) {
    const x = (i * 100 - (game.score / 4) % 100) | 0;
    ctx.fillRect(x, H - 80, 40, 30);
  }

  // Ground line — with gaps drawn as black
  ctx.fillStyle = "#1f7a3a";
  ctx.fillRect(0, game.groundY, W, 2);
  ctx.fillStyle = "#000";
  for (const o of game.obstacles) {
    if (o.type === "gap") ctx.fillRect(o.x, game.groundY - 2, o.w, 8);
  }

  // Obstacles
  ctx.font = "10px monospace";
  ctx.textAlign = "center";
  for (const o of game.obstacles) {
    if (o.type === "block") {
      ctx.fillStyle = "#ff5252";
      ctx.fillRect(o.x, game.groundY - o.h, o.w, o.h);
      ctx.fillStyle = "#fff";
      ctx.fillText(o.label, o.x + o.w / 2, game.groundY - o.h / 2 + 4);
    }
  }

  // Gator (pixel art-ish silhouette)
  const gx = game.gator.x;
  const gy = game.groundY + game.gator.y - game.gator.h;
  drawGator(gx, gy);

  // HUD
  ctx.fillStyle = "#8cdc96";
  ctx.font = "14px monospace";
  ctx.textAlign = "right";
  ctx.fillText(`SCORE ${String(game.score).padStart(5, "0")}   BEST ${String(game.best).padStart(5, "0")}`, W - 10, 20);
  ctx.textAlign = "left";

  if (game.gameOver) {
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(0, H / 2 - 30, W, 60);
    ctx.fillStyle = "#ff5252";
    ctx.font = "bold 22px monospace";
    ctx.textAlign = "center";
    ctx.fillText("GAME OVER", W / 2, H / 2);
    ctx.fillStyle = "#8cdc96";
    ctx.font = "12px monospace";
    ctx.fillText("press SPACE to retry  ·  ESC to quit", W / 2, H / 2 + 18);
    ctx.textAlign = "left";
  }
}

function drawGator(x, y) {
  // Body
  ctx.fillStyle = "#3aaa4a";
  ctx.fillRect(x + 4, y + 12, 28, 14);
  // Head
  ctx.fillRect(x + 26, y + 8, 18, 12);
  // Snout
  ctx.fillRect(x + 36, y + 14, 8, 4);
  // Eye
  ctx.fillStyle = "#fff";
  ctx.fillRect(x + 32, y + 10, 3, 3);
  ctx.fillStyle = "#000";
  ctx.fillRect(x + 33, y + 11, 1, 1);
  // Tail
  ctx.fillStyle = "#3aaa4a";
  ctx.fillRect(x, y + 16, 6, 4);
  // Legs (animated)
  const step = Math.floor(game.score / 4) % 2;
  ctx.fillRect(x + 8, y + 24, 4, step ? 6 : 4);
  ctx.fillRect(x + 22, y + 24, 4, step ? 4 : 6);
  // Teeth
  ctx.fillStyle = "#fff";
  ctx.fillRect(x + 36, y + 17, 1, 1);
  ctx.fillRect(x + 38, y + 17, 1, 1);
  ctx.fillRect(x + 40, y + 17, 1, 1);
}

function keyHandler(e) {
  if (e.key === "Escape") {
    stop();
    onNavigate("/doors");
    return true;
  }
  if (e.key === " " || e.key === "ArrowUp" || e.key === "w" || e.key === "W") {
    e.preventDefault();
    jump();
    return true;
  }
  return true;
}

function stop() {
  game.running = false;
  if (raf) cancelAnimationFrame(raf);
  raf = null;
}

export function start(mount, ctx0, navigate) {
  mountEl = mount;
  onNavigate = navigate;
  mountEl.innerHTML = `<div class="bbs-screen">
<div class="bbs-header">GATOR RUN  ::  press SPACE to jump  ·  ESC to quit</div>
<div style="display:flex; justify-content:center; padding:8px 0;">
  <canvas id="gator-canvas" width="${W}" height="${H}" style="image-rendering: pixelated; background:#000; border:1px solid #1f7a3a;"></canvas>
</div>
<div class="bbs-row bbs-dim" style="text-align:center;">jump server racks, firewalls, captchas. don't fall in the gaps.</div>
</div>`;
  canvas = mountEl.querySelector("#gator-canvas");
  ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  reset();
  tick();
  return { keyHandler };
}
