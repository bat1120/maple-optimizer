import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AgentPanel from "./AgentPanel.jsx";

const sseResponse = (events) => new Response(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
  { status: 200, headers: { "Content-Type": "text/event-stream" } });

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("agent panel", () => {
  it("틀린 비밀번호는 서버 메시지를 보여준다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ code: "BAD_PASSWORD", message: "비밀번호가 틀렸습니다." }), { status: 401 }));
    render(<AgentPanel />);
    fireEvent.change(screen.getByLabelText("관리자 비밀번호"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("비밀번호가 틀렸습니다.");
  });

  it("로그인 후 질문하면 도구 호출·답변·검증 안 된 숫자 경고를 스트림으로 보여준다", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(sseResponse([
        { type: "tool_call", name: "starforce_cost", input: { level: 200 } },
        { type: "tool_result", name: "starforce_cost", result: { exact_mean: 1 } },
        { type: "text", text: "평균 178억 8700만 메소예요." },
        { type: "done", unverified_numbers: ["999억"] },
      ]));
    render(<AgentPanel />);
    fireEvent.change(screen.getByLabelText("관리자 비밀번호"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    fireEvent.change(await screen.findByLabelText("질문"), { target: { value: "200제 22성 비용?" } });
    fireEvent.click(screen.getByRole("button", { name: "보내기" }));
    expect(await screen.findByText(/평균 178억 8700만 메소예요/)).toBeInTheDocument();
    expect(screen.getByText(/starforce_cost/)).toBeInTheDocument();
    expect(screen.getByText(/검증되지 않은 숫자: 999억/)).toBeInTheDocument();
    const body = JSON.parse(f.mock.calls[1][1].body);
    expect(body.messages.at(-1)).toEqual({ role: "user", content: "200제 22성 비용?" });
  });

  it("스트림 error 이벤트를 알림으로 보여준다", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(sseResponse([{ type: "error", message: "오늘 에이전트 토큰 한도를 다 썼어요." }, { type: "done", unverified_numbers: [] }]));
    render(<AgentPanel />);
    fireEvent.change(screen.getByLabelText("관리자 비밀번호"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    fireEvent.change(await screen.findByLabelText("질문"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "보내기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("토큰 한도");
  });
});

describe("agent panel with screen items", () => {
  it("화면에서 읽은 매물을 질문에 붙여 보낸다 (평가는 에이전트가 도구로 다시 한다)", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(sseResponse([{ type: "done", unverified_numbers: [] }]));
    const items = [{ signature: "s", evaluated: true, slot: "모자", delta_pct: 1, read: {
      name: "에테르넬 메이지햇", category: "모자", part: "모자", starforce: 22, total: { INT: 120 }, potentials: ["INT +12%"], price: 4.5e9 } }];
    render(<AgentPanel name="내신부레테" screenItems={items} />);
    fireEvent.change(screen.getByLabelText("관리자 비밀번호"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect(await screen.findByText(/화면 매물 1개를 함께 보내요/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("질문"), { target: { value: "경매장에서 본거 어때" } });
    fireEvent.click(screen.getByRole("button", { name: "보내기" }));
    await screen.findByText(/경매장에서 본거 어때/);
    const sent = JSON.parse(f.mock.calls[1][1].body).messages.at(-1).content;
    expect(sent).toContain("경매장에서 본거 어때");
    expect(sent).toContain("캐릭터: 내신부레테");
    expect(sent).toContain('"name":"에테르넬 메이지햇"');
    expect(sent).toContain('"price":4500000000');
    expect(sent).not.toContain("delta_pct");   // 숫자는 에이전트가 도구로 다시 계산해야 출처 검사가 된다
  });
});

describe("agent panel character context", () => {
  it("화면 매물이 없어도 조회한 캐릭터를 질문에 붙인다", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(sseResponse([{ type: "done", unverified_numbers: [] }]));
    render(<AgentPanel name="내신부레테" />);
    fireEvent.change(screen.getByLabelText("관리자 비밀번호"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    fireEvent.change(await screen.findByLabelText("질문"), { target: { value: "200억으로 뭐부터" } });
    fireEvent.click(screen.getByRole("button", { name: "보내기" }));
    await screen.findByText(/200억으로 뭐부터/);
    expect(JSON.parse(f.mock.calls[1][1].body).messages.at(-1).content).toContain("[조회한 캐릭터: 내신부레테]");
  });

  it("목록에서만 본 매물은 빼고, 가격 못 읽은 매물에는 같은 이름 목록 가격을 후보로 붙인다", async () => {
    const { withScreenItems } = await import("./AgentPanel.jsx");
    const row = (name, price) => ({ signature: name + price, evaluated: false, read: { name, total: {}, potentials: [], price } });
    const tip = { signature: "t", evaluated: true, slot: "보조무기", read: { name: "녹스 마법깃펜", category: "보조무기",
      total: { INT: 10 }, potentials: ["마력 +12%"], price: null } };
    const sent = withScreenItems("분석해줘", "내신부레테", [row("녹스 마법깃펜", 4e10), row("녹스 마법깃펜", 5e10), row("미트라", 9e9), tip]);
    const json = JSON.parse(sent.slice(sent.lastIndexOf("\n") + 1));
    expect(json).toHaveLength(1);
    expect(json[0].list_prices).toEqual([4e10, 5e10]);
  });

  it("판매 수수료를 질문에 붙인다", async () => {
    const { withScreenItems } = await import("./AgentPanel.jsx");
    expect(withScreenItems("q", "내신부레테", [], 0.03)).toContain("[경매장 판매 수수료: 3% — fee_rate 0.03]");
    expect(withScreenItems("q", "내신부레테", [])).not.toContain("수수료");
  });

  it("확인 필요 줄을 첨부 매물에 함께 보낸다", async () => {
    const { withScreenItems } = await import("./AgentPanel.jsx");
    const item = { signature: "u", evaluated: true, slot: "장갑", unverified_lines: ["HP 회복 아이템 및 회복 스킬 +30%"],
      read: { name: "글러브", category: "장갑", total: { STR: 1 }, potentials: ["HP 회복 아이템 및 회복 스킬 +30%"], price: 1 } };
    const sent = withScreenItems("q", "x", [item]);
    expect(sent).toContain('"unverified_lines":["HP 회복 아이템 및 회복 스킬 +30%"]');
  });
});
