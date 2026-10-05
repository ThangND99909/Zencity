import moment from "moment-timezone";
import {
  resolveDefaultTimezone,
  TIMEZONE_ALIASES,
  FALLBACK_TIMEZONE,
  formatCompactInZone,
  formatInZone,
  formatRangeInZone,
  getEventInstant,
  getEventTimezone,
  getViewerTimezone,
  isKnownTimezone,
  sameWallClock,
} from "./eventTime";

// Cùng một mốc thật, viết dưới dạng UTC.
const MUA_HE = "2026-07-15T14:00:00Z"; // 09:00 Chicago (CDT, -05:00) = 21:00 VN
const MUA_DONG = "2026-01-15T15:00:00Z"; // 09:00 Chicago (CST, -06:00) = 22:00 VN

describe("formatInZone", () => {
  test("cùng một mốc hiện ra khác nhau ở từng múi giờ người xem", () => {
    expect(formatInZone(MUA_HE, "America/Chicago")).toBe("09:00");
    expect(formatInZone(MUA_HE, "America/New_York")).toBe("10:00");
    expect(formatInZone(MUA_HE, "America/Los_Angeles")).toBe("07:00");
    expect(formatInZone(MUA_HE, "Asia/Ho_Chi_Minh")).toBe("21:00");
    expect(formatInZone(MUA_HE, "Europe/London")).toBe("15:00");
  });

  test("người xem ở VN thấy lớp 9h sáng Chicago đổi giờ theo mùa", () => {
    // Đây chính là lý do nhãn phải bám múi giờ người xem: giờ VN của cùng một lớp
    // 9h sáng Chicago là 21:00 mùa hè nhưng 22:00 mùa đông.
    expect(formatInZone(MUA_HE, "Asia/Ho_Chi_Minh")).toBe("21:00");
    expect(formatInZone(MUA_DONG, "Asia/Ho_Chi_Minh")).toBe("22:00");

    // Còn chính người xem ở Chicago thì luôn thấy 09:00.
    expect(formatInZone(MUA_HE, "America/Chicago")).toBe("09:00");
    expect(formatInZone(MUA_DONG, "America/Chicago")).toBe("09:00");
  });

  test("múi giờ thiếu hoặc không hợp lệ thì dùng giờ máy người xem", () => {
    // KHÔNG được rơi về một múi giờ cố định: vị trí khối sự kiện trong lưới tính theo
    // giờ máy, fallback cứng sẽ làm nhãn lệch khỏi hàng nó đang nằm.
    const gioMay = moment(MUA_HE).format("HH:mm");

    expect(formatInZone(MUA_HE, undefined)).toBe(gioMay);
    expect(formatInZone(MUA_HE, null)).toBe(gioMay);
    expect(formatInZone(MUA_HE, "")).toBe(gioMay);
    expect(formatInZone(MUA_HE, "Mars/Olympus")).toBe(gioMay);
    expect(formatInZone(MUA_HE, "UTC+7")).toBe(gioMay);
  });

  test("nhận Date object và chuỗi có offset", () => {
    expect(formatInZone(new Date(MUA_HE), "America/Chicago")).toBe("09:00");
    expect(formatInZone("2026-07-15T09:00:00-05:00", "America/Chicago")).toBe("09:00");
    expect(formatInZone("2026-07-15T21:00:00+07:00", "America/Chicago")).toBe("09:00");
  });

  test("đổi được định dạng", () => {
    expect(formatInZone(MUA_HE, "America/Chicago", "HH:mm DD/MM/YYYY"))
      .toBe("09:00 15/07/2026");
  });

  test("đầu vào hỏng trả về chuỗi rỗng, không in Invalid date", () => {
    ["", null, undefined, "khong-phai-ngay"].forEach((bad) => {
      expect(formatInZone(bad, "America/Chicago")).toBe("");
    });
  });
});

describe("formatCompactInZone", () => {
  test("bỏ phút khi đúng giờ tròn", () => {
    expect(formatCompactInZone(MUA_HE, "America/Chicago")).toBe("9AM");
    expect(formatCompactInZone(MUA_HE, "Asia/Ho_Chi_Minh")).toBe("9PM");
  });

  test("giữ phút khi lẻ", () => {
    expect(formatCompactInZone("2026-07-15T14:30:00Z", "America/Chicago")).toBe("9:30AM");
  });

  test("múi giờ hỏng thì theo giờ máy, đầu vào hỏng thì rỗng", () => {
    const m = moment(MUA_HE);
    const gioMay = m.format(m.minutes() === 0 ? "hA" : "h:mmA");

    expect(formatCompactInZone(MUA_HE, "Mars/Olympus")).toBe(gioMay);
    expect(formatCompactInZone("khong-phai-ngay", "America/Chicago")).toBe("");
    expect(formatCompactInZone(null, "America/Chicago")).toBe("");
  });
});

