import React, { act } from "react";
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
    getPrograms.mockResolvedValue([
      { id: "program-1", name: "Program A" },
      { id: "esl_kids_and_junior", name: "ESL KIDS and JUNIOR" },
    ]);
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
    const summary = "Class A - Teacher A - ESL KIDS and JUNIOR";
    const event = {
      id: "event-1",
      summary,
      classname: "Class A",
      teacher: "Teacher A",
      program: "esl_kids_and_junior_",
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

    const detailDialog = container.querySelector('[role="dialog"]');
    expect(detailDialog.textContent).toContain("Chương trình: ESL KIDS and JUNIOR");
    expect(detailDialog.textContent).not.toContain("esl_kids_and_junior_");
    expect(detailDialog.textContent).not.toContain("Calendar Lẻ");
    expect(detailDialog.textContent).not.toContain("Calendar Chẵn");

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
    expect(onCreateEvent.mock.calls[0][0].program).toBe("esl_kids_and_junior");
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

  test("does not reuse an event card at a different vertical position when changing day", async () => {
    const firstStart = new Date();
    firstStart.setHours(9, 0, 0, 0);
    const firstEnd = new Date(firstStart.getTime() + 60 * 60 * 1000);
    const nextStart = new Date(firstStart);
    nextStart.setDate(nextStart.getDate() + 1);
    nextStart.setHours(18, 0, 0, 0);
    const nextEnd = new Date(nextStart.getTime() + 60 * 60 * 1000);
    const makeEvent = (id, summary, start, end) => ({
      id,
      summary,
      classname: summary,
      teacher: "Teacher",
      program: "Program A",
      start: { dateTime: start.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      end: { dateTime: end.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      _calendar_source: "odd",
    });

    await act(async () => {
      root.render(
        <CalendarView
          events={[
            makeEvent("day-one", "Day one event", firstStart, firstEnd),
            makeEvent("day-two", "Day two event", nextStart, nextEnd),
          ]}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const dayButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "Ngày");
    await act(async () => {
      dayButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const firstCard = container.querySelector('[title*="Day one event"]');
    expect(firstCard).toBeTruthy();

    await act(async () => {
      container.querySelector('[aria-label="Khoảng thời gian tiếp theo"]')
        .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const nextCard = container.querySelector('[title*="Day two event"]');
    expect(nextCard).toBeTruthy();
    expect(nextCard).not.toBe(firstCard);
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
    expect(container.querySelectorAll('[role="dialog"]')).toHaveLength(1);
    expect(container.textContent).not.toContain("Chi tiết sự kiện");
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
    expect(onCreateEvent.mock.calls[0][0].start).toMatch(/\+07:00$/);
    expect(container.textContent).not.toContain(`Chỉnh sửa: ${summary}`);

    if (editMode === "following") {
      const updatedInstance = {
        ...instance,
        id: "new-master_20260815T040000Z",
        recurringEventId: "new-master",
        summary: "Updated recurring class",
      };
      await act(async () => {
        root.render(
          <CalendarView
            events={[updatedInstance]}
            onCreateEvent={onCreateEvent}
            onDeleteEvent={jest.fn()}
            calendarFilter="both"
          />
        );
        await flushPromises();
      });
      expect(container.textContent).toContain("Updated recurring class");
    }
    }
  );
});
