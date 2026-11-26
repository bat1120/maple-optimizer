import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import ConsultPanel from "./ConsultPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

// 실제 서버 응답 모양(2026-11-26, /api/character/{name}/consult)
const build = (starforce, delta, over = {}) => ({
  starforce, delta_pct: delta,
  armor: { label: "에테르넬 7", delta_pct: 22.67 }, accessory: { label: "칠흑 6 · 보스 장신구 2 · 광휘 3", delta_pct: 49.51 },
  pieces: [],
  buy: [{ slot: "귀고리", name: "커맨더 포스 이어링", starforce, group: "장신구", set: "칠흑의 보스 세트", level: 200,
          match_cost: 2866720000, match_text: "28억 6672만", match_parts: { 잠재: { cost: 1224980000, text: "12억 2498만" }, 에디: { cost: 1641740000, text: "16억 4174만" } } },
        { slot: "반지1", name: "근원의 속삭임", starforce, group: "장신구", set: "광휘의 보스 세트", level: 250,
          match_cost: null, match_text: null, match_parts: { 잠재: null, 에디: { cost: 0, text: "0" } } }],
  match_cost: 2866720000, match_cost_text: "28억 6672만", match_unknown: 1,
  raise: [{ slot: "모자", name: "에테르넬 메이지햇", from_star: 18, starforce, cost: 56362620000, cost_text: "563억 6262만", destroys: 1.2, group: "방어구" }],
  raise_cost: 56362620000, raise_cost_text: "563억 6262만",
  set_change: [{ set: "칠흑의 보스 세트", before: 0, after: 6, lost: [], gained: ["공격력 +10, 마력 +10, 보스 몬스터 데미지 +10%"] },
               { set: "여명의 보스 세트", before: 3, after: 0, lost: ["올스탯 +10, 최대 HP +250, 공격력 +10, 마력 +10"], gained: [] }],
  ...over,
});
const DATA = { evaluation_setting: { equipment: 2 }, boss: { defense: 300 }, note: "세팅 전체를 한 번에 낀 보스 실딜이에요.",
               builds: [build(17, 13.94, { raise: [], raise_cost: 0, raise_cost_text: null }), build(18, 20.07), build(21, 60.77), build(22, 77.24)] };
const ok = (body) => ({ ok: true, status: 200, json: async () => body });

