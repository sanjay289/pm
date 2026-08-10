import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchBoard: vi.fn(),
  renameColumn: vi.fn(),
  createCard: vi.fn(),
  moveCard: vi.fn(),
  deleteCard: vi.fn(),
  sendChatMessage: vi.fn(),
  UnauthorizedError: class UnauthorizedError extends Error {},
}));

const cloneBoard = () => JSON.parse(JSON.stringify(initialData));

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.mocked(api.fetchBoard).mockResolvedValue(cloneBoard());
    vi.mocked(api.renameColumn).mockResolvedValue(cloneBoard());
    vi.mocked(api.createCard).mockResolvedValue(cloneBoard());
    vi.mocked(api.moveCard).mockResolvedValue(cloneBoard());
    vi.mocked(api.deleteCard).mockResolvedValue(cloneBoard());
  });

  it("fetches and renders five columns", async () => {
    render(<KanbanBoard />);
    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
    expect(api.fetchBoard).toHaveBeenCalledTimes(1);
  });

  it("renders the chat sidebar toggle", async () => {
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);
    expect(screen.getByRole("button", { name: /ask ai/i })).toBeInTheDocument();
  });

  it("renames a column", async () => {
    render(<KanbanBoard />);
    const column = (await screen.findAllByTestId(/column-/i))[0];
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    const boardWithCard = cloneBoard();
    boardWithCard.cards["card-new"] = { id: "card-new", title: "New card", details: "Notes" };
    boardWithCard.columns[0].cardIds.push("card-new");
    vi.mocked(api.createCard).mockResolvedValue(boardWithCard);
    vi.mocked(api.deleteCard).mockResolvedValue(cloneBoard());

    render(<KanbanBoard />);
    const column = (await screen.findAllByTestId(/column-/i))[0];
    const addButton = within(column).getByRole("button", { name: /add a card/i });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await within(column).findByText("New card")).toBeInTheDocument();
    expect(api.createCard).toHaveBeenCalledWith("col-backlog", "New card", "Notes");

    const deleteButton = within(column).getByRole("button", { name: /delete new card/i });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    expect(api.deleteCard).toHaveBeenCalledWith("card-new");
  });
});
