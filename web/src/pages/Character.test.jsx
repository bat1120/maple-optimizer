import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
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

function mockApi() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (String(url).includes("/settings")) return ok(SETTINGS);
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

  it("세팅 순위: 1위 메달", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    const t = await screen.findByRole("table", { name: "보스 세팅 순위" });
    expect(t.querySelector(".medal-1")).not.toBeNull();
  });

  it("탭: 위쪽 탭을 누르면 주소가 바뀌고, 업그레이드 탭은 들어가자마자 로드맵을 불러온다", async () => {
    const f = mockApi();
    const { rerender } = render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.getByRole("tab", { name: "업그레이드" })).toHaveAttribute("href", `#/c/${encodeURIComponent("내신부레테")}?tab=upgrade`);
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />); });
    expect(f.mock.calls.some((c) => String(c[0]).includes("/roadmap"))).toBe(true);
    expect(screen.queryByRole("button", { name: "경매장 시세 갱신" })).toBeNull();   // 공개 화면에선 관리자 기능 숨김
  });

  it("공개 화면에서는 화면 분석·AI 상담이 없다", async () => {
    mockApi();
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.queryByRole("button", { name: "경매장 화면 연결" })).toBeNull();
    expect(screen.queryByText(/관리자 로그인/)).toBeNull();
  });

  it("오류는 카드 안에 서버 문구 그대로 + 다시 시도", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ code: "NOT_FOUND", message: "캐릭터를 찾을 수 없어요." }) });
    render(<Character route={{ page: "character", name: "없는캐릭", tab: "summary" }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("캐릭터를 찾을 수 없어요.");
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
    expect(await screen.findByRole("heading", { name: "경매장 화면 평가" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "장비창 채점" })).toBeNull();
    expect(screen.getByText(/PC에서 열면 경매장 화면을 바로 평가/)).toBeInTheDocument();
  });

  it("탭마다 할 수 있는 것 한 줄과 사용 방법이 붙는다", async () => {
    mockApi();
    const { rerender } = render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    await screen.findByRole("heading", { name: "내신부레테" });
    expect(screen.getByText(/프리셋 조합별 보스 실딜 순위/)).toBeInTheDocument();
    expect(screen.getAllByText("사용 방법").length).toBeGreaterThan(0);
    expect(screen.getByText(/칸을 누르면 잠재·에디 옵션이 열려요/)).toBeInTheDocument();
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "upgrade" }} />); });
    expect(screen.getByText(/무엇을 바꾸면 보스 실딜이 오르는지/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "업그레이드 경로 비교" })).toBeInTheDocument();
    await act(async () => { rerender(<Character route={{ page: "character", name: "내신부레테", tab: "calc" }} />); });
    expect(screen.getByText(/스타포스·큐브 비용과 매물 vs 직작/)).toBeInTheDocument();
  });

  it("장비가 없으면 빈 상태 안내", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => (String(url).includes("/settings") ? ok(SETTINGS) : ok({ ...SUMMARY, equipment_presets: {} })));
    render(<Character route={{ page: "character", name: "내신부레테", tab: "summary" }} />);
    expect(await screen.findByText("불러온 장비가 없어요")).toBeInTheDocument();
  });
});
