// utils/sanitizeDescription.js
export const parseZoomInfo = (rawDescription = "") => {
  if (!rawDescription) return {};

  // 🧹 1️⃣ Làm sạch HTML & giữ lại link
  let description = rawDescription
    .replace(/<br\s*\/?>/gi, "\n") // <br> => xuống dòng
    .replace(/<a[^>]*href="([^"]+)"[^>]*>(.*?)<\/a>/gi, "$1") // lấy link trong thẻ <a>
    .replace(/<\/?[^>]+(>|$)/g, "") // xóa các tag HTML còn lại
    .trim();

  // 🧩 2️⃣ Tìm Zoom link
  const zoomLinkMatch = description.match(/https:\/\/[\w.-]*zoom\.us\/[^\s]+/i);
  const zoomLink = zoomLinkMatch ? zoomLinkMatch[0].trim() : "";

  // 🧩 3️⃣ Tìm Meeting ID
  const meetingMatch = description.match(/Meeting ID[:：]?\s*([0-9 ]+)/i);
  const meetingId = meetingMatch ? meetingMatch[1].replace(/\s+/g, "") : "";

  // 🧩 4️⃣ Tìm Passcode
  const passcodeMatch = description.match(/Passcode[:：]?\s*([A-Za-z0-9]+)/i);
  const passcode = passcodeMatch ? passcodeMatch[1].trim() : "";

  // 🧩 5️⃣ Tìm Program (nếu có)
  const programMatch = description.match(/Program[:：]?\s*([A-Za-z0-9]+)/i);
  const program = programMatch ? programMatch[1].trim() : "";

  // 🧩 6️⃣ Tìm Teacher
  const teacherMatch = description.match(/GV[:：]?\s*(.*?)(?:\n|$)/i) || description.match(/Teacher[:：]?\s*(.*?)(?:\n|$)/i);
  const teacher = teacherMatch ? teacherMatch[1].trim() : "";

  const classnameMatch = description.match(/Classname[:：]?\s*(.*?)(?:\n|$)/i);
  const classname = classnameMatch ? classnameMatch[1].trim() : "";

  return { zoomLink, meetingId, passcode, program, teacher, classname };
};
