// 공유된 경매장 탭 화면의 변화 감지. 화면이 크게 바뀌고, 바뀐 화면이 N프레임 안정되면(툴팁이 다 뜬 상태)
// 한 번만 분석을 요청한다. 같은 화면은 다시 보내지 않고, 요청 사이에는 쿨다운을 둔다(비전 호출 비용 절약).

export function frameHash(imageData, size = 16) {
  const { width, height, data } = imageData;
  const out = new Array(size * size).fill(0);
  const counts = new Array(size * size).fill(0);
  for (let y = 0; y < height; y++) {
    const by = Math.min(size - 1, Math.floor((y * size) / height));
    for (let x = 0; x < width; x++) {
      const bx = Math.min(size - 1, Math.floor((x * size) / width));
      const i = (y * width + x) * 4;
      out[by * size + bx] += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      counts[by * size + bx] += 1;
    }
  }
  return out.map((v, k) => Math.round(v / (counts[k] || 1)));
}

export function frameDiff(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
  return s / a.length;
}

// 크게(cell 이상) 바뀐 칸의 비율. 툴팁끼리 바뀔 때는 화면 일부만 바뀌어 평균 차이로는 못 잡는다
// (2026-10-06 실측, 32×32: 툴팁 전환 최소 9.3%, 커서 이동 1% 미만, JPEG 잡음 0%)
export function changedFraction(a, b, cell = 12) {
  let n = 0;
  for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > cell) n++;
  return n / a.length;
}

// 툴팁 중심 비교(2026-10-06): 소환수·스킬 이펙트가 움직이면 화면 전체 비교로는 툴팁을 띄워도 '안 멈춤'이 된다
// (실측: 이펙트 배경 위 툴팁 12장 중 안정 판정 0). 서버 툴팁 찾기와 같은 남회색 칸만 비교하고 화려한 칸은 무시한다.
// 실측(실제 프레임, 256×144·32×32): 이펙트만 움직임 — 바뀐 칸 거의 0, 남회색 칸 변동 5% 미만 /
// 다른 템 툴팁 — 남회색 칸 안에서 크게 바뀐 칸 대부분 7% 이상 / 툴팁이 뜨면 남회색 칸 6% 이상 변동.
export function tipHash(imageData, n = 32) {
  const { width, height, data } = imageData;
  const dark = new Array(n * n).fill(0), lum = new Array(n * n).fill(0), cnt = new Array(n * n).fill(0);
  for (let y = 0; y < height; y++) {
    const by = Math.min(n - 1, Math.floor((y * n) / height));
    for (let x = 0; x < width; x++) {
      const k = by * n + Math.min(n - 1, Math.floor((x * n) / width));
      const i = (y * width + x) * 4, r = data[i], g = data[i + 1], b = data[i + 2];
      const l = 0.299 * r + 0.587 * g + 0.114 * b;
      const sat = Math.max(r, g, b) - Math.min(r, g, b);
      if (l > 30 && l < 95 && sat < 34 && b >= r) dark[k] += 1; // 툴팁 바탕: 어둡고 채도 낮은 남회색
      lum[k] += l;
      cnt[k] += 1;
    }
  }
  return { dark: dark.map((v, k) => v / (cnt[k] || 1)), lum: lum.map((v, k) => v / (cnt[k] || 1)) };
}

export function tipSame(a, b, { cell = 0.6, flip = 0.06, big = 0.05, lumCell = 12 } = {}) {
  let flips = 0, both = 0, moved = 0;
  for (let k = 0; k < a.dark.length; k++) {
    const da = a.dark[k] >= cell, db = b.dark[k] >= cell;
    if (da !== db) flips++;
    else if (da) {
      both++;
      if (Math.abs(a.lum[k] - b.lum[k]) > lumCell) moved++;
    }
  }
  return flips / a.dark.length < flip && (both ? moved / both : 0) < big;
}

export function createWatcher({ threshold = 8, stableFrames = 2, cooldownMs = 3000, minChanged = null, same: sameFn = null } = {}) {
  let last = null, stable = 0, sent = null, sentAt = -Infinity;
  return {
    step(hash, now) {
      const same = sameFn || ((x, y) => frameDiff(x, y) < threshold && (minChanged == null || changedFraction(x, y) < minChanged));
      stable = last && same(hash, last) ? stable + 1 : 1;
      last = hash;
      const changed = !sent || !same(hash, sent);
      if (changed && stable >= stableFrames && now - sentAt >= cooldownMs) {
        sent = hash;
        sentAt = now;
        return true;
      }
      return false;
    },
  };
}
