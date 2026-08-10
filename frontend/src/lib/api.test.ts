import {
  fetchBoard,
  renameColumn,
  createCard,
  moveCard,
  deleteCard,
  sendChatMessage,
  UnauthorizedError,
} from "@/lib/api";

const board = { columns: [], cards: {} };

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("fetchBoard requests /api/board", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(board), { status: 200 }));

    const result = await fetchBoard();

    expect(fetch).toHaveBeenCalledWith(
      "/api/board",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } })
    );
    expect(result).toEqual(board);
  });

  it("renameColumn PATCHes the column with the new title", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(board), { status: 200 }));

    await renameColumn("col-backlog", "Triage");

    expect(fetch).toHaveBeenCalledWith(
      "/api/columns/col-backlog",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ title: "Triage" }) })
    );
  });

  it("createCard POSTs to /api/cards", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(board), { status: 200 }));

    await createCard("col-backlog", "Title", "Details");

    expect(fetch).toHaveBeenCalledWith(
      "/api/cards",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ column_id: "col-backlog", title: "Title", details: "Details" }),
      })
    );
  });

  it("moveCard PATCHes the card with column and position", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(board), { status: 200 }));

    await moveCard("card-1", "col-done", 2);

    expect(fetch).toHaveBeenCalledWith(
      "/api/cards/card-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ column_id: "col-done", position: 2 }),
      })
    );
  });

  it("deleteCard DELETEs the card", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(board), { status: 200 }));

    await deleteCard("card-1");

    expect(fetch).toHaveBeenCalledWith("/api/cards/card-1", expect.objectContaining({ method: "DELETE" }));
  });

  it("sendChatMessage POSTs to /api/chat and returns reply + board", async () => {
    const chatResponse = { reply: "Done!", board };
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(chatResponse), { status: 200 }));

    const result = await sendChatMessage("move the card to Done");

    expect(fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "move the card to Done" }),
      })
    );
    expect(result).toEqual(chatResponse);
  });

  it("throws UnauthorizedError on a 401 response", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));

    await expect(fetchBoard()).rejects.toBeInstanceOf(UnauthorizedError);
  });

  it("throws a generic error on other non-ok responses", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

    await expect(fetchBoard()).rejects.toThrow();
  });
});
