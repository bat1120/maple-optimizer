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

describe("screen watch corrections", () => {
  const row = { signature: "c1", frame_id: "1-abcdef12", evaluated: true, slot: "모자", delta_pct: 0.8, excluded: [],
                read: { name: "에테르넬 메이지햇", starforce: 25, total: { INT: 150 }, potential_lines: ["INT +13%"],
                        additional: ["마력 +10"], potentials: ["INT +13%", "마력 +10"], price: 5e9 } };

  it("잘못 읽은 값을 고치면 정답으로 보내고, 다시 평가된 줄로 바꾸고, 학습 데이터 수를 보여준다", async () => {
    const fixed = { ...row, signature: "c2", read: { ...row.read, starforce: 21, corrected: true } };
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(ok({ item: fixed }))
      .mockResolvedValueOnce(ok({ enabled: true, frames: 3, corrected: 1 }));
    render(<ScreenWatch name="내신부레테" defense={300} capture={null} initialItems={[row]} />);
    fireEvent.click(screen.getByRole("button", { name: "고치기" }));
    fireEvent.change(screen.getByLabelText("스타포스"), { target: { value: "21" } });
    fireEvent.change(screen.getByLabelText("윗잠 (한 줄에 하나)"), { target: { value: "INT +13%" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "저장" })); });
    expect(f.mock.calls[0][0]).toBe("/api/vision/correct");
    const body = JSON.parse(f.mock.calls[0][1].body);
    expect(body).toMatchObject({ frame_id: "1-abcdef12", signature: "c1", name: "내신부레테", boss_defense: 300 });
    expect(body.fields).toEqual({ name: "에테르넬 메이지햇", starforce: 21, potentials: ["INT +13%"], additional: ["마력 +10"], price: 5e9 });
    expect(await screen.findByText(/21성/)).toBeInTheDocument();
    expect(screen.getByText(/고친 값/)).toBeInTheDocument();
    expect(screen.getByText("학습 데이터: 프레임 3장 · 고친 것 1건")).toBeInTheDocument();
  });

  it("학습 데이터가 꺼져 있으면(frame_id 없음) 고치기 버튼이 없다", () => {
    render(<ScreenWatch name="x" defense={300} capture={null} initialItems={[{ ...row, frame_id: null }]} />);
    expect(screen.queryByRole("button", { name: "고치기" })).toBeNull();
  });
});

describe("screen watch queue", () => {
  it("읽는 중에도 다음 화면을 동시에 보낸다(최대 3개) — AI 한 장 7~10초라 한 장씩이면 훑는 속도를 못 따라간다", async () => {
    vi.useFakeTimers();
    const seq = [10, 10, 60, 60, 120, 120, 180, 180, 240, 240, 240, 240];
    let k = 0;
    const capture = { start: async () => ({
      hash: () => new Array(256).fill(seq[Math.min(k++, seq.length - 1)]),
      image: () => `data:image/jpeg;base64,${k}`,
      stop: vi.fn(),
    }) };
    const waiting = [];
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((r) => waiting.push(r)));
    render(<ScreenWatch name="x" defense={300} capture={capture} intervalMs={500} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 12; i++) await act(async () => { vi.advanceTimersByTime(500); });
    expect(f).toHaveBeenCalledTimes(3);                       // 셋은 동시에, 나머지 둘은 줄에서 대기
    await act(async () => { waiting.splice(0).forEach((r) => r(ok({ tooltip_visible: true, items: [] }))); });
    for (let i = 0; i < 4; i++) await act(async () => { vi.advanceTimersByTime(500); });
    expect(f).toHaveBeenCalledTimes(5);
    const sent = f.mock.calls.map((c) => JSON.parse(c[1].body).image);
    expect(new Set(sent).size).toBe(5);
  });

  it("1초씩 10개를 훑어도 하나도 버리지 않는다(줄 40장)", async () => {
    vi.useFakeTimers();
    const seq = [];
    for (let v = 0; v < 10; v++) seq.push(20 * v + 10, 20 * v + 10);
    let k = 0;
    const capture = { start: async () => ({
      hash: () => new Array(256).fill(seq[Math.min(k++, seq.length - 1)]),
      image: () => `data:image/jpeg;base64,${Math.min(k, seq.length)}`,
      stop: vi.fn(),
    }) };
    const waiting = [];
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((r) => waiting.push(r)));
    render(<ScreenWatch name="x" defense={300} capture={capture} intervalMs={500} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 22; i++) await act(async () => { vi.advanceTimersByTime(500); });
    for (let round = 0; round < 6; round++) {
      await act(async () => { waiting.splice(0).forEach((r) => r(ok({ tooltip_visible: true, items: [] }))); });
      await act(async () => { vi.advanceTimersByTime(500); });
    }
    expect(f).toHaveBeenCalledTimes(10);
  });
});