describe("formatRangeInZone", () => {
  test("ghép hai đầu theo cùng một múi giờ", () => {
    expect(formatRangeInZone(MUA_HE, "2026-07-15T15:00:00Z", "America/Chicago"))
      .toBe("09:00 15/07/2026 – 10:00 15/07/2026");
    expect(formatRangeInZone(MUA_HE, "2026-07-15T15:00:00Z", "Asia/Ho_Chi_Minh"))
      .toBe("21:00 15/07/2026 – 22:00 15/07/2026");
  });

  test("thiếu một đầu thì đánh dấu '?', thiếu cả hai thì rỗng", () => {
    expect(formatRangeInZone(MUA_HE, null, "America/Chicago"))
      .toBe("09:00 15/07/2026 – ?");
    expect(formatRangeInZone(null, null, "America/Chicago")).toBe("");
  });
});

describe("getEventTimezone", () => {
  test("ưu tiên start.timeZone rồi mới tới các nguồn khác", () => {
    expect(getEventTimezone({ start: { timeZone: "America/Chicago" } }))
      .toBe("America/Chicago");
    expect(getEventTimezone({ timezone: "America/Denver" })).toBe("America/Denver");
    expect(getEventTimezone({ end: { timeZone: "Europe/London" } })).toBe("Europe/London");
    expect(getEventTimezone({
      start: { timeZone: "America/Chicago" },
      timezone: "Asia/Tokyo",
    })).toBe("America/Chicago");
  });

  test("không có gì thì về mặc định", () => {
    expect(getEventTimezone({})).toBe(FALLBACK_TIMEZONE);
    expect(getEventTimezone(null)).toBe(FALLBACK_TIMEZONE);
    expect(getEventTimezone(undefined)).toBe(FALLBACK_TIMEZONE);
  });
});

describe("getEventInstant", () => {
  test("đọc được cả ba dạng biên sự kiện của Google", () => {
    expect(getEventInstant({ dateTime: MUA_HE })).toBe(MUA_HE);
    expect(getEventInstant({ date: "2026-07-15" })).toBe("2026-07-15");
    expect(getEventInstant(MUA_HE)).toBe(MUA_HE);
    expect(getEventInstant({ dateTime: MUA_HE, date: "2026-07-15" })).toBe(MUA_HE);
  });

  test("rỗng thì trả null", () => {
    expect(getEventInstant(null)).toBeNull();
    expect(getEventInstant(undefined)).toBeNull();
    expect(getEventInstant({})).toBeNull();
    expect(getEventInstant({ dateTime: null, date: null })).toBeNull();
  });

  test("biên dị dạng không được biến thành giờ hiện tại", () => {
    // moment({}) trả về THỜI ĐIỂM HIỆN TẠI chứ không phải "không hợp lệ", nên nếu
    // getEventInstant trả lại chính object thì sự kiện sẽ hiển thị thành giờ bây giờ.
    expect(formatInZone(getEventInstant({}), "America/Chicago")).toBe("");
    expect(formatInZone(getEventInstant({ foo: "bar" }), "America/Chicago")).toBe("");
  });

  test("giữ nguyên Date object", () => {
    const date = new Date(MUA_HE);
    expect(getEventInstant(date)).toBe(date);
  });
});

describe("isKnownTimezone", () => {
  test("phân biệt được tên múi giờ thật", () => {
    expect(isKnownTimezone("America/Chicago")).toBe(true);
    expect(isKnownTimezone("Asia/Ho_Chi_Minh")).toBe(true);
    expect(isKnownTimezone("Mars/Olympus")).toBe(false);
    expect(isKnownTimezone("UTC+7")).toBe(false);
    expect(isKnownTimezone("")).toBe(false);
    expect(isKnownTimezone(undefined)).toBe(false);
  });
});

describe("sameWallClock", () => {
  test("alias của cùng một múi giờ được coi là một", () => {
    expect(sameWallClock("Asia/Saigon", "Asia/Ho_Chi_Minh", MUA_HE)).toBe(true);
    expect(sameWallClock("America/Chicago", "America/Chicago", MUA_HE)).toBe(true);
  });

  test("múi giờ khác hẳn thì không", () => {
    expect(sameWallClock("America/Chicago", "Asia/Ho_Chi_Minh", MUA_HE)).toBe(false);
  });

  test("so theo offset THẬT nên bám đúng mùa DST", () => {
    // Denver có đổi giờ, Phoenix thì không:
    //   mùa đông cả hai đều -07:00  → cùng giờ treo tường
    //   mùa hè  Denver -06:00 vs Phoenix -07:00 → khác
    expect(sameWallClock("America/Denver", "America/Phoenix", MUA_DONG)).toBe(true);
    expect(sameWallClock("America/Denver", "America/Phoenix", MUA_HE)).toBe(false);
  });

  test("múi giờ không hợp lệ thì trả false", () => {
    expect(sameWallClock("Mars/Olympus", "Asia/Ho_Chi_Minh", MUA_HE)).toBe(false);
    expect(sameWallClock("America/Chicago", "", MUA_HE)).toBe(false);
  });
});