describe("목표 세팅 컨설팅", () => {
  it("성마다 세팅 전체의 실딜을 보여 주고, 기본은 22성 — 살 템·강화할 템·세트 효과 변화가 나온다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    const tabs = await screen.findByRole("tablist", { name: "목표 스타포스" });
    expect(String(f.mock.calls[0][0])).toContain("/consult?boss_defense=300");
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["17성 +13.9%", "18성 +20.1%", "21성 +60.8%", "22성 +77.2%"]);
    expect(within(tabs).getByRole("tab", { name: /22성/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("22성 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "살 템" })).toBeNull();           // 처음엔 결론만 — 목록은 눌러서 편다
    fireEvent.click(screen.getByRole("button", { name: "살 템 2개 · 강화할 템 1개 보기" }));
    const buy = screen.getByRole("list", { name: "살 템" });
    expect(within(buy).getAllByRole("listitem")).toHaveLength(2);
    expect(buy).toHaveTextContent("커맨더 포스 이어링 22성 · 칠흑");
    expect(screen.getByRole("list", { name: "강화할 템" })).toHaveTextContent("에테르넬 메이지햇 18→22성563억 6262만");
    const sets = screen.getByRole("list", { name: "세트 효과 변화" });
    expect(sets).toHaveTextContent("칠흑의 보스 세트 0→6개 · 새로 켜지는 효과: 공격력 +10, 마력 +10, 보스 몬스터 데미지 +10%");
    expect(sets).toHaveTextContent("여명의 보스 세트 3→0개 · 사라지는 효과: 올스탯 +10, 최대 HP +250, 공격력 +10, 마력 +10");
  });

  it("시세를 넣으면 필요한 메소를 합치고, 다 넣으면 1억 메소당 효율까지 계산한다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    await screen.findByRole("tablist", { name: "목표 스타포스" });
    fireEvent.click(screen.getByRole("button", { name: /보기$/ }));
    const total = () => document.querySelector(".consult-total").textContent;
    expect(total()).toContain("필요한 메소 563억 6262만");                       // 강화 비용만(시세 없음)
    expect(total()).toContain("시세를 안 넣은 템 2개");
    fireEvent.change(screen.getByLabelText("커맨더 포스 이어링 시세"), { target: { value: "30억" } });
    expect(total()).toContain("필요한 메소 593억 6262만");
    expect(total()).toContain("시세를 안 넣은 템 1개");
    fireEvent.change(screen.getByLabelText("근원의 속삭임 시세"), { target: { value: "406억 3738만" } });
    expect(total()).toContain("필요한 메소 1000억");
    expect(total()).toContain("1억 메소당 +0.077%");                             // 77.24% ÷ 1000억
    // 2026-11-26 사용자 결정: '잠재 없는 템만'과 '잠재까지 맞추면'을 같이 보여 준다(큐브를 처음부터 돌리는 평균 = 위쪽 한계)
    expect(total()).toContain("잠재·에디까지 지금 수준으로 큐브로 맞추면 평균 28억 6672만이 더 들어요");
    expect(total()).toContain("합계 1028억 6672만");
    expect(total()).toContain("계산하지 못한 템 1개는 빠져 있어요");
    const buy = screen.getByRole("list", { name: "살 템" });
    expect(buy).toHaveTextContent("잠재·에디까지 맞추면 평균 +28억 6672만");
    expect(buy).toHaveTextContent("잠재 맞추는 비용은 계산하지 못했어요");
  });

  it("가진 메소를 넣으면 장신구만 · 방어구만 · 둘 다 중 어디까지 되는지 알려 준다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    await screen.findByRole("tablist", { name: "목표 스타포스" });
    fireEvent.click(screen.getByRole("button", { name: /보기$/ }));
    const rows = () => within(screen.getByRole("table", { name: "나눠서 한다면" })).getAllByRole("row").slice(1).map((r) => r.textContent);
    // 메소를 안 넣었을 때: 아는 비용(강화 평균)과 시세가 필요한 템 수
    expect(rows()).toEqual(["장신구만+49.5%강화 0 + 살 템 2개 시세", "방어구만+22.7%563억 6262만", "둘 다+77.2%강화 563억 6262만 + 살 템 2개 시세"]);
    fireEvent.change(screen.getByLabelText("컨설팅에 쓸 메소"), { target: { value: "600억" } });
    expect(rows()).toEqual(["장신구만+49.5%살 템 2개에 600억까지 쓸 수 있어요", "방어구만+22.7%돼요 · 36억 3738만 남아요",
                            "둘 다+77.2%살 템 2개에 36억 3738만까지 쓸 수 있어요"]);
    fireEvent.change(screen.getByLabelText("컨설팅에 쓸 메소"), { target: { value: "100억" } });
    expect(rows()[1]).toBe("방어구만+22.7%463억 6262만 모자라요");
    fireEvent.change(screen.getByLabelText("커맨더 포스 이어링 시세"), { target: { value: "30억" } });
    fireEvent.change(screen.getByLabelText("근원의 속삭임 시세"), { target: { value: "50억" } });
    expect(rows()[0]).toBe("장신구만+49.5%돼요 · 20억 남아요");
  });

  it("성을 바꾸면 그 성의 세팅으로 바뀐다(17성은 강화할 템이 없다)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    fireEvent.click(await screen.findByRole("tab", { name: /17성/ }));
    expect(screen.getByText("17성 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "살 템 2개 · 강화할 템 0개 보기" }));
    expect(screen.queryByRole("list", { name: "강화할 템" })).toBeNull();
    expect(document.querySelector(".consult-total").textContent).toContain("시세를 넣으면");
  });

  it("잠재 목표를 고르면 그 잠재를 낀 실딜과, 큐브 비용이 들어간 합계를 보여 준다", async () => {
    // 실제 서버 응답 모양(2026-11-26): 성 × 잠재 목표, 각 줄에 potential·potential_label·cube
    const same = (st, d) => build(st, d, { potential: "same", potential_label: "지금 그대로", cube: [], cube_cost: 0, cube_cost_text: null, cube_unknown: 0 });
    const three = (st, d) => build(st, d, {
      potential: "legend3", potential_label: "레전드리 3줄", match_cost: 4000000000, match_cost_text: "40억", match_unknown: 0,
      buy: [{ slot: "귀고리", name: "커맨더 포스 이어링", starforce: st, group: "장신구", set: "칠흑의 보스 세트", level: 200,
              target: ["INT +12%", "INT +9%", "INT +9%"], match_cost: 4000000000, match_text: "40억",
              goal: { gain_pct: 2.5, cost: 2358260000, per_100m: 0.106, cost_text: "23억 5826만" },
              match_parts: { 잠재: { cost: 2358260000, text: "23억 5826만" }, 에디: { cost: 1641740000, text: "16억 4174만" } } }],
      cube: [{ slot: "장갑", name: "에테르넬 메이지글러브", group: "방어구", from_grade: "유니크", target: ["크리티컬 데미지 +8%", "INT +10%", "INT +10%"],
               cost: 11560000000, cost_text: "115억 6000만", gain_pct: 1.2, per_100m: 0.0104 }],
      cube_cost: 11560000000, cube_cost_text: "115억 6000만", cube_unknown: 0,
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...DATA, builds: [same(21, 60.77), three(21, 90.5), same(22, 77.24), three(22, 110.31)] }));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    const stars = await screen.findByRole("tablist", { name: "목표 스타포스" });
    const pots = screen.getByRole("tablist", { name: "잠재 목표" });
    expect(within(stars).getAllByRole("tab").map((t) => t.textContent)).toEqual(["21성 +60.8%", "22성 +77.2%"]);   // 기본은 지금 그대로
    expect(within(pots).getAllByRole("tab").map((t) => t.textContent)).toEqual(["지금 그대로 +77.2%", "레전드리 3줄 +110.3%"]);
    expect(within(pots).getByRole("tab", { name: /지금 그대로/ })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(within(pots).getByRole("tab", { name: /레전드리 3줄/ }));
    expect(within(stars).getAllByRole("tab").map((t) => t.textContent)).toEqual(["21성 +90.5%", "22성 +110.3%"]);
    expect(screen.getByText("22성 · 잠재 레전드리 3줄 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "살 템 1개 · 강화할 템 1개 · 잠재 올릴 템 1개 보기" }));
    expect(screen.getByRole("list", { name: "살 템" })).toHaveTextContent("목표 잠재 INT +12% · INT +9% · INT +9% — 에디(지금 수준)까지 합치면 평균 40억");
    expect(screen.getByRole("list", { name: "잠재 올릴 템" })).toHaveTextContent("에테르넬 메이지글러브 유니크 → 레전드리보스 실딜 +1.2% · 100억당 +1.04%목표 잠재 크리티컬 데미지 +8% · INT +10% · INT +10%115억 6000만");
    const total = () => document.querySelector(".consult-total").textContent;
    // 강화 563억 6262만 + 큐브(살 템 40억 + 지금 템 115억 6000만) = 719억 2262만
    expect(total()).toContain("필요한 메소 719억 2262만");
    expect(total()).toContain("잠재를 레전드리 3줄로 맞추는 큐브 평균 155억 6000만이 들어 있어요");
    expect(total()).toContain("에디·추옵은 지금 그대로로 봤어요");
    const rows = within(screen.getByRole("table", { name: "나눠서 한다면" })).getAllByRole("row").slice(1).map((r) => r.textContent);
    expect(rows).toEqual(["장신구만+49.5%강화·큐브 40억 + 살 템 1개 시세", "방어구만+22.7%679억 2262만", "둘 다+110.3%강화·큐브 719억 2262만 + 살 템 1개 시세"]);
    // 칸마다 그 칸 잠재 목표의 몫과 1억당 효율 — 효율이 낮은 칸(장갑: 115억에 +1.2%)은 체크를 풀어 뺀다
    expect(screen.getByRole("list", { name: "살 템" })).toHaveTextContent("잠재를 목표로 +2.5% · 100억당 +10.60% · 큐브 평균 23억 5826만");
    expect(screen.getByRole("list", { name: "잠재 올릴 템" })).toHaveTextContent("보스 실딜 +1.2% · 100억당 +1.04%");
    fireEvent.click(screen.getByLabelText("에테르넬 메이지글러브 잠재 목표 넣기"));
    expect(total()).toContain("필요한 메소 603억 6262만");                       // 719억 2262만 − 115억 6000만
    expect(total()).toContain("잠재 목표에서 뺀 칸 1개는 지금 잠재 그대로예요");
    expect(total()).toContain("큐브 평균 40억이 들어 있어요 (살 템 40억 · 지금 템 0)");   // 뺀 칸은 안쪽 내역에서도 빠진다
    expect(document.querySelector(".consult-gain").textContent).toBe("약 +109.1%");   // 110.31 − 1.2
    const after = within(screen.getByRole("table", { name: "나눠서 한다면" })).getAllByRole("row").slice(1).map((r) => r.textContent);
    expect(after).toEqual(["장신구만약 +49.5%강화·큐브 40억 + 살 템 1개 시세", "방어구만약 +21.5%563억 6262만", "둘 다약 +109.1%강화·큐브 603억 6262만 + 살 템 1개 시세"]);
    fireEvent.click(screen.getByLabelText("에테르넬 메이지글러브 잠재 목표 넣기"));
    expect(document.querySelector(".consult-gain").textContent).toBe("+110.3%");
  });

  it("에디 목표를 고르면 에디까지 얹은 실딜과 칸별 목표·큐브 비용을 보여 주고, 칸을 뺄 수 있다", async () => {
    // 실제 서버 응답 모양(2026-11-26): 세팅마다 additional_options(에디까지 얹은 실딜·칸별 목표)
    const opts = (d) => [{
      key: "legend2", label: "레전드리 2줄", delta_pct: d + 10, armor_delta_pct: 26.67, accessory_delta_pct: 55.01, cost: 59000000000,
      cost_text: "590억", unknown: 0,
      slots: [{ slot: "귀고리", name: "커맨더 포스 이어링", group: "장신구", kept: false, from_grade: null, target: ["INT +8%", "INT +6%"],
                cost: 28100000000, cost_text: "281억", gain_pct: 6, per_100m: 0.02131 },
              { slot: "모자", name: "에테르넬 메이지햇", group: "방어구", kept: true, from_grade: "에픽", target: ["INT +9%", "INT +7%"],
                cost: 30900000000, cost_text: "309억", gain_pct: 4, per_100m: 0.01294 }],
    }];
    const same = (st, d) => build(st, d, { potential: "same", potential_label: "지금 그대로", cube: [], cube_cost: 0, cube_cost_text: null, cube_unknown: 0,
                                           match_unknown: 0, additional_options: opts(d),
                                           buy: [{ slot: "귀고리", name: "커맨더 포스 이어링", starforce: st, group: "장신구", set: "칠흑의 보스 세트", level: 200,
                                                   target: null, goal: null, match_cost: 2866720000, match_text: "28억 6672만",
                                                   match_parts: { 잠재: { cost: 1224980000, text: "12억 2498만" }, 에디: { cost: 1641740000, text: "16억 4174만" } } }] });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...DATA, builds: [same(21, 60.77), same(22, 77.24)] }));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    const tabs = await screen.findByRole("tablist", { name: "에디 목표" });
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["지금 그대로 +77.2%", "레전드리 2줄 +87.2%"]);
    fireEvent.click(within(tabs).getByRole("tab", { name: /레전드리 2줄/ }));
    expect(within(screen.getByRole("tablist", { name: "목표 스타포스" })).getAllByRole("tab").map((t) => t.textContent)).toEqual(["21성 +70.8%", "22성 +87.2%"]);
    expect(screen.getByText("22성 · 에디 레전드리 2줄 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    expect(document.querySelector(".consult-headline").textContent).toContain("방어구 에테르넬 7 +26.7% · 장신구 칠흑 6 · 보스 장신구 2 · 광휘 3 +55.0%");
    fireEvent.click(screen.getByRole("button", { name: "살 템 1개 · 강화할 템 1개 · 에디 올릴 템 2개 보기" }));
    const list = screen.getByRole("list", { name: "에디 올릴 템" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "귀고리커맨더 포스 이어링 살 템 · 레어에서보스 실딜 +6.0% · 100억당 +2.13%목표 에디 INT +8% · INT +6%281억",
      "모자에테르넬 메이지햇 에픽 → 레전드리보스 실딜 +4.0% · 100억당 +1.29%목표 에디 INT +9% · INT +7%309억"]);
    const total = () => document.querySelector(".consult-total").textContent;
    // 강화 563억 6262만 + 살 템(잠재 지금 수준 12억 2498만 + 에디 목표 281억) + 지금 템 에디 309억 = 1165억 8760만
    expect(total()).toContain("필요한 메소 1165억 8760만");
    expect(total()).toContain("에디를 레전드리 2줄로 맞추는 큐브 평균 602억 2498만이 들어 있어요 (살 템 293억 2498만 · 지금 템 309억)");
    expect(screen.getByRole("list", { name: "살 템" })).toHaveTextContent("잠재를 지금 수준으로 맞추면 평균 +12억 2498만");
    // 살 템의 에디 목표를 빼면: 에디는 지금 수준으로 맞추는 비용(16억 4174만)으로 돌아간다
    fireEvent.click(screen.getByLabelText("커맨더 포스 이어링 에디 목표 넣기"));
    expect(total()).toContain("필요한 메소 901억 2934만");
    expect(document.querySelector(".consult-gain").textContent).toBe("약 +81.2%");
    expect(screen.getByRole("list", { name: "살 템" })).toHaveTextContent("잠재·에디까지 맞추면 평균 +28억 6672만");
    fireEvent.click(screen.getByLabelText("에테르넬 메이지햇 에디 목표 넣기"));
    expect(total()).toContain("필요한 메소 592억 2934만");
    const rows = within(screen.getByRole("table", { name: "나눠서 한다면" })).getAllByRole("row").slice(1).map((r) => r.textContent);
    expect(rows).toEqual(["장신구만약 +49.0%강화·큐브 28억 6672만 + 살 템 1개 시세", "방어구만약 +22.7%563억 6262만", "둘 다약 +77.2%강화·큐브 592억 2934만 + 살 템 1개 시세"]);
  });
});
