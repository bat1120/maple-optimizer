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

describe("screen watch rows", () => {
  const base = { signature: "s2", evaluated: true, slot: "모자", setting: { equipment: 2, hyper: 3, ability: 2 },
                 delta_pct: 0.8, per_100m: null, main_stat_gain: 300, excluded: [],
                 read: { name: "에테르넬 메이지햇", category: "모자", part: "모자", starforce: 22,
                         total: { INT: 120, MATK: 60 }, potentials: ["INT +12%"], price: null } };

  it("읽은 총 옵션을 보여주고, 가격을 못 읽으면 입력해서 억당을 계산한다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      { ok: true, status: 200, json: async () => ({ ranking: [{ per_100m: 0.0178, main_stat_gain_per_100m: 6.7 }] }) });
    render(<ScreenWatch name="내신부레테" defense={300} capture={null} initialItems={[base]} />);
    expect(screen.getByText(/총옵션 INT 120 · 마력 60/)).toBeInTheDocument();
    expect(screen.getByText(/가격 못 읽음/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("에테르넬 메이지햇 가격"), { target: { value: "45억" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "억당 계산" })); });
    const body = JSON.parse(f.mock.calls[0][1].body);
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/listings`);
    expect(body).toMatchObject({ setting: base.setting, boss_defense: 300,
                                 listings: [{ slot: "모자", name: "에테르넬 메이지햇", total: { INT: 120, MATK: 60 }, price: 4_500_000_000 }] });
    expect(await screen.findByText(/억당 \+0\.018%/)).toBeInTheDocument();
  });

  it("평가를 보류한 이유를 보여준다", () => {
    const pending = { signature: "s3", evaluated: false, reason: "총 옵션을 읽지 못했어요", read: { name: "모자", potentials: ["LUK +13%"] } };
    render(<ScreenWatch name="x" defense={300} capture={null} initialItems={[pending]} />);
    expect(screen.getByText(/총 옵션을 읽지 못했어요/)).toBeInTheDocument();
  });
});

describe("screen watch share target", () => {
  it("게임 창이나 웹 경매장 탭을 공유하라고 안내한다", () => {
    render(<ScreenWatch name="x" defense={300} capture={null} />);
    expect(screen.getByText(/게임 창/)).toHaveTextContent("창 모드");
  });
});

describe("screen watch pending rows", () => {
  const pen = { name: "이볼빙 녹스 마법깃펜", category: "보조무기", part: "보조무기", starforce: 0,
                total: { INT: 10 }, potentials: ["마력 +12%"], price: 32_799_999_999 };
  it("캐릭터 조회 전에 읽은 매물은 조회하면 다시 평가한다", async () => {
    const pending = { signature: "p1", evaluated: false, reason: "캐릭터를 먼저 조회해 주세요", read: pen };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ items: [
      { signature: "p1", evaluated: true, slot: "보조무기", delta_pct: -2.381, per_100m: -0.007, main_stat_gain: -900, excluded: [], read: pen }] }));
    const { rerender } = render(<ScreenWatch name="" defense={300} capture={null} initialItems={[pending]} />);
    expect(f).not.toHaveBeenCalled();
    await act(async () => { rerender(<ScreenWatch name="내신부레테" defense={300} capture={null} initialItems={[pending]} />); });
    expect(f.mock.calls[0][0]).toBe("/api/vision/evaluate");
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ name: "내신부레테", boss_defense: 300, listings: [pen] });
    expect(await screen.findByText(/보조무기 자리 · 실딜 -2\.381%/)).toBeInTheDocument();
  });

  it("목록에서만 본 매물(총옵션·잠재 없음)은 한 줄로 접는다", () => {
    const listOnly = (sig, price) => ({ signature: sig, evaluated: false, reason: "총 옵션을 읽지 못했어요",
      read: { name: "미트라의 분노 : 마법사", total: {}, potentials: [], price } });
    render(<ScreenWatch name="x" defense={300} capture={null} initialItems={[listOnly("a", 9e9), listOnly("b", 1e10)]} />);
    expect(screen.getByText("목록에서 본 매물 2개 (툴팁을 띄우면 평가해요)")).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});

describe("screen watch fee", () => {
  it("화면에서 판매 수수료를 읽으면 알려준다", async () => {
    vi.useFakeTimers();
    const hashes = [100, 100, 100];
    let k = 0;
    const capture = { start: async () => ({ hash: () => new Array(256).fill(hashes[Math.min(k++, 2)]),
                                            image: () => "data:image/jpeg;base64,AAA", stop: vi.fn() }) };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ tooltip_visible: false, fee_rate: 0.03, items: [] }));
    const onFeeRate = vi.fn();
    render(<ScreenWatch name="x" defense={300} capture={capture} intervalMs={1500} onFeeRate={onFeeRate} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 4; i++) await act(async () => { vi.advanceTimersByTime(1500); });
    expect(onFeeRate).toHaveBeenCalledWith(0.03);
  });
});

describe("screen watch needs-check lines", () => {
  it("공식 옵션표에 없는 줄은 확인 필요로 표시한다", () => {
    const row = { signature: "u1", evaluated: true, slot: "장갑", delta_pct: 0.5, excluded: [],
                  unverified_lines: ["HP 회복 아이템 및 회복 스킬 +30%"],
                  read: { name: "에테르넬 나이트글러브", total: { STR: 253 }, potentials: ["크리티컬 데미지 +8%"], price: 1e10 } };
    render(<ScreenWatch name="x" defense={300} capture={null} initialItems={[row]} />);
    expect(screen.getByText(/확인 필요: HP 회복 아이템 및 회복 스킬 \+30%/)).toBeInTheDocument();
  });
});
