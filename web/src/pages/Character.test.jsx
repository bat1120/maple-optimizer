import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import Character from "./Character.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); window.location.hash = ""; });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const item = (slot, name, extra = {}) => ({ slot, name, starforce: 22, icon: null, potential_grade: "레전드리",
  additional_grade: "에픽", potentials: ["INT +12%", "INT +9%"], additional: ["마력 +10"], level: 250,
  special_ring_level: 0, ...extra });
const SUMMARY = {
  character_class: "아크메이지(불,독)", level: 288, date: null,
  active_setting: { equipment: 2, hyper: 1, ability: 1 },
  stat_attack: { engine: 123456789, api: 123400000 }, combat_power_reference: 98765432,
  final: {}, excluded: [],
  profile: { name: "내신부레테", world: "스카니아", guild: "길드", image: null, class_level: "6", date_create: null },
  equipment_presets: {
    "1": [item("모자", "도전자의 모자"), item("장갑", "에테르넬 메이지글러브", { potential_grade: "유니크", starforce: 17 })],
    "2": [item("모자", "프리셋2 모자"), item("반지3", "컨티뉴어스 링", { potential_grade: null, starforce: 0, special_ring_level: 4 })],
  },
};
const SETTINGS = { ranking: [
  { setting: { equipment: 2, hyper: 1, ability: 1 }, relative_to_active: 1, main_stat_vs_active: 0 },
  { setting: { equipment: 1, hyper: 1, ability: 1 }, relative_to_active: 0.97, main_stat_vs_active: -1200 },
] };

// 업그레이드 계획(2026-11-23 계획 하나): 추옵 1줄 + 경매장에서 살 수 있는 큐브 1줄
const CUBE = { slot: "엠블렘", path: "큐브", kind: "에디", name: "골드 서버너 엠블렘", grade: "레전드리", lines_good: 2, route: "경매장",
  target: ["마력 +12%", "마력 +9%"], delta_pct: 5.55, per_100m: 0.022, cost_text: "253억 8269만", total_cost_text: "254억 2664만", gain_pct_after: 5.7 };
const PLAN = { evaluation_setting: { equipment: 2, hyper: 3, ability: 2 }, budget_text: null, spent_text: "254억 2664만", left_text: null, gain_pct: 5.7,
  next_step: null, note: "비용은 평균 기대값이에요.", steps: [
    { slot: "귀고리", path: "추옵", name: "에스텔라 이어링", delta_pct: 0.156, per_100m: 0.354, cost_text: "4395만", total_cost_text: "4395만", gain_pct_after: 0.156 },
    CUBE] };

function mockApi() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (String(url).includes("/settings")) return ok(SETTINGS);
    if (String(url).includes("/budget-roadmap")) return ok(PLAN);
    if (String(url).includes("/roadmap")) return ok({ evaluation_setting: SUMMARY.active_setting, note: "", value_ranking: [], slots: [] });
    if (String(url).includes("/paths")) return ok({ evaluation_setting: SUMMARY.active_setting, observed_count: 0, note: "", all: [] });
    if (String(url).includes("/recommend")) return ok({ evaluation_setting: SUMMARY.active_setting, note: "", recommendations: [] });
    return ok(SUMMARY);
  });
}

