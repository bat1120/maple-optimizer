import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import ScreenWatch from "./ScreenWatch.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });

describe("screen watch panel", () => {
  it("화면 공유를 지원하지 않으면 안내한다", async () => {
    render(<ScreenWatch name="x" defense={300} capture={null} />);
    fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("화면 공유");
  });

  it("화면이 바뀌어 안정되면 분석을 보내고, 평가 결과와 중복 지문을 이어서 보낸다", async () => {
    vi.useFakeTimers();
    const hashes = [100, 100, 100, 180, 180];
    let k = 0;
    const capture = { start: async () => ({
      hash: () => new Array(256).fill(hashes[Math.min(k++, hashes.length - 1)]),
      image: () => "data:image/jpeg;base64,AAA",
      stop: vi.fn(),
    }) };
    const item = { signature: "sig1", evaluated: true, slot: "반지4", delta_pct: 1.234, per_100m: 0.041, main_stat_gain: 712,
                   read: { name: "센 반지", price: 3e9, potentials: ["INT +12%"], starforce: 17 }, excluded: [] };
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(ok({ tooltip_visible: true, items: [item] }))
      .mockResolvedValueOnce(ok({ tooltip_visible: true, items: [{ ...item, evaluated: false }] }));
    render(<ScreenWatch name="내신부레테" defense={300} capture={capture} intervalMs={1500} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 6; i++) await act(async () => { vi.advanceTimersByTime(1500); });
    expect(f).toHaveBeenCalledTimes(2);
    expect(JSON.parse(f.mock.calls[0][1].body)).toMatchObject({ name: "내신부레테", boss_defense: 300, seen: [] });
    expect(JSON.parse(f.mock.calls[1][1].body).seen).toEqual(["sig1"]);
    expect(screen.getByText(/센 반지/)).toBeInTheDocument();
    expect(screen.getByText(/반지4 자리 · 실딜 \+1\.234%/)).toBeInTheDocument();
    expect(screen.getAllByText(/센 반지/)).toHaveLength(1);   // 같은 매물은 한 번만 표시
  });
});
