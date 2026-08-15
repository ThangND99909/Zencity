import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ModalShell from "./ModalShell";

global.IS_REACT_ACT_ENVIRONMENT = true;

describe("ModalShell accessibility", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  test("exposes dialog semantics, focuses content and closes with Escape", async () => {
    const onClose = jest.fn();
    await act(async () => {
      root.render(
        <ModalShell title="Xác nhận" description="Mô tả" onClose={onClose}>
          <button type="button">Hủy</button>
          <button type="button">Đồng ý</button>
        </ModalShell>
      );
    });

    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement.textContent).toBe("Hủy");

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("keeps Tab focus inside the dialog", async () => {
    await act(async () => {
      root.render(
        <ModalShell title="Kiểm thử">
          <button type="button">Đầu</button>
          <button type="button">Cuối</button>
        </ModalShell>
      );
    });
    const buttons = container.querySelectorAll("button");
    buttons[1].focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
    expect(document.activeElement).toBe(buttons[0]);
  });
});
