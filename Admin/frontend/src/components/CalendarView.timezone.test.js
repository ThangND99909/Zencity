import { act } from "react";
import { createRoot } from "react-dom/client";
import moment from "moment-timezone";
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

/**
 * Giống Google Calendar: cả lưới lẫn popup đo theo múi giờ NGƯỜI XEM.
 *
 * Bất biến được khoá ở đây: NHÃN GIỜ in trong khối sự kiện phải khớp với HÀNG GIỜ mà
 * khối đó được vẽ vào. Trước đây vị trí tính theo giờ trình duyệt
 * (`new Date(...).getHours()`) còn nhãn lại định dạng theo múi giờ của sự kiện, nên
 * một lớp 9:00 sáng giờ Chicago bị vẽ ở hàng 21:00 nhưng ghi "09:00".
 *
 * Mọi giá trị mong đợi đều suy ra từ chính giờ máy đang chạy test, nên test đúng trên
 * mọi máy bất kể TZ của CI.
 */

// Trải rộng nhiều offset để chắc chắn tìm được một múi giờ KHÁC máy đang chạy test.
const CANDIDATE_ZONES = [
  "Pacific/Auckland",
  "Asia/Ho_Chi_Minh",
  "Europe/London",
  "America/Chicago",
  "America/Los_Angeles",
];

const pickForeignZone = (instant) => {
  const localOffset = moment(instant).utcOffset();
  const zone = CANDIDATE_ZONES.find(
    (candidate) => moment(instant).tz(candidate).utcOffset() !== localOffset
  );
  if (!zone) throw new Error("Không tìm được múi giờ khác giờ máy để test");
  return zone;
};

const viewerTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

