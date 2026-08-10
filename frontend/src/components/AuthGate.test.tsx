import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";
import { initialData } from "@/lib/kanban";

const replace = vi.fn();
const router = { replace };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

// A Response body can only be read once, so a shared `mockResolvedValue`
// instance breaks as soon as two endpoints are fetched (session + board).
// Use `mockImplementation` so every call gets its own fresh Response.
function mockFetch(sessionAuthenticated: boolean) {
  return (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/session") {
      return Promise.resolve(
        new Response(JSON.stringify({ authenticated: sessionAuthenticated }), { status: 200 })
      );
    }
    if (url === "/api/board") {
      return Promise.resolve(new Response(JSON.stringify(initialData), { status: 200 }));
    }
    return Promise.resolve(new Response(null, { status: 200 }));
  };
}

describe("AuthGate", () => {
  beforeEach(() => {
    replace.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("redirects to /login when the session is unauthenticated", async () => {
    vi.mocked(fetch).mockImplementation(mockFetch(false));

    render(<AuthGate />);

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("renders the board when the session is authenticated", async () => {
    vi.mocked(fetch).mockImplementation(mockFetch(true));

    render(<AuthGate />);

    expect(await screen.findByText("Kanban Studio")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("logs out and redirects to /login when the logout control is used", async () => {
    vi.mocked(fetch).mockImplementation(mockFetch(true));

    render(<AuthGate />);

    const logoutButton = await screen.findByRole("button", { name: /log out/i });
    await userEvent.click(logoutButton);

    expect(replace).toHaveBeenCalledWith("/login");
  });
});