describe("character page", () => {
  it("조회 중에는 뼈대 화면, 다 오면 프로필 카드와 큰 숫자", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    expect(screen.getByTestId("skeleton")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "내신부레테" })).toBeInTheDocument();
    expect(screen.getByText(/스카니아/)).toBeInTheDocument();
    expect(screen.getByText(/Lv\.288/)).toBeInTheDocument();
    expect(screen.queryByTestId("skeleton")).toBeNull();
    expect(JSON.parse(localStorage.getItem("maple-optimizer:recent"))).toEqual(["내신부레테"]);
  });

  it("장비창: 지금 프리셋(2)부터, 등급색·성 배지·특수 반지 레벨, 프리셋을 바꾸면 템이 바뀐다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    const hat = await screen.findByRole("button", { name: /모자 프리셋2 모자/ });
    expect(hat.className).toMatch(/grade-legendary/);
    expect(hat).toHaveTextContent("22");
    expect(screen.getByRole("button", { name: /반지3 컨티뉴어스 링/ })).toHaveTextContent("Lv.4");
    fireEvent.click(screen.getByRole("button", { name: "프리셋 1" }));
    expect(screen.getByRole("button", { name: /장갑 에테르넬 메이지글러브/ }).className).toMatch(/grade-unique/);
    expect(screen.queryByText("프리셋2 모자")).toBeNull();
  });

  it("장비 칸을 누르면 잠재·에디 줄 상세가 열린다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    fireEvent.click(await screen.findByRole("button", { name: /모자 프리셋2 모자/ }));
    const d = screen.getByRole("region", { name: "프리셋2 모자 상세" });
    expect(d).toHaveTextContent("INT +12%");
    expect(d).toHaveTextContent("마력 +10");
  });

  it("상세 툴팁은 강화된 별만 5개씩 묶어 보여 준다(빈 별은 그리지 않는다)", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    fireEvent.click(await screen.findByRole("button", { name: /모자 프리셋2 모자/ }));
    const d = screen.getByRole("region", { name: "프리셋2 모자 상세" });
    const groups = [...d.querySelectorAll(".tip-stars [aria-hidden]")].map((s) => s.textContent);
    expect(groups).toEqual(["★★★★★", "★★★★★", "★★★★★", "★★★★★", "★★"]);
    expect(d).toHaveTextContent("스타포스 22성");
  });

  it("장비 [목록] 보기는 부위·이름·잠재 줄을 카드로 보여 준다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "목록" }));
    const list = screen.getByRole("list", { name: "장비 목록" });
    const hat = within(list).getAllByRole("listitem").find((li) => li.textContent.includes("프리셋2 모자"));
    expect(hat).toHaveTextContent("모자");
    expect(hat).toHaveTextContent("INT +12%");
    fireEvent.click(screen.getByRole("button", { name: "장비창" }));
    expect(screen.queryByRole("list", { name: "장비 목록" })).toBeNull();
  });

  it("요약 탭 위에 '업그레이드 1순위' 한 줄 = 업그레이드 계획의 첫 줄 — 누르면 업그레이드 탭", async () => {
    const f = mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    const pick = await screen.findByRole("region", { name: "업그레이드 1순위" });
    await within(pick).findByText("귀고리 추옵 재설정");
    expect(pick).toHaveTextContent("1억 메소당 +0.354%");
    expect(pick).toHaveTextContent("평균 4395만");
    expect(f.mock.calls.some((c) => /budget-roadmap\?.*steps=1/.test(String(c[0])))).toBe(true);   // 첫 줄만 받는다
    expect(within(pick).getByRole("link", { name: /내 업그레이드 계획 보기/ })).toHaveAttribute("href", `#/c/${encodeURIComponent("내신부레테")}?tab=upgrade`);
  });

  it("세팅 순위: 1위 메달", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    const t = await screen.findByRole("table", { name: "보스 세팅 순위" });
    expect(t.querySelector(".medal-1")).not.toBeNull();
  });

  it("탭: 위쪽 탭을 누르면 주소가 바뀌고, 업그레이드 탭은 들어가자마자 계획만 불러온다", async () => {
    const f = mockApi();
    const { rerender } = render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.getByRole("tab", { name: "업그레이드" })).toHaveAttribute("href", `#/c/${encodeURIComponent("내신부레테")}?tab=upgrade`);
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />); });
    // 업그레이드 탭: 계획만 바로 계산, 나머지는 펼칠 때(2026-10-17 점검: 들어가자마자 요청이 몰려 분당 한도)
    const called = (k) => f.mock.calls.some((c) => String(c[0]).includes(k));
    expect(called("/budget-roadmap?")).toBe(true);
    expect(called("/roadmap?")).toBe(false);   // 잠재·에디만 본 순위는 '다른 기준으로 보기' 아래에서 펼칠 때
    expect(called("/paths")).toBe(false);
    expect(called("/recommend")).toBe(false);
    const paths = screen.getByText("방법별 비교 — 구매·직작·큐브·강화").closest("details");
    await act(async () => { paths.open = true; fireEvent(paths, new Event("toggle")); });
    expect(called("/paths")).toBe(true);
    expect(screen.queryByRole("button", { name: "경매장 시세 갱신" })).toBeNull();   // 공개 화면에선 관리자 기능 숨김
  });

  it("공개 화면 요약 탭에는 화면 분석 버튼·관리자 로그인이 없다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.queryByRole("button", { name: "경매장 화면 연결" })).toBeNull();
    expect(screen.queryByText(/관리자 로그인/)).toBeNull();
  });

  // 2026-10-11 디자인 심사: 닉네임을 못 찾으면 같은 이름 '다시 시도'는 막다른 길 → 닉네임이 채워진 검색창으로 고쳐 찾게
  it("닉네임을 못 찾으면(404) 그 닉네임이 채워진 검색창과 [다시 검색], 아래 탭 막대는 숨긴다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 404, json: async () => ({ code: "NOT_FOUND", message: "캐릭터를 찾을 수 없어요." }) });
    const { container } = render(<Character route={{ page: "character", name: "없는캐릭", tab: "summary" }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("「없는캐릭」 캐릭터를 찾지 못했어요");
    expect(screen.getByRole("searchbox", { name: "캐릭터 닉네임 다시 검색" })).toHaveValue("없는캐릭");
    expect(screen.getByRole("button", { name: "다시 검색" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();
    expect(container.querySelector(".bottom-tabs")).toBeNull();
  });

  it("서버 오류는 카드 안에 서버 문구 그대로 + 다시 시도", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ code: "NEXON_DOWN", message: "넥슨 Open API가 응답하지 않아요." }) });
    render(<Character route={{ page: "character", name: "없는캐릭", tab: "summary" }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("넥슨 Open API가 응답하지 않아요.");
    f.mockImplementation(async (url) => (String(url).includes("/settings") ? ok(SETTINGS) : ok(SUMMARY)));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "다시 시도" })); });
    expect(await screen.findByRole("heading", { name: "내신부레테" })).toBeInTheDocument();
  });

  it("이미지가 없으면 직업 첫 글자 아바타", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.getByTestId("avatar-fallback")).toHaveTextContent("아");
  });

  it("업그레이드 탭: PC용 경매장 화면 평가(일반 유저 모드)와 휴대폰 안내", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />);
    const watch = (await screen.findByText("3·4단계 · 검색 화면을 공유하면 여기에 매물별 실딜이 나와요 (PC)")).closest("details");
    expect(watch).not.toHaveAttribute("open");
    expect(screen.queryByRole("heading", { name: "경매장 화면 평가" })).toBeNull();   // 펼치기 전엔 그리지 않는다
    await act(async () => { watch.open = true; fireEvent(watch, new Event("toggle")); });
    expect(screen.getByRole("heading", { name: "경매장 화면 평가" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "장비창 채점" })).toBeNull();
    expect(screen.getByText(/3·4단계는 PC에서 돼요/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "내 업그레이드 계획" })).toBeInTheDocument();
    expect(screen.queryByText(/무엇을 바꾸면 보스 실딜이 오르는지/)).toBeNull();   // 업그레이드 탭은 단계 줄이 안내 띠를 대신한다
    expect(screen.queryByRole("heading", { name: "잠재·에디 가격 대비 순위" })).toBeNull();   // 추천 목록은 계획 하나뿐
    // 2026-11-23: 흐름 4단계와 '내 메소로 어디까지'가 순위보다 위, 화면 공유는 '고급 도구'가 아니라 순위 바로 아래
    expect(within(screen.getByRole("list", { name: "이렇게 진행해요" })).getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByLabelText("가진 메소")).toBeInTheDocument();
    expect(screen.queryByText("고급 도구")).toBeNull();
  });

  it("탭마다 할 수 있는 것 한 줄과 사용 방법이 붙는다", async () => {
    mockApi();
    const { rerender } = render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.getByText(/프리셋 조합별 보스 실딜 순위/)).toBeInTheDocument();
    expect(screen.getAllByText("사용 방법").length).toBeGreaterThan(0);
    expect(screen.getByText(/칸을 누르면 잠재·에디 옵션이 열려요/)).toBeInTheDocument();
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />); });
    expect(screen.getByRole("list", { name: "이렇게 진행해요" })).toBeInTheDocument();   // 업그레이드 탭 안내 = 단계 줄(2026-11-23)
    expect(screen.getByText("방법별 비교 — 구매·직작·큐브·강화")).toBeInTheDocument();
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "calc" }} />); });
    expect(screen.getByText(/스타포스·큐브 비용과 매물 vs 직작/)).toBeInTheDocument();
  });

  // 2026-10-17 사용자: 처음 들어가면 보스 최적 세팅으로 보여 준다(지금 착용은 작게 같이)
  it("기본은 보스 세팅: 프로필 세팅, 주요 스탯, 장비창 프리셋이 보스 1위 조합 기준", async () => {
    const best = { setting: { equipment: 1, hyper: 3, ability: 2 }, stat_attack: 222000000,
                   final: { ...SUMMARY.final, boss: 333 } };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      if (String(url).includes("/settings")) return ok({ ...SETTINGS, best });
      if (String(url).includes("/roadmap")) return ok({ evaluation_setting: best.setting, note: "", value_ranking: [], slots: [] });
      return ok(SUMMARY);
    });
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    expect(await screen.findByText("보스 세팅")).toBeInTheDocument();
    expect(screen.getByText("장비 1 · 하이퍼 3 · 어빌 2")).toBeInTheDocument();
    expect(screen.getByText(/지금 착용: 장비 2 · 하이퍼 1 · 어빌 1/)).toBeInTheDocument();
    // 큰 숫자는 넥슨이 준 전투력 그대로(2026-11-07 사용자) — 스탯 공격력은 첫 화면에 없다
    expect(screen.getByText("전투력(인게임 기록)")).toBeInTheDocument();
    expect(screen.getByText("9,876만")).toBeInTheDocument();
    expect(screen.queryByText(/스탯 공격력/)).toBeNull();
    expect(screen.queryByText("2억 2,200만")).toBeNull();
    expect(screen.getByText("333%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "프리셋 1" })).toHaveAttribute("aria-pressed", "true");
  });

  // 2026-11-23 계획 하나: 계획의 경매장 줄 → [경매장에서 찾기](2단계 조건) → [검색 화면 공유](3단계) → 그 줄 바로 아래 공유 칸
  it("계획의 경매장 줄에서 공유를 누르면 화면 공유 평가 칸이 열리고 찾는 조건을 보여 준다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />);
    const flow = () => screen.getByRole("list", { name: "이렇게 진행해요" }).querySelector("[aria-current=step]");
    const watch = (await screen.findByText("3·4단계 · 검색 화면을 공유하면 여기에 매물별 실딜이 나와요 (PC)")).closest("details");
    expect(watch).not.toHaveAttribute("open");
    expect(flow()).toHaveTextContent("추천 확인");
    fireEvent.click(screen.getByRole("button", { name: "경매장에서 찾기" }));
    expect(flow()).toHaveTextContent("경매장에서 검색");
    fireEvent.click(screen.getByRole("button", { name: "화면 공유 칸 열기" }));
    expect(watch).toHaveAttribute("open");
    expect(flow()).toHaveTextContent("검색 화면 공유");
    const note = screen.getByRole("note", { name: "찾는 조건" });
    expect(note).toHaveTextContent("부위엠블렘");
    expect(note).toHaveTextContent("1줄마력 +12% 이상");
    // 2026-11-23 운영에서 발견: 계획을 다시 계산해도 진행 순서가 3단계에 머물렀다 → 다시 계산하면 공유 칸을 접고 1단계로
    fireEvent.click(screen.getByRole("button", { name: "50억" }));
    await waitFor(() => expect(flow()).toHaveTextContent("추천 확인"));
    expect(watch).not.toHaveAttribute("open");
  });

  it("장비가 없으면 빈 상태 안내", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => (String(url).includes("/settings") ? ok(SETTINGS) : ok({ ...SUMMARY, equipment_presets: {} })));
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    expect(await screen.findByText("불러온 장비가 없어요")).toBeInTheDocument();
  });

  // 2026-10-11 디자인 심사 2회차: 1위가 셋(가격 대비·검색 추천·경로 비교)으로 갈림 → 가격 대비 순위만 펼치고 나머지는 접는다
  it("업그레이드 탭은 계획만 펼치고, 잠재·에디 순위·검색 추천·경로 비교·목표 배율은 접어 둔다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />);
    expect((await screen.findByRole("heading", { name: "내 업그레이드 계획" })).closest("details")).toBeNull();
    for (const t of ["잠재·에디만 가격 대비 순위로 보기", "실딜만 보고 고르기 — 가격은 안 봐요", "방법별 비교 — 구매·직작·큐브·강화", "목표 보스 배율까지의 순서"]) {
      const d = screen.getByText(t).closest("details");
      expect(d).not.toBeNull();
      expect(d).not.toHaveAttribute("open");
    }
    for (const h of ["잠재·에디 가격 대비 순위", "경매장 검색 추천", "업그레이드 경로 비교", "목표 배율 로드맵"]) {
      expect(screen.queryByRole("heading", { name: h })).toBeNull();   // 펼치기 전엔 그리지도, 계산하지도 않는다
    }
  });
});

