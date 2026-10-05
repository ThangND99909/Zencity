// frontend/src/utils/eventTime.js
import moment from "moment-timezone";

/**
 * Hiển thị giờ của sự kiện — giống cách Google Calendar làm.
 *
 * Google Calendar vẽ TOÀN BỘ lưới theo MỘT múi giờ duy nhất: múi giờ của người đang
 * xem. Sự kiện tạo ở múi giờ khác được quy đổi về múi giờ đó để vẽ. Nhờ vậy lưới là
 * một trục thời gian thật và nhìn ra ngay lớp nào chồng lớp nào. Múi giờ riêng của
 * sự kiện chỉ xuất hiện ở màn hình sửa (giống edit view của Google).
 *
 * ⚠️ Trước đây component trộn hai hệ: khối sự kiện được ĐẶT theo giờ trình duyệt
 * (`new Date(...).getHours()`) nhưng chữ in bên trong lại được ĐỊNH DẠNG theo múi giờ
 * của sự kiện. Một lớp 9:00 sáng giờ Chicago bị vẽ ở hàng 21:00 nhưng ghi "09:00".
 * Mọi hàm ở đây đều quy về múi giờ người xem để nhãn luôn khớp vị trí.
 */

export const FALLBACK_TIMEZONE = "Asia/Ho_Chi_Minh";

/**
 * Tên cũ/tên khác của những múi giờ mà sản phẩm hỗ trợ.
 *
 * Trình duyệt có thể khai báo múi giờ bằng tên legacy ('US/Central') hoặc tên phụ
 * ('Asia/Saigon'). Không quy đổi thì chúng bị coi là "không hỗ trợ" và lớp sẽ bị tạo
 * nhầm sang giờ Việt Nam.
 */
export const TIMEZONE_ALIASES = {
  "Asia/Saigon": "Asia/Ho_Chi_Minh",
  "Asia/HoChiMinh": "Asia/Ho_Chi_Minh",
  "US/Eastern": "America/New_York",
  "US/Central": "America/Chicago",
  "US/Mountain": "America/Denver",
  "US/Arizona": "America/Phoenix",
  "US/Pacific": "America/Los_Angeles",
  "US/Alaska": "America/Anchorage",
  "US/Hawaii": "Pacific/Honolulu",
  "America/Detroit": "America/New_York",
  "America/Indiana/Indianapolis": "America/New_York",
  "America/Boise": "America/Denver",
  "America/Juneau": "America/Anchorage",
};

/**
 * Múi giờ mặc định cho một lớp mới: múi giờ của người đang tạo, NẾU sản phẩm hỗ trợ.
 *
 * ⚠️ Trước đây `openPopup` đối chiếu với một danh sách 7 múi giờ viết cứng, tách rời
 * khỏi dropdown thật. Thầy cô ở Denver/Phoenix/Honolulu… không nằm trong danh sách đó
 * nên form mặc định về giờ Việt Nam, trong khi ô giờ họ vừa bấm trên lưới lại là giờ
 * của họ → lớp bị tạo lệch tới 13 tiếng mà không có cảnh báo nào.
 *
 * Nay hàm nhận thẳng `supportedValues` lấy từ chính dropdown (API /timezones), nên hai
 * bên không thể lệch nhau được nữa.
 */
export const resolveDefaultTimezone = (browserTimezone, supportedValues = []) => {
  const supported = supportedValues.filter(Boolean);
  if (!supported.length) return FALLBACK_TIMEZONE;

  const candidate = TIMEZONE_ALIASES[browserTimezone] || browserTimezone;
  if (candidate && supported.includes(candidate)) return candidate;

  // Không hỗ trợ (vd thầy cô ở Bangkok) → giờ Việt Nam nếu có, không thì mục đầu tiên.
  return supported.includes(FALLBACK_TIMEZONE) ? FALLBACK_TIMEZONE : supported[0];
};

/** Tên múi giờ có được moment-timezone biết đến không. */
export const isKnownTimezone = (timezone) =>
  Boolean(timezone && moment.tz.zone(timezone));

