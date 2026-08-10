import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatSidebar } from "@/components/ChatSidebar";
import { initialData } from "@/lib/kanban";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  sendChatMessage: vi.fn(),
}));

const openSidebar = async () => {
  await userEvent.click(screen.getByRole("button", { name: /ask ai/i }));
};

describe("ChatSidebar", () => {
  it("starts collapsed, showing only a toggle button", () => {
    render(<ChatSidebar onBoardUpdate={vi.fn()} />);

    expect(screen.getByRole("button", { name: /ask ai/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("Chat message")).not.toBeInTheDocument();
  });

  it("sends a message, appends both messages, and applies a board update", async () => {
    const onBoardUpdate = vi.fn();
    const updatedBoard = { ...initialData };
    vi.mocked(api.sendChatMessage).mockResolvedValue({ reply: "Moved it!", board: updatedBoard });

    render(<ChatSidebar onBoardUpdate={onBoardUpdate} />);
    await openSidebar();

    await userEvent.type(screen.getByLabelText("Chat message"), "move the card to Done");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(api.sendChatMessage).toHaveBeenCalledWith("move the card to Done");
    expect(screen.getByText("move the card to Done")).toBeInTheDocument();
    expect(await screen.findByText("Moved it!")).toBeInTheDocument();
    expect(onBoardUpdate).toHaveBeenCalledWith(updatedBoard);
  });

  it("shows an error and does not call onBoardUpdate when the request fails", async () => {
    const onBoardUpdate = vi.fn();
    vi.mocked(api.sendChatMessage).mockRejectedValue(new Error("network error"));

    render(<ChatSidebar onBoardUpdate={onBoardUpdate} />);
    await openSidebar();

    await userEvent.type(screen.getByLabelText("Chat message"), "hello");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
    expect(onBoardUpdate).not.toHaveBeenCalled();
  });
});