describe("screen watch quick hover", () => {
  it("템마다 0.5초만 마우스를 대도 전부 보낸다(기본 0.25초 간격) — 2026-10-06 실측 재현: 0.5초 간격이면 0/20", async () => {
    vi.useFakeTimers();
    const t0 = Date.now();
    const capture = { start: async () => ({
      hash: () => new Array(256).fill(10 + 20 * (Math.floor((Date.now() - t0) / 500) % 10)), // 0.5초마다 다른 템
      image: () => `data:image/jpeg;base64,${Math.floor((Date.now() - t0) / 500)}`,
      stop: vi.fn(),
    }) };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ tooltip_visible: true, items: [] }));
    render(<ScreenWatch name="x" defense={300} capture={capture} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 20; i++) await act(async () => { vi.advanceTimersByTime(250); });   // 5초 = 템 10개
    const sent = new Set(f.mock.calls.filter((c) => c[0] === "/api/vision/listings").map((c) => JSON.parse(c[1].body).image));
    expect(sent.size).toBeGreaterThanOrEqual(9);
  });
});

describe("screen watch equipment scoring", () => {
  it("읽은 툴팁을 넥슨 API 착용 템과 채점해 정확도와 틀린 항목을 보여준다", async () => {
    const row = { signature: "e1", evaluated: false, read: { name: "에테르넬 메이지글러브", starforce: 22, total: { INT: 100 },
                  potential_lines: ["크리티컬 데미지 +8%"], additional: [], potentials: ["크리티컬 데미지 +8%"] } };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({
      matched: 1, unmatched: [], fields_ok: 12, fields: 13, accuracy: 0.9231,
      items: [{ name: "에테르넬 메이지글러브", ok: 12, n: 13, miss: ["스타포스: 정답 22 / 읽음 21"] }] }));
    render(<ScreenWatch name="내신부레테" defense={300} capture={null} initialItems={[row]} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "장비창 채점" })); });
    expect(f.mock.calls[0][0]).toBe("/api/vision/score");
    expect(JSON.parse(f.mock.calls[0][1].body)).toMatchObject({ name: "내신부레테", reads: [{ name: "에테르넬 메이지글러브", starforce: 22 }] });
    expect(screen.getByText(/착용 템 1개 채점 · 항목 정확도 92.3% \(12\/13\)/)).toBeInTheDocument();
    expect(screen.getByText(/스타포스: 정답 22 \/ 읽음 21/)).toBeInTheDocument();
  });
});

describe("screen watch scoring button visibility", () => {
  it("캐릭터를 조회했으면 채점 버튼이 항상 보인다(서버가 읽은 판독을 기억한다)", () => {
    render(<ScreenWatch name="내신부레테" defense={300} capture={null} />);
    expect(screen.getByRole("button", { name: "장비창 채점" })).toBeEnabled();
  });

  it("채점 결과는 모든 템을 ✓/✗로 보여주고, 초기화하면 서버 기억도 지운다", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(ok({ matched: 2, unmatched: [], fields_ok: 32, fields: 33, accuracy: 0.97, note: "",
        items: [{ name: "도전자의 신발", ok: 15, n: 15, miss: [] },
                { name: "에테르넬 메이지글러브", ok: 14, n: 15, miss: ["레벨: 정답 250 / 읽음 225"] }] }))
      .mockResolvedValueOnce(ok({ cleared: true }));
    render(<ScreenWatch name="내신부레테" defense={300} capture={null} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "장비창 채점" })); });
    expect(screen.getByText("✓ 도전자의 신발 15/15")).toBeInTheDocument();
    expect(screen.getByText(/✗ 에테르넬 메이지글러브 14\/15 — 레벨: 정답 250 \/ 읽음 225/)).toBeInTheDocument();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "채점 초기화" })); });
    expect(f.mock.calls[1][0]).toBe("/api/vision/score/reset");
    expect(screen.queryByText("✓ 도전자의 신발 15/15")).toBeNull();
  });
});

