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
