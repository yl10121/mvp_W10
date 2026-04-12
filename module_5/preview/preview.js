/**
 * 从 preview_data.json 渲染卡片与弹窗（需本地 HTTP 服务打开，见 README）
 */

const grid = document.getElementById("grid");
const overlay = document.getElementById("overlay");
const modalTitle = document.getElementById("modal-title");
const modalSub = document.getElementById("modal-sub");
const modalStrategy = document.getElementById("modal-strategy");
const modalDrafts = document.getElementById("modal-drafts");
const modalEvidence = document.getElementById("modal-evidence");
const closeBtn = document.getElementById("modal-close");
const emptyState = document.getElementById("empty-state");

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function openModal(item) {
  modalTitle.textContent = item.name || item.client_id;
  modalSub.textContent = [item.client_id, item.best_angle].filter(Boolean).join(" · ");
  modalStrategy.innerHTML = esc(item.angle_summary || "—");

  const drafts = item.wechat_drafts || [];
  if (drafts.length === 0) {
    modalDrafts.innerHTML = "<p class=\"draft-text\">（无草稿）</p>";
  } else {
    modalDrafts.innerHTML = drafts
      .map(
        (d, i) => `
      <div class="draft-block">
        <div class="draft-label">草稿 ${i + 1}${d.tone ? ` · ${esc(d.tone)}` : ""}</div>
        <p class="draft-text">${esc(d.message || "")}</p>
      </div>`
      )
      .join("");
  }

  const ev = item.evidence_used || [];
  if (ev.length === 0) {
    modalEvidence.innerHTML = "<p>（无）</p>";
  } else {
    modalEvidence.innerHTML = `<ul class="evidence-list">${ev.map((x) => `<li>${esc(String(x))}</li>`).join("")}</ul>`;
  }

  overlay.classList.add("is-open");
  document.body.style.overflow = "hidden";
  closeBtn.focus();
}

function closeModal() {
  overlay.classList.remove("is-open");
  document.body.style.overflow = "";
}

function renderCards(items) {
  grid.innerHTML = "";
  items.forEach((item, idx) => {
    const card = document.createElement("article");
    card.className = "card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `查看 ${item.name || item.client_id} 详情`);

    card.innerHTML = `
      <div class="card-top">
        <div>
          <p class="card-name">${esc(item.name)}</p>
          <span class="card-id">${esc(item.client_id)}</span>
        </div>
        ${item.vip_tier ? `<span class="vip">${esc(item.vip_tier)}</span>` : ""}
      </div>
      <p class="persona">${esc(item.persona_tag || "")}</p>
      <p class="card-snippet">${esc(item.summary || item.best_angle || "")}</p>
      <p class="card-hint">点击查看策略与草稿</p>
    `;

    const open = () => openModal(item);
    card.addEventListener("click", open);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
    grid.appendChild(card);
  });
}

async function load() {
  try {
    const res = await fetch("preview_data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    const items = await res.json();
    if (!Array.isArray(items) || items.length === 0) {
      emptyState.hidden = false;
      emptyState.textContent = "preview_data.json 为空，请先运行 python3 build_preview_data.py";
      return;
    }
    emptyState.hidden = true;
    renderCards(items);
  } catch (e) {
    emptyState.hidden = false;
    emptyState.innerHTML =
      "无法加载 preview_data.json。<br/>请在本目录执行 <code>python3 build_preview_data.py</code>，再用 <code>python3 -m http.server 8765</code> 打开本页。";
    console.error(e);
  }
}

closeBtn.addEventListener("click", closeModal);
overlay.addEventListener("click", (e) => {
  if (e.target === overlay) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

load();
