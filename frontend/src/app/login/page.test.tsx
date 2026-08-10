import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/login/page";

const replace = vi.fn();
const router = { replace };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    replace.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("redirects to / on successful login", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 200 }));
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(replace).toHaveBeenCalledWith("/");
  });

  it("shows an error and does not redirect on failed login", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