describe("CalendarView hiển thị theo múi giờ người xem", () => {
  let container;
  let root;
  let consoleError;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    getPrograms.mockResolvedValue([{ id: "program-1", name: "Program A" }]);
    getTimezones.mockResolvedValue({
      timezones: [
        { value: "America/Chicago", label: "🇺🇸 Giờ Miền Trung (UTC-6/-5)" },
        { value: "Asia/Ho_Chi_Minh", label: "🇻🇳 Giờ Việt Nam (UTC+7)" },
      ],
    });
    checkScheduleConflict.mockResolvedValue({ has_conflict: false, conflicts: [] });
    getEvent.mockReset();
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
    consoleError.mockRestore();
  });

  const makeEvent = (start, end, zone) => ({
    id: "evt-1",
    summary: "Lop Ngoai Gio - Co Lan - Program A",
    classname: "Lop Ngoai Gio",
    teacher: "Co Lan",
    program: "Program A",
    timezone: zone,
    start: { dateTime: start.toISOString(), timeZone: zone },
    end: { dateTime: end.toISOString(), timeZone: zone },
    _calendar_source: "odd",
  });

  const render = async (event) => {
    await act(async () => {
      root.render(
        <CalendarView
          events={[event]}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });
  };

  const switchTo = async (label) => {
    const button = Array.from(container.querySelectorAll("button")).find(
      (candidate) => candidate.textContent.trim() === label
    );
    expect(button).toBeTruthy();
    await act(async () => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });
  };

  /** Khối sự kiện + nhãn giờ của nó — dùng được cho cả lưới tuần lẫn lưới ngày. */
  const readCard = () => {
    const label = container.querySelector(".eventTime");
    expect(label).toBeTruthy();
    return {
      text: label.textContent.trim(),
      top: label.parentElement.style.top,
      card: label.parentElement,
    };
  };

  const openDetailPopup = async (card) => {
    await act(async () => {
      card.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });
  };

  test.each([["Tuần"], ["Ngày"]])(
    "lưới %s: nhãn giờ khớp đúng hàng mà khối được vẽ vào",
    async (viewLabel) => {
      const start = new Date();
      start.setHours(9, 0, 0, 0); // 09:00 theo giờ máy đang chạy test
      const end = new Date(start.getTime() + 60 * 60 * 1000);
      const foreignZone = pickForeignZone(start);

      await render(makeEvent(start, end, foreignZone));
      await switchTo(viewLabel);

      const { text, top } = readCard();
      const gioMay = moment(start).format("HH:mm");
      const gioSuKien = moment(start).tz(foreignZone).format("HH:mm");

      // 1. Nhãn theo giờ người xem.
      expect(text).toBe(gioMay);
      // 2. KHÔNG phải giờ gốc của sự kiện — đây chính là lỗi cũ.
      expect(gioSuKien).not.toBe(gioMay);
      expect(text).not.toBe(gioSuKien);
      // 3. Và khớp với hàng giờ mà khối đang nằm.
      expect(top).toBe(`${start.getHours() * 60 + start.getMinutes()}px`);
    }
  );

  test("lớp buổi tối cũng khớp vị trí, không bị lệch ngày", async () => {
    const start = new Date();
    start.setHours(21, 30, 0, 0);
    const end = new Date(start.getTime() + 90 * 60 * 1000);

    await render(makeEvent(start, end, pickForeignZone(start)));
    await switchTo("Ngày");

    const { text, top } = readCard();
    expect(text).toBe(moment(start).format("HH:mm"));
    expect(top).toBe(`${21 * 60 + 30}px`);
  });

  test("popup ghi rõ con số giờ là giờ của người xem, kèm giờ gốc của lớp", async () => {
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const foreignZone = pickForeignZone(start);

    await render(makeEvent(start, end, foreignZone));
    await switchTo("Ngày");
    await openDetailPopup(readCard().card);

    const text = document.body.textContent;

    // Giờ hiển thị là giờ người xem, và được nói rõ là giờ của ai.
    expect(text).toContain(moment(start).format("HH:mm DD/MM/YYYY"));
    expect(text).toContain("giờ của bạn");
    expect(text).toContain(viewerTimezone());

    // Múi giờ của sự kiện là thông tin RIÊNG, không còn dán nhãn lên con số ở trên.
    expect(text).toContain("Múi giờ sự kiện");
    expect(text).toContain(moment(start).tz(foreignZone).format("HH:mm DD/MM/YYYY"));
  });

  test("popup dùng nhãn thân thiện của múi giờ khi có trong danh sách", async () => {
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);

    await render(makeEvent(start, end, "America/Chicago"));
    await switchTo("Ngày");
    await openDetailPopup(readCard().card);

    expect(document.body.textContent).toContain("🇺🇸 Giờ Miền Trung (UTC-6/-5)");
  });

  test("người xem đang ở đúng múi giờ của lớp thì không lặp lại dòng giờ gốc", async () => {
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);

    await render(makeEvent(start, end, viewerTimezone()));
    await switchTo("Ngày");
    await openDetailPopup(readCard().card);

    const text = document.body.textContent;
    const gio = moment(start).format("HH:mm DD/MM/YYYY");

    expect(text).toContain("Múi giờ sự kiện");
    expect(text.split(gio).length - 1).toBe(1);
  });

  test("biên sự kiện dị dạng không bị hiển thị thành giờ hiện tại", async () => {
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const event = makeEvent(start, end, "America/Chicago");
    event.start = { timeZone: "America/Chicago" }; // thiếu cả dateTime lẫn date

    await render(event);
    await switchTo("Ngày");

    // Lưới vẫn dựng được (không crash), và không nhãn nào bịa ra giờ bây giờ.
    expect(container.querySelector(".eventsColumn")).toBeTruthy();
    const bayGio = moment().format("HH:mm");
    container.querySelectorAll(".eventTime").forEach((node) => {
      expect(node.textContent.trim()).not.toBe(bayGio);
    });
  });
});

/**
 * Lớp mới phải mặc định vào múi giờ của chính người đang tạo — miễn là sản phẩm hỗ
 * trợ (Việt Nam + Hoa Kỳ). Trước đây `openPopup` đối chiếu với một danh sách 7 múi
 * giờ viết cứng, tách rời khỏi dropdown, nên Denver/Phoenix/Anchorage/Honolulu rơi hết
 * về giờ Việt Nam trong khi ô giờ vừa bấm lại là giờ của họ → lệch tới 13 tiếng.
 */
