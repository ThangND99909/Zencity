import { act } from "react";
import { createRoot } from "react-dom/client";
import moment from "moment-timezone";
import * as XLSX from "xlsx";
import ClassTable from "./ClassTable";
import { getPrograms } from "../services/api";

jest.mock("../services/api", () => ({
  getPrograms: jest.fn(),
}));

jest.mock("xlsx", () => ({
  utils: {
    json_to_sheet: jest.fn(() => ({})),
    book_new: jest.fn(() => ({})),
    book_append_sheet: jest.fn(),
  },
  write: jest.fn(() => new Uint8Array()),
}));

jest.mock("file-saver", () => ({ saveAs: jest.fn() }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

/**
 * File Excel xuất ra phải TỰ NHẤT QUÁN.
 *
 * ⚠️ Trước đây hai cột giờ dùng `new Date(...).toLocaleString("vi-VN")` — tức giờ
 * TRÌNH DUYỆT của người bấm xuất — trong khi cột "Timezone" lại ghi múi giờ của SỰ
 * KIỆN. Admin ở Việt Nam xuất lớp Chicago sẽ ra "21:00" nằm ngay cạnh
 * "America/Chicago"; ai mở file cũng hiểu thành 21:00 giờ Chicago. File còn được gửi
 * cho thầy cô nên sai kiểu này rất khó lần ra.
 *
 * Nay hai cột giờ được tính theo đúng múi giờ ghi ở cột "Timezone".
 */
describe("ClassTable xuất Excel", () => {
  let container;
  let root;
  let consoleError;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    getPrograms.mockResolvedValue([{ id: "program-1", name: "Program A" }]);
    // CRA bật resetMocks nên implementation bị xoá trước mỗi test → gắn lại ở đây.
    XLSX.utils.json_to_sheet.mockImplementation(() => ({}));
    XLSX.utils.book_new.mockImplementation(() => ({}));
    XLSX.write.mockImplementation(() => new Uint8Array());
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
    consoleError.mockRestore();
  });

  // ClassTable chỉ hiển thị lớp trong TUẦN HIỆN TẠI, nên dữ liệu test phải nằm trong
  // tuần đang chạy. Lấy giữa tuần (thứ Tư) để lệch múi giờ ±1 ngày vẫn không rơi ra
  // ngoài biên tuần.
  const midWeekDate = () => {
    const now = new Date();
    const day = now.getDay();                       // 0 = Chủ nhật
    const monday = new Date(now);
    monday.setDate(now.getDate() + (day === 0 ? -6 : 1 - day));
    monday.setDate(monday.getDate() + 2);           // thứ Tư
    monday.setHours(12, 0, 0, 0);
    return moment(monday).format("YYYY-MM-DD");
  };

  /** Một lớp bắt đầu đúng `hour` giờ treo tường ở `zone`, trong tuần hiện tại. */
  const classAt = (zone, hour, overrides = {}) => {
    const date = midWeekDate();
    const start = moment.tz(`${date}T${String(hour).padStart(2, "0")}:00`, zone);
    const end = start.clone().add(1, "hour");
    return {
      id: `evt-${zone}`,
      summary: "Lop A - Co Lan - Program A",
      classname: "Lop A",
      teacher: "Co Lan",
      description: "Teacher: Co Lan",
      start: { dateTime: start.toISOString(), timeZone: zone },
      end: { dateTime: end.toISOString(), timeZone: zone },
      _calendar_source: "odd",
      ...overrides,
    };
  };

  /** Ngày của lớp, viết theo đúng định dạng cột Excel. */
  const expectedDate = () => moment(midWeekDate(), "YYYY-MM-DD").format("DD/MM/YYYY");

  const exportRows = async (classes) => {
    await act(async () => {
      root.render(
        <ClassTable classes={classes} onDelete={jest.fn()} calendarFilter="both" />
      );
      await flushPromises();
    });

    const exportButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent.includes("Xuất Excel")
    );
    expect(exportButton).toBeTruthy();

    await act(async () => {
      exportButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await flushPromises();
    });

    expect(XLSX.utils.json_to_sheet).toHaveBeenCalled();
    return XLSX.utils.json_to_sheet.mock.calls.at(-1)[0];
  };

  const rowFor = (rows, teacher) => {
    const row = rows.find((candidate) => candidate.Teacher === teacher);
    expect(row).toBeTruthy();
    return row;
  };

  test("cột giờ tính theo đúng múi giờ ghi ở cột Timezone", async () => {
    const rows = await exportRows([classAt("America/Chicago", 9)]);
    const row = rowFor(rows, "Co Lan");

    expect(row.Timezone).toBe("America/Chicago");
    expect(row["Start Time"]).toBe(`${expectedDate()} 09:00`);
    expect(row["End Time"]).toBe(`${expectedDate()} 10:00`);
  });

  test("không còn xuất ra giờ trình duyệt dưới nhãn múi giờ sự kiện", async () => {
    const cls = classAt("America/Chicago", 9);
    const rows = await exportRows([cls]);
    const row = rowFor(rows, "Co Lan");

    // Con số mà bản cũ ghi ra: giờ trình duyệt của người bấm xuất file.
    const gioTrinhDuyet = moment(cls.start.dateTime).format("HH:mm");
    const gioChicago = "09:00";

    expect(row["Start Time"]).toContain(gioChicago);
    if (gioTrinhDuyet !== gioChicago) {
      expect(row["Start Time"]).not.toContain(gioTrinhDuyet);
    }
  });

  test("mỗi lớp dùng múi giờ của riêng nó trong cùng một file", async () => {
    const rows = await exportRows([
      classAt("America/Chicago", 9, { id: "a", teacher: "Co Lan", description: "Teacher: Co Lan" }),
      classAt("Asia/Ho_Chi_Minh", 9, { id: "b", teacher: "Co Mai", description: "Teacher: Co Mai" }),
    ]);

    const chicago = rowFor(rows, "Co Lan");
    const vietnam = rowFor(rows, "Co Mai");

    // Hai lớp cách nhau 12 tiếng thật, nhưng cùng là "09:00" ở múi giờ của mình.
    expect(chicago["Start Time"]).toContain("09:00");
    expect(vietnam["Start Time"]).toContain("09:00");
    expect(chicago.Timezone).toBe("America/Chicago");
    expect(vietnam.Timezone).toBe("Asia/Ho_Chi_Minh");
  });

  test("hai múi giờ Mỹ lệch nhau vẫn ra đúng giờ riêng", async () => {
    const rows = await exportRows([
      classAt("America/Chicago", 9, { id: "a", teacher: "Co Lan", description: "Teacher: Co Lan" }),
      classAt("America/Los_Angeles", 9, { id: "b", teacher: "Co Hoa", description: "Teacher: Co Hoa" }),
    ]);

    expect(rowFor(rows, "Co Lan")["Start Time"]).toContain("09:00");
    expect(rowFor(rows, "Co Hoa")["Start Time"]).toContain("09:00");
    // Cùng ghi 09:00 nhưng là hai mốc thật cách nhau 2 tiếng.
    expect(rowFor(rows, "Co Lan").Timezone).not.toBe(rowFor(rows, "Co Hoa").Timezone);
  });

  test("lớp thiếu timeZone thì mặc định giờ Việt Nam và vẫn khớp cột Timezone", async () => {
    const cls = classAt("Asia/Ho_Chi_Minh", 9);
    const rows = await exportRows([{
      ...cls,
      start: { dateTime: cls.start.dateTime },
      end: { dateTime: cls.end.dateTime },
    }]);
    const row = rowFor(rows, "Co Lan");

    expect(row.Timezone).toBe("Asia/Ho_Chi_Minh");
    expect(row["Start Time"]).toBe(`${expectedDate()} 09:00`);
  });

  test("biên sự kiện hỏng không sinh ra 'Invalid date' trong file", async () => {
    const cls = classAt("America/Chicago", 9);
    const rows = await exportRows([{
      ...cls,
      end: { timeZone: "America/Chicago" },   // thiếu dateTime
    }]);
    const row = rowFor(rows, "Co Lan");

    expect(row["Start Time"]).toBe(`${expectedDate()} 09:00`);
    expect(row["End Time"]).toBe("");
  });

  test("số cột khớp với mảng độ rộng cột", async () => {
    const rows = await exportRows([classAt("America/Chicago", 9)]);

    expect(Object.keys(rows[0])).toHaveLength(14);
  });
});