describe("character page — AI 상담은 모두에게, 일반 사용자는 하루 횟수 제한(2026-10-17)", () => {
  const withSession = (admin) => vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (String(url).includes("/api/admin/session")) return ok({ admin });
    if (String(url).includes("/api/agent/quota")) return ok(admin ? { admin: true, limit: null, remaining: null } : { admin: false, limit: 5, remaining: 3 });
    if (String(url).includes("/settings")) return ok(SETTINGS);
    return ok(SUMMARY);
  });
  it("관리자면 탭보다 위에 AI 상담(비밀번호 없이)과 바로 물어볼 질문, 횟수 제한 표시 없음", async () => {
    withSession(true);
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    const ai = await screen.findByRole("heading", { name: "AI에게 물어보기" });
    const tabs = screen.getByRole("tablist", { name: "캐릭터 화면 탭" });
    expect(ai.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByLabelText("관리자 비밀번호")).toBeNull();
    expect(screen.getByRole("button", { name: "지금 뭐부터 올리면 돼?" })).toBeInTheDocument();
    expect(screen.queryByText(/오늘 남은 질문/)).toBeNull();
  });
  it("일반 사용자도 AI 상담을 쓰고, 오늘 남은 질문 수를 본다", async () => {
    withSession(false);
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    expect(await screen.findByRole("heading", { name: "AI에게 물어보기" })).toBeInTheDocument();
    expect(await screen.findByText(/오늘 남은 질문 3\/5회/)).toBeInTheDocument();
    expect(screen.queryByLabelText("관리자 비밀번호")).toBeNull();
  });
});