describe("Múi giờ mặc định khi tạo lớp mới", () => {
  let container;
  let root;
  let consoleError;
  let resolvedOptionsSpy;

  const US_OPTIONS = [
    { value: "Asia/Ho_Chi_Minh", label: "🇻🇳 Giờ Việt Nam (UTC+7)" },
    { value: "America/New_York", label: "🇺🇸 Giờ Miền Đông - New York (UTC-5/-4)" },
    { value: "America/Chicago", label: "🇺🇸 Giờ Miền Trung - Chicago (UTC-6/-5)" },
    { value: "America/Denver", label: "🇺🇸 Giờ Miền Núi - Denver (UTC-7/-6)" },
    { value: "America/Phoenix", label: "🇺🇸 Giờ Arizona (UTC-7, không đổi giờ)" },
    { value: "America/Los_Angeles", label: "🇺🇸 Giờ Miền Tây - Los Angeles (UTC-8/-7)" },
    { value: "America/Anchorage", label: "🇺🇸 Giờ Alaska (UTC-9/-8)" },
    { value: "Pacific/Honolulu", label: "🇺🇸 Giờ Hawaii (UTC-10, không đổi giờ)" },
  ];

  // Giả lập trình duyệt đang ở một múi giờ khác mà KHÔNG phá toLocaleString.
  const pretendViewerIsIn = (timeZone) => {
    const original = Intl.DateTimeFormat.prototype.resolvedOptions;
    resolvedOptionsSpy = jest
      .spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions")
      .mockImplementation(function resolved() {
        return { ...original.call(this), timeZone };
      });
  };

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    getPrograms.mockResolvedValue([{ id: "program-1", name: "Program A" }]);
    getTimezones.mockResolvedValue({ timezones: US_OPTIONS });
    checkScheduleConflict.mockResolvedValue({ has_conflict: false, conflicts: [] });
    getEvent.mockReset();
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
    consoleError.mockRestore();
    if (resolvedOptionsSpy) resolvedOptionsSpy.mockRestore();
    resolvedOptionsSpy = undefined;
  });

  const openCreateForm = async () => {
    await act(async () => {
      root.render(
        <CalendarView
          events={[]}
          onCreateEvent={jest.fn()}
          onDeleteEvent={jest.fn()}
          calendarFilter="both"
        />
      );
      await flushPromises();
    });

    const createButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.trim() === "+ Tạo lớp"
    );
    expect(createButton).toBeTruthy();
    await act(async () => {
      createButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    const select = Array.from(container.querySelectorAll("select")).find((node) =>
      Array.from(node.options).some((option) => option.value === "Asia/Ho_Chi_Minh")
    );
    expect(select).toBeTruthy();
    return select;
  };

  test.each([
    ["America/Denver"],
    ["America/Phoenix"],
    ["America/Anchorage"],
    ["Pacific/Honolulu"],
    ["America/New_York"],
    ["America/Chicago"],
    ["America/Los_Angeles"],
    ["Asia/Ho_Chi_Minh"],
  ])("người tạo ở %s thì form mặc định đúng múi giờ đó", async (zone) => {
    pretendViewerIsIn(zone);

    const select = await openCreateForm();

    expect(select.value).toBe(zone);
  });

  test("bốn múi giờ Mỹ từng bị danh sách cứng bỏ sót nay không còn rơi về giờ VN", async () => {
    for (const zone of ["America/Denver", "America/Phoenix", "America/Anchorage", "Pacific/Honolulu"]) {
      pretendViewerIsIn(zone);
      const select = await openCreateForm();
      expect(select.value).not.toBe("Asia/Ho_Chi_Minh");
      resolvedOptionsSpy.mockRestore();
      await act(async () => {
        root.unmount();
      });
      container.remove();
      container = document.createElement("div");
      document.body.appendChild(container);
      root = createRoot(container);
    }
  });

  test("người tạo ở nước không hỗ trợ thì mặc định giờ Việt Nam", async () => {
    pretendViewerIsIn("Asia/Bangkok");

    const select = await openCreateForm();

    expect(select.value).toBe("Asia/Ho_Chi_Minh");
  });

  test("dropdown chỉ liệt kê múi giờ Việt Nam và Hoa Kỳ", async () => {
    pretendViewerIsIn("Asia/Ho_Chi_Minh");

    const select = await openCreateForm();
    const values = Array.from(select.options).map((option) => option.value);

    expect(values).toEqual(US_OPTIONS.map((option) => option.value));
    values.forEach((value) => {
      expect(value === "Asia/Ho_Chi_Minh" || /^(America|Pacific)\//.test(value)).toBe(true);
    });
  });
});
