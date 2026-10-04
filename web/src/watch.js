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

export function createWatcher({ threshold = 8, stableFrames = 2, cooldownMs = 3000 } = {}) {
  let last = null, stable = 0, sent = null, sentAt = -Infinity;
  return {
    step(hash, now) {
      stable = last && frameDiff(hash, last) < threshold ? stable + 1 : 1;
      last = hash;
      const changed = !sent || frameDiff(hash, sent) >= threshold;
      if (changed && stable >= stableFrames && now - sentAt >= cooldownMs) {
        sent = hash;
        sentAt = now;
        return true;
      }
      return false;
    },
  };
}