describe("character page — 방어율 입력은 멈춘 뒤에 한 번만 다시 계산(2026-10-17 점검)", () => {
  it("빠르게 여러 글자를 쳐도 세팅 순위는 한 번만 다시 부르고, 캐릭터 정보는 다시 부르지 않는다", async () => {
    const f = mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    await act(async () => { await new Promise((r) => setTimeout(r, 650)); });
    const count = (part) => f.mock.calls.filter(([u]) => String(u).includes(part)).length;
    const summaryCalls = f.mock.calls.filter(([u]) => /\/api\/character\/[^/?]+$/.test(String(u))).length;
    const settingsCalls = count("/settings");
    fireEvent.change(screen.getByRole("combobox", { name: "보스" }), { target: { value: "custom" } });
    const input = await screen.findByLabelText("보스 방어율(%)");
    for (const v of ["3", "38", "380"]) fireEvent.change(input, { target: { value: v } });
    await act(async () => { await new Promise((r) => setTimeout(r, 700)); });
    expect(count("/settings") - settingsCalls).toBeLessThanOrEqual(2);
    expect(f.mock.calls.filter(([u]) => /\/api\/character\/[^/?]+$/.test(String(u))).length).toBe(summaryCalls);
    expect(f.mock.calls.at(-1)[0]).toContain("boss_defense=380");
  });
});