describe("getViewerTimezone", () => {
  const originalIntl = global.Intl;

  afterEach(() => {
    global.Intl = originalIntl;
  });

  test("lấy múi giờ trình duyệt khi có", () => {
    global.Intl = {
      DateTimeFormat: () => ({ resolvedOptions: () => ({ timeZone: "America/Chicago" }) }),
    };

    expect(getViewerTimezone()).toBe("America/Chicago");
  });

  test("Intl bị chặn thì rơi về mặc định, không ném lỗi", () => {
    global.Intl = {
      DateTimeFormat: () => {
        throw new Error("blocked");
      },
    };

    expect(getViewerTimezone()).toBe(FALLBACK_TIMEZONE);
  });

  test("Intl trả tên lạ thì cũng rơi về mặc định", () => {
    global.Intl = {
      DateTimeFormat: () => ({ resolvedOptions: () => ({ timeZone: "Mars/Olympus" }) }),
    };

    expect(getViewerTimezone()).toBe(FALLBACK_TIMEZONE);
  });

  test("môi trường thật trả về một múi giờ dùng được", () => {
    expect(isKnownTimezone(getViewerTimezone())).toBe(true);
  });
});

// Đúng danh sách backend trả về (app.py SUPPORTED_TIMEZONES): chỉ VN + Hoa Kỳ.
const SUPPORTED = [
  "Asia/Ho_Chi_Minh",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
];

describe("resolveDefaultTimezone", () => {
  test.each(SUPPORTED)("giữ nguyên múi giờ được hỗ trợ: %s", (zone) => {
    expect(resolveDefaultTimezone(zone, SUPPORTED)).toBe(zone);
  });

  test("các múi giờ Mỹ trước đây bị bỏ sót nay được nhận đúng", () => {
    // Danh sách cứng cũ chỉ có Chicago / New_York / Los_Angeles, nên bốn múi giờ
    // dưới đây rơi hết về giờ Việt Nam — lớp bị tạo lệch tới 13 tiếng.
    ["America/Denver", "America/Phoenix", "America/Anchorage", "Pacific/Honolulu"]
      .forEach((zone) => {
        expect(resolveDefaultTimezone(zone, SUPPORTED)).toBe(zone);
        expect(resolveDefaultTimezone(zone, SUPPORTED)).not.toBe(FALLBACK_TIMEZONE);
      });
  });

  test("tên legacy và tên phụ được quy đổi", () => {
    expect(resolveDefaultTimezone("Asia/Saigon", SUPPORTED)).toBe("Asia/Ho_Chi_Minh");
    expect(resolveDefaultTimezone("US/Central", SUPPORTED)).toBe("America/Chicago");
    expect(resolveDefaultTimezone("US/Arizona", SUPPORTED)).toBe("America/Phoenix");
    expect(resolveDefaultTimezone("US/Hawaii", SUPPORTED)).toBe("Pacific/Honolulu");
    expect(resolveDefaultTimezone("America/Detroit", SUPPORTED)).toBe("America/New_York");
    expect(resolveDefaultTimezone("America/Boise", SUPPORTED)).toBe("America/Denver");
  });

  test("mọi alias đều trỏ tới một múi giờ có trong danh sách hỗ trợ", () => {
    Object.values(TIMEZONE_ALIASES).forEach((target) => {
      expect(SUPPORTED).toContain(target);
    });
  });

  test("múi giờ không hỗ trợ thì về giờ Việt Nam", () => {
    // Sản phẩm chỉ phục vụ VN + Hoa Kỳ, nên thầy cô ở nơi khác lấy mặc định VN.
    ["Europe/London", "Asia/Bangkok", "Asia/Tokyo", "Australia/Sydney"]
      .forEach((zone) => {
        expect(resolveDefaultTimezone(zone, SUPPORTED)).toBe(FALLBACK_TIMEZONE);
      });
  });

  test("đầu vào rỗng hoặc hỏng vẫn cho kết quả dùng được", () => {
    [undefined, null, "", "Mars/Olympus"].forEach((zone) => {
      expect(resolveDefaultTimezone(zone, SUPPORTED)).toBe(FALLBACK_TIMEZONE);
    });
  });

  test("danh sách hỗ trợ rỗng thì về mặc định, không trả undefined", () => {
    expect(resolveDefaultTimezone("America/Denver", [])).toBe(FALLBACK_TIMEZONE);
    expect(resolveDefaultTimezone("America/Denver", undefined)).toBe(FALLBACK_TIMEZONE);
    expect(resolveDefaultTimezone("America/Denver", [null, undefined])).toBe(FALLBACK_TIMEZONE);
  });

  test("danh sách không chứa VN thì lấy mục đầu tiên", () => {
    expect(resolveDefaultTimezone("Europe/London", ["America/Chicago", "America/Denver"]))
      .toBe("America/Chicago");
  });

  test("không tự bịa ra múi giờ ngoài danh sách", () => {
    SUPPORTED.concat(["Europe/London", "Mars/Olympus", ""]).forEach((zone) => {
      expect(SUPPORTED).toContain(resolveDefaultTimezone(zone, SUPPORTED));
    });
  });
});
