import { act } from "react";
import { createRoot } from "react-dom/client";
import PasscodeModal from "./PasscodeModal";

global.IS_REACT_ACT_ENVIRONMENT = true;

describe("PasscodeModal loading feedback", () => {
  let container;
  let root;

  beforeEach(() => {
    jest.useFakeTimers();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.useRealTimers();
  });

  test("shows an immediate spinner and a helpful message when login is slow", async () => {
    let resolveSubmit;
    const onSubmit = jest.fn(() => new Promise((resolve) => {
      resolveSubmit = resolve;
    }));
    await act(async () => {
      root.render(<PasscodeModal isOpen onSubmit={onSubmit} />);
    });

    const input = container.querySelector('input[type="password"]');
    Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    ).set.call(input, "1234");
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => {
      container.querySelector("form").dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true })
      );
    });

    const button = container.querySelector('button[type="submit"]');
    expect(onSubmit).toHaveBeenCalledWith("1234");
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.textContent).toContain("Đang kiểm tra");
    expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Máy chủ đang khởi động");

    await act(async () => jest.advanceTimersByTime(1500));
    expect(container.textContent).toContain("Máy chủ đang khởi động");

    await act(async () => resolveSubmit({ success: true }));
  });
});