/**
 * Múi giờ của người đang xem, lấy từ trình duyệt.
 * Rơi về giờ Việt Nam nếu trình duyệt không cho biết (môi trường cũ, Intl bị chặn).
 */
export const getViewerTimezone = () => {
  try {
    const resolved = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return isKnownTimezone(resolved) ? resolved : FALLBACK_TIMEZONE;
  } catch (error) {
    return FALLBACK_TIMEZONE;
  }
};

/** Múi giờ gắn trên chính sự kiện — Google trả kèm `start.timeZone`. */
export const getEventTimezone = (event) =>
  event?.start?.timeZone ||
  event?.timezone ||
  event?.end?.timeZone ||
  FALLBACK_TIMEZONE;

/**
 * Mốc thời gian thô của một biên sự kiện Google (`{dateTime}` | `{date}` | giá trị trần).
 *
 * Biên là object mà thiếu cả hai field thì trả null chứ KHÔNG trả lại chính object đó:
 * `moment({})` không phải "không hợp lệ" mà là THỜI ĐIỂM HIỆN TẠI, nên một biên dị dạng
 * sẽ âm thầm hiển thị thành giờ bây giờ.
 */
export const getEventInstant = (boundary) => {
  if (!boundary) return null;
  if (typeof boundary === "object" && !(boundary instanceof Date)) {
    return boundary.dateTime || boundary.date || null;
  }
  return boundary;
};

/**
 * Định dạng một mốc thời gian theo `timezone`.
 *
 * `timezone` rỗng hoặc không hợp lệ → dùng luôn giờ máy người xem, KHÔNG rơi về một
 * múi giờ cố định: vị trí của khối sự kiện trong lưới cũng tính theo giờ máy, nên
 * fallback cứng sẽ làm nhãn lệch khỏi hàng mà nó đang nằm.
 *
 * Trả về "" nếu không đọc được, để chỗ gọi không in ra "Invalid date".
 */
export const formatInZone = (value, timezone, pattern = "HH:mm") => {
  if (!value) return "";
  const parsed = moment(value);
  if (!parsed.isValid()) return "";
  return (isKnownTimezone(timezone) ? parsed.tz(timezone) : parsed).format(pattern);
};

/** Kiểu giờ gọn của lưới tháng: "9AM", "9:30AM". */
export const formatCompactInZone = (value, timezone) => {
  if (!value) return "";
  const parsed = moment(value);
  if (!parsed.isValid()) return "";
  const zoned = isKnownTimezone(timezone) ? parsed.tz(timezone) : parsed;
  return zoned.format(zoned.minutes() === 0 ? "hA" : "h:mmA");
};

/** "HH:mm DD/MM/YYYY – HH:mm DD/MM/YYYY" theo một múi giờ. */
export const formatRangeInZone = (
  start,
  end,
  timezone,
  pattern = "HH:mm DD/MM/YYYY"
) => {
  const from = formatInZone(start, timezone, pattern);
  const to = formatInZone(end, timezone, pattern);
  if (!from && !to) return "";
  return `${from || "?"} – ${to || "?"}`;
};

/**
 * Hai múi giờ có đang chỉ cùng một offset tại `reference` không.
 *
 * So tên thôi thì chưa đủ: 'Asia/Saigon' và 'Asia/Ho_Chi_Minh' là một, và người xem ở
 * đúng múi giờ của lớp thì không cần thấy dòng "giờ gốc" lặp lại y hệt. So theo offset
 * thật tại thời điểm đó cũng xử lý luôn chuyện DST.
 */
export const sameWallClock = (zoneA, zoneB, reference) => {
  if (!isKnownTimezone(zoneA) || !isKnownTimezone(zoneB)) return false;
  const at = moment(reference);
  if (!at.isValid()) return zoneA === zoneB;
  return at.clone().tz(zoneA).utcOffset() === at.clone().tz(zoneB).utcOffset();
};
