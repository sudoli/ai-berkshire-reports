"use strict";

const input = document.querySelector("#search");
const list = document.querySelector("#reports");
const status = document.querySelector("#status");
const more = document.querySelector("#more");
let reports = [];
let matches = [];
let visible = 0;
const batchSize = 60;

function appendBatch() {
  const batch = document.createDocumentFragment();
  for (const report of matches.slice(visible, visible + batchSize)) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = report.url;
    link.textContent = report.title;
    const meta = document.createElement("small");
    meta.textContent = `${report.date || "日期未标注"} · ${report.path}`;
    item.append(link, meta);
    batch.append(item);
  }
  visible = Math.min(visible + batchSize, matches.length);
  list.append(batch);
  status.textContent = matches.length
    ? `共 ${matches.length} 份报告，已显示 ${visible} 份`
    : "未找到匹配的报告，请试试公司名称或股票代码。";
  more.hidden = visible >= matches.length;
}

function filter() {
  const terms = input.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  matches = reports.filter(report =>
    terms.every(term => `${report.title} ${report.path}`.toLocaleLowerCase().includes(term))
  );
  visible = 0;
  list.replaceChildren();
  appendBatch();
}

async function loadReports() {
  try {
    const response = await fetch("reports.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    reports = await response.json();
    input.disabled = false;
    input.addEventListener("input", filter);
    more.addEventListener("click", appendBatch);
    filter();
  } catch (error) {
    console.error("Unable to load report search index", error);
    status.textContent = "搜索目录加载失败，请刷新重试。仍可使用下方最新报告和文件夹目录。";
    more.hidden = true;
  }
}

loadReports();