describe("screen watch equipped reads", () => {
  it("장비창에서 읽은 착용 템도 모아서 보여주고 채점에 넣는다", async () => {
    vi.useFakeTimers();
    const seq = [10, 10, 60, 60, 60, 60];
    let k = 0;
    const capture = { start: async () => ({ hash: () => new Array(256).fill(seq[Math.min(k++, 5)]),
                                            image: () => `data:image/jpeg;base64,${k}`, stop: vi.fn() }) };
    const ring = { name: "여명의 가디언 엔젤 링", starforce: 18, potential_lines: ["INT +9%"], additional: [], total: { INT: 50 } };
    const pendant = { name: "데이브레이크 펜던트", starforce: 22, potential_lines: ["INT +9%"], additional: [], total: { INT: 80 } };
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(ok({ tooltip_visible: true, items: [], equipped_items: [ring] }))
      .mockResolvedValueOnce(ok({ tooltip_visible: true, items: [], equipped_items: [pendant, ring] }))
      .mockResolvedValueOnce(ok({ matched: 2, unmatched: [], fields_ok: 10, fields: 10, accuracy: 1, items: [], note: "" }));
    render(<ScreenWatch name="내신부레테" defense={300} capture={capture} intervalMs={500} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 6; i++) await act(async () => { vi.advanceTimersByTime(500); });
    expect(screen.getByText(/착용 템 2개: 여명의 가디언 엔젤 링, 데이브레이크 펜던트/)).toBeInTheDocument();
    vi.useRealTimers();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "장비창 채점" })); });
    const body = JSON.parse(f.mock.calls[2][1].body);
    expect(body.reads.map((r) => r.name).sort()).toEqual(["데이브레이크 펜던트", "여명의 가디언 엔젤 링"]);
  });
});

describe("screen watch tooltips only", () => {
  it("기본은 툴팁 있는 화면만 읽고, 목록 화면도 읽기를 켜면 함께 보낸다", async () => {
    vi.useFakeTimers();
    let k = 0;
    const seq = [10, 10, 60, 60, 60];
    const capture = { start: async () => ({ hash: () => new Array(256).fill(seq[Math.min(k++, 4)]),
                                            image: () => "data:image/jpeg;base64,A", stop: vi.fn() }) };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ tooltip_visible: false, items: [] }));
    render(<ScreenWatch name="x" defense={300} capture={capture} intervalMs={500} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 화면 연결" })); });
    for (let i = 0; i < 2; i++) await act(async () => { vi.advanceTimersByTime(500); });
    expect(JSON.parse(f.mock.calls[0][1].body).tooltips_only).toBe(true);
    fireEvent.click(screen.getByLabelText(/목록 화면도 읽기/));
    for (let i = 0; i < 3; i++) await act(async () => { vi.advanceTimersByTime(500); });
    expect(JSON.parse(f.mock.calls.at(-1)[1].body).tooltips_only).toBe(false);
  });
});

describe("screen watch special ring", () => {
  it("특수 반지 매물에는 효과 미반영·레벨 비교 안내를 보여준다", () => {
    const row = { signature: "r", evaluated: true, slot: "반지3", delta_pct: -0.1, per_100m: null, main_stat_gain: -20, excluded: [],
                  special_ring_note: "특수 반지 스킬 효과는 실딜 계산에 없어요 — 스탯만 계산했어요. 이 매물 4레벨 · 지금 낀 컨티뉴어스 링 3레벨",
                  read: { name: "컨티뉴어스 링", total: { INT: 3 }, potentials: [], price: 5e9 } };
    render(<ScreenWatch name="x" defense={300} capture={null} initialItems={[row]} />);
    expect(screen.getByText(/이 매물 4레벨 · 지금 낀 컨티뉴어스 링 3레벨/)).toBeInTheDocument();
  });
});

