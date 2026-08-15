import React from "react";
import { act } from "react-dom/test-utils";
import { createRoot } from "react-dom/client";
import CalendarView from "./CalendarView";
import {
  checkScheduleConflict,
  getEvent,
  getPrograms,
  getTimezones,
} from "../services/api";

jest.mock("../services/api", () => ({
  checkScheduleConflict: jest.fn(),
  getEvent: jest.fn(),
  getPrograms: jest.fn(),
  getTimezones: jest.fn(),
}));

global.IS_REACT_ACT_ENVIRONMENT = true;

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("CalendarView edit lifecycle", () => {
  let container;
  let root;
  let consoleError;

  beforeEach(async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    getPrograms.mockResolvedValue([{ id: "program-1", name: "Program A" }]);
    getTimezones.mockResolvedValue({ timezones: [] });
    checkScheduleConflict.mockResolvedValue({ has_conflict: false, conflicts: [] });
    getEvent.mockReset();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    consoleError.mockRestore();
    jest.clearAllMocks();
  });

  test("waits for edit data before opening form and closes safely after update", async () => {
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const summary = "Class A - Teacher A - Program A";
    const event = {
      id: "event-1",
      summary,
      classname: "Class A",
      teacher: "Teacher A",
      program: "Program A",
      zoom_link: "https://zoom.example/test",
      start: { dateTime: start.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      end: { dateTime: end.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      _calendar_source: "odd",
    };
    const onCreateEvent = jest.fn().mockResolvedValue({ id: event.id });

    await act(async () => {
      root.render(
        <CalendarView
          events={[event]}
          onCreateEvent={onCreateEvent}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const eventName = Array.from(container.querySelectorAll("div"))
      .find((element) => element.textContent === summary);
    expect(eventName).toBeTruthy();

    await act(async () => {
      eventName.parentElement.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const editButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Chỉnh sửa"));
    expect(editButton).toBeTruthy();

    await act(async () => {
      editButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(container.textContent).toContain(`Chỉnh sửa: ${summary}`);

    const updateButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Cập nhật"));
    expect(updateButton).toBeTruthy();

    await act(async () => {
      updateButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(onCreateEvent).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toContain(`Chỉnh sửa: ${summary}`);
    expect(
      consoleError.mock.calls.some((args) =>
        args.some((value) => String(value).includes("Cannot read properties of null"))
      )
    ).toBe(false);
  });

  test("creates an event and clears the popup state without a null render", async () => {
    const onCreateEvent = jest.fn().mockResolvedValue({ id: "created-event" });
    await act(async () => {
      root.render(
        <CalendarView
          events={[]}
          onCreateEvent={onCreateEvent}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const createButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "+ Tạo");
    await act(async () => {
      createButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const field = (labelText, selector = "input") => Array.from(container.querySelectorAll("label"))
      .find((label) => label.textContent.includes(labelText))
      .querySelector(selector);
    const changeValue = async (element, value) => {
      const prototype = element.tagName === "SELECT"
        ? window.HTMLSelectElement.prototype
        : window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, value);
      await act(async () => {
        element.dispatchEvent(new Event("change", { bubbles: true }));
        element.dispatchEvent(new Event("input", { bubbles: true }));
      });
    };

    await changeValue(field("Tên lớp"), "New Class");
    await changeValue(field("Giáo viên"), "Teacher C");
    await changeValue(field("Chương trình", "select"), "program-1");
    await changeValue(field("Link Zoom"), "https://zoom.example/new");

    const submitButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Tạo mới"));
    await act(async () => {
      submitButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(onCreateEvent).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toContain("Thêm sự kiện mới");
  });

  test.each(["this", "following"])(
    "opens and updates recurring mode '%s' safely",
    async (editMode) => {
    const start = new Date();
    start.setHours(11, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const masterStart = new Date(start);
    masterStart.setDate(masterStart.getDate() - 7);
    const summary = "Recurring Class - Teacher B - Program B";
    const master = {
      id: "master-1",
      summary,
      start: { dateTime: masterStart.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      recurrence: ["RRULE:FREQ=WEEKLY;COUNT=5;BYDAY=SA"],
    };
    const instance = {
      id: "master-1_20260815T040000Z",
      recurringEventId: master.id,
      summary,
      classname: "Recurring Class",
      teacher: "Teacher B",
      program: "Program B",
      zoom_link: "https://zoom.example/recurring",
      start: { dateTime: start.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      end: { dateTime: end.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      _calendar_source: "odd",
      _is_instance: true,
    };
    getEvent.mockResolvedValue(master);
    const onCreateEvent = jest.fn().mockResolvedValue({ id: master.id });

    await act(async () => {
      root.render(
        <CalendarView
          events={[instance]}
          onCreateEvent={onCreateEvent}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const eventName = Array.from(container.querySelectorAll("div"))
      .find((element) => element.textContent === summary);
    expect(eventName).toBeTruthy();

    await act(async () => {
      eventName.parentElement.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    const editButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Chỉnh sửa"));

    await act(async () => {
      editButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(container.textContent).toContain("Chọn cách chỉnh sửa");
    if (editMode === "following") {
      const followingRadio = container.querySelector('input[value="following"]');
      await act(async () => {
        followingRadio.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }
    const continueButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Tiếp tục chỉnh sửa"));
    await act(async () => {
      continueButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain(`Chỉnh sửa: ${summary}`);
    const updateButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Cập nhật"));
    await act(async () => {
      updateButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(onCreateEvent).toHaveBeenCalledTimes(1);
    expect(onCreateEvent.mock.calls[0][0].edit_mode).toBe(editMode);
    expect(container.textContent).not.toContain(`Chỉnh sửa: ${summary}`);
    }
  );
});
