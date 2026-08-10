import { login, logout, getSession } from "@/lib/auth";

describe("auth", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("login posts credentials and reports success", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 200 }));

    const result = await login("user", "password");

    expect(result).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      "/api/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "user", password: "password" }),
      })
    );
  });

  it("login reports failure on a non-ok response", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));

    const result = await login("user", "wrong");

    expect(result).toBe(false);
  });

  it("logout posts to the logout endpoint", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 200 }));

    await logout();

    expect(fetch).toHaveBeenCalledWith("/api/logout", { method: "POST" });
  });

  it("getSession returns the authenticated flag from the response", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ authenticated: true }), { status: 200 })
    );

    const result = await getSession();

    expect(result).toBe(true);
  });
});
