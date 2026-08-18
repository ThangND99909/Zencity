import { act } from "react";
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

  const renderEmptyCalendar = async (onCreateEvent) => {
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
  };

  test("disables event creation when Google Calendar is unavailable", async () => {
    await act(async () => {
      root.render(
        <CalendarView
          events={[]}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
          writeDisabled
          writeDisabledReason="Google Calendar chưa được chia sẻ."
        />
      );
      await flushPromises();
    });

    const createButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "+ Tạo");
    expect(createButton).toBeTruthy();
    expect(createButton.disabled).toBe(true);
    expect(createButton.title).toContain("chưa được chia sẻ");
  });

  test("lists managed programs and programs extracted from event title suffixes", async () => {
    const now = new Date();
    const end = new Date(now.getTime() + 60 * 60 * 1000);
    const events = [
      {
        id: "beginner-vietnamese",
        summary: "Room 2X - Tutoring Katherine - Beginner Vietnamese",
        start: { dateTime: now.toISOString() },
        end: { dateTime: end.toISOString() }
      },
      {
        id: "beginner",
        summary: "Room 5B - Tutoring Vietnamese - Student (13y)- Beginner",
        start: { dateTime: now.toISOString() },
        end: { dateTime: end.toISOString() }
      }
    ];

    await act(async () => {
      root.render(
        <CalendarView
          events={[events[0]]}
          programEvents={[events[1]]}
          onCreateEvent={jest.fn()}
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

    const labels = Array.from(container.querySelectorAll("#event-program option"))
      .map((option) => option.textContent.trim());
    expect(labels).toEqual(expect.arrayContaining([
      "-- Chọn chương trình --",
      "Program A",
      "ESL KIDS and JUNIOR",
      "Beginner Vietnamese",
      "Beginner"
    ]));
    expect(labels.filter((label) => label === "-- Chọn chương trình --")).toHaveLength(1);
  });

  const setFieldValue = async (labelText, value, selector = "input") => {
    const element = Array.from(container.querySelectorAll("label"))
      .find((label) => label.textContent.includes(labelText))
      .querySelector(selector);
    const prototype = element.tagName === "SELECT"
      ? window.HTMLSelectElement.prototype
      : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, value);
    await act(async () => {
      element.dispatchEvent(new Event("change", { bubbles: true }));
      element.dispatchEvent(new Event("input", { bubbles: true }));
    });
  };

  const fillNewEventForm = async () => {
    const createButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "+ Tạo");
    await act(async () => {
      createButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await setFieldValue("Tên lớp", "New Class");
    await setFieldValue("Giáo viên", "Teacher C");
    await setFieldValue("Chương trình", "program-1", "select");
    await setFieldValue("Link Zoom", "https://zoom.example/new");
  };

  const clickButton = async (label) => {
    const button = Array.from(container.querySelectorAll("button"))
      .find((element) => element.textContent.includes(label));
    expect(button).toBeTruthy();
    await act(async () => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });
  };

  // Bộ 3 test dưới đây khoá lại lỗi: nút lưu từng được gắn onClick={handleSave},
  // khiến React truyền SyntheticEvent vào skipConflictCheck (truthy) → bước kiểm tra
  // trùng lịch bị bỏ qua hoàn toàn và sự kiện trùng vẫn được tạo.
  test("runs the conflict check before creating an event", async () => {
    const onCreateEvent = jest.fn().mockResolvedValue({ id: "created-event" });
    await renderEmptyCalendar(onCreateEvent);
    await fillNewEventForm();
    await clickButton("Tạo mới");

    expect(checkScheduleConflict).toHaveBeenCalledTimes(1);
    expect(checkScheduleConflict).toHaveBeenCalledWith(
      expect.objectContaining({
        teacher: "Teacher C",
        start: expect.any(String),
        end: expect.any(String),
        excludeEventId: undefined,
        recurrence: "",
      })
    );
    expect(onCreateEvent).toHaveBeenCalledTimes(1);
  });

  test("sends the recurrence rule so every occurrence gets checked", async () => {
    const onCreateEvent = jest.fn().mockResolvedValue({ id: "created-event" });
    await renderEmptyCalendar(onCreateEvent);
    await fillNewEventForm();
    await setFieldValue("Lặp lại", "DAILY", "select");
    await setFieldValue("Số lần lặp", "5");
    await clickButton("Tạo mới");

    // Backend cần luật lặp để bung ra đủ 5 buổi; nếu chỉ gửi start/end thì 4 buổi
    // sau không được kiểm tra và có thể trùng lịch mà không ai biết.
    expect(checkScheduleConflict).toHaveBeenCalledWith(
      expect.objectContaining({ recurrence: "DAILY", repeatCount: 5 })
    );
    // Luật lặp dùng để kiểm tra phải khớp đúng luật lặp được lưu.
    const saved = onCreateEvent.mock.calls[0][0];
    expect(saved.recurrence).toBe("DAILY");
    expect(saved.repeat_count).toBe(5);
  });

  test("does not create the event while a conflict is unresolved", async () => {
    checkScheduleConflict.mockResolvedValue({
      has_conflict: true,
      conflicts: [
        {
          event_summary: "Existing Class",
          event_teacher: "Teacher C",
          event_start: "2026-08-15T02:00:00Z",
          event_end: "2026-08-15T03:00:00Z",
        },
      ],
    });
    const onCreateEvent = jest.fn().mockResolvedValue({ id: "created-event" });
    await renderEmptyCalendar(onCreateEvent);
    await fillNewEventForm();
    await clickButton("Tạo mới");

    expect(onCreateEvent).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Existing Class");

    // Người dùng chủ động chấp nhận trùng lịch thì mới được lưu.
    await clickButton("Vẫn lưu sự kiện");
    expect(onCreateEvent).toHaveBeenCalledTimes(1);
  });

  test("does not create the event when the conflict check fails", async () => {
    checkScheduleConflict.mockRejectedValue(new Error("backend unavailable"));
    const onCreateEvent = jest.fn().mockResolvedValue({ id: "created-event" });
    await renderEmptyCalendar(onCreateEvent);
    await fillNewEventForm();
    await clickButton("Tạo mới");

    expect(onCreateEvent).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Không kiểm tra được trùng lịch");
    expect(container.textContent).toContain("CHƯA được lưu");
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
    await renderEmptyCalendar(onCreateEvent);
    await fillNewEventForm();
    await clickButton("Tạo mới");

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

  test("renders Google-style month event rows and opens the remaining-events list", async () => {
    const starts = [5, 7, 9, 11].map((hour) => {
      const date = new Date();
      date.setHours(hour, 0, 0, 0);
      return date;
    });
    const monthEvents = starts.map((start, index) => ({
      id: `month-event-${index}`,
      summary: `Month class ${index + 1}`,
      classname: `Month class ${index + 1}`,
      teacher: "Teacher",
      program: "Program A",
      start: { dateTime: start.toISOString(), timeZone: "Asia/Ho_Chi_Minh" },
      end: {
        dateTime: new Date(start.getTime() + 60 * 60 * 1000).toISOString(),
        timeZone: "Asia/Ho_Chi_Minh",
      },
      _calendar_source: "odd",
    }));

    await act(async () => {
      root.render(
        <CalendarView
          events={monthEvents}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const monthButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "Tháng");
    await act(async () => {
      monthButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const visibleEventRows = Array.from(container.querySelectorAll("button"))
      .filter((button) => button.title?.startsWith("Month class"));
    expect(visibleEventRows).toHaveLength(2);
    expect(visibleEventRows[0].textContent).toMatch(/5AMMonth class 1/);

    const moreButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "2 mục khác");
    expect(moreButton).toBeTruthy();

    await act(async () => {
      moreButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const overflowDialog = container.querySelector('[role="dialog"][aria-label^="Sự kiện ngày"]');
    expect(overflowDialog).toBeTruthy();
    monthEvents.forEach((event) => {
      expect(overflowDialog.textContent).toContain(event.summary);
    });
  });

  test("reports the complete visible month range when the user changes months", async () => {
    const onVisibleRangeChange = jest.fn();
    await act(async () => {
      root.render(
        <CalendarView
          events={[]}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
          onVisibleRangeChange={onVisibleRangeChange}
        />
      );
      await flushPromises();
    });

    const monthButton = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.trim() === "Tháng");
    await act(async () => {
      monthButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    const selectedMonth = new Date();
    const firstOfMonth = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth(), 1);
    const mondayIndex = (firstOfMonth.getDay() + 6) % 7;
    const expectedStart = new Date(
      selectedMonth.getFullYear(),
      selectedMonth.getMonth(),
      1 - mondayIndex
    );
    expectedStart.setHours(0, 0, 0, 0);
    const lastOfMonth = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 0);
    const lastDayIndex = (lastOfMonth.getDay() + 6) % 7;
    const expectedEnd = new Date(
      selectedMonth.getFullYear(),
      selectedMonth.getMonth() + 1,
      7 - lastDayIndex
    );
    expectedEnd.setHours(0, 0, 0, 0);

    expect(onVisibleRangeChange).toHaveBeenLastCalledWith({
      timeMin: expectedStart.toISOString(),
      timeMax: expectedEnd.toISOString(),
    });

    const nextButton = container.querySelector('[aria-label="Khoảng thời gian tiếp theo"]');
    await act(async () => {
      nextButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    const nextRange = onVisibleRangeChange.mock.calls.at(-1)[0];
    expect(new Date(nextRange.timeMin).getTime()).toBeGreaterThan(expectedStart.getTime());
    expect(new Date(nextRange.timeMax).getTime()).toBeGreaterThan(new Date(nextRange.timeMin).getTime());
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

    const conflictPayload = checkScheduleConflict.mock.calls[0][0];
    expect(conflictPayload.excludeEventId).toBe(instance.id);
    if (editMode === "following") {
      // Cả chuỗi bị thay thế → phải loại trừ chuỗi cũ, nếu không mọi buổi của chính
      // chuỗi đó sẽ bị báo trùng với nhau.
      expect(conflictPayload.excludeMasterEventId).toBe(master.id);
      expect(conflictPayload.recurrence).toBe("WEEKLY");
    } else {
      // Mode 'this' chỉ tách đúng một buổi thành sự kiện đơn: không còn luật lặp, và
      // các buổi còn lại của chuỗi VẪN phải được so trùng.
      expect(conflictPayload.excludeMasterEventId).toBeNull();
      expect(conflictPayload.recurrence).toBe("");
    }

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
