const mockData = {
  status: {
    ok: true,
    data: {
      plugin_name: "astrbot_plugin_majsoul",
      version: "1.5.3",
      plugin_root: "/plugins/astrbot_plugin_majsoul-master",
      data_root: "/data/plugin_data/astrbot_plugin_majsoul",
      webui_enable: true,
      accounts: { total: 2, ok: 1, failed: 1, recent_errors: [] },
      paipus: { total: 2, total_size_bytes: 73800, latest_modified_at: "2026-05-04 12:00:00" },
    },
  },
  accounts: {
    ok: true,
    data: {
      items: [
        { index: 1, uid: "10001", nickname: "PlayerA", username_masked: "pl***01", has_token: true, last_status: "ok", last_error: "", updated_at: "2026-05-04 12:00:00" },
        { index: 2, uid: "10002", nickname: "PlayerB", username_masked: "pl***02", has_token: false, last_status: "failed", last_error: "登录失败", updated_at: "2026-05-04 11:30:00" },
      ],
    },
  },
  paipus: {
    ok: true,
    data: {
      items: [
        { file_name: "260331-demo_a123 - raw.json", game_id: "260331-demo_a123", players: ["东家", "南家", "西家", "北家"], round_count: 8, size_bytes: 41023, modified_at: "2026-05-04 12:00:00" },
        { file_name: "260202-demo_a456 - raw.json", game_id: "260202-demo_a456", players: ["一姬", "二阶堂", "三上", "四宫"], round_count: 10, size_bytes: 32777, modified_at: "2026-05-04 10:20:00" },
      ],
    },
  },
};

const mockRounds = {
  ok: true,
  data: {
    status: "success",
    players: [
      { seat: 0, name: "东家" },
      { seat: 1, name: "南家" },
      { seat: 2, name: "西家" },
      { seat: 3, name: "北家" },
    ],
    rounds: [
      { round_index: 0, round_label: "东1 0本场", result_type: "和了", winner_seats: [0], from_seat: 1, point_text: "3900点", yakus: ["立直", "平和"] },
      { round_index: 1, round_label: "东2 0本场", result_type: "流局", winner_seats: [], from_seat: null, point_text: "", yakus: [] },
    ],
  },
};

const mockDetail = {
  ok: true,
  data: {
    paipu: mockData.paipus.data.items[0],
    rounds: mockRounds.data,
  },
};

const mockRoundResult = {
  ok: true,
  data: {
    status: "success",
    round_index: 0,
    round_label: "东1 0本场",
    start_scores: [25000, 25000, 25000, 25000],
    result_type: "和了",
    score_delta: [5200, -3900, -1000, -300],
    agari: [{ winner_name: "东家", from_name: "南家", win_type: "ron", point_text: "3900点", yakus: ["立直", "平和"] }],
  },
};

const mockTurnState = {
  ok: true,
  data: {
    status: "success",
    round_label: "东1 0本场",
    turn_number: 3,
    players: [
      { seat: 0, name: "东家", closed_hand: ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "東", "東", "白", "白"], melds: [], last_draw: "5m", last_discard: "9m", riichi_declared: false },
      { seat: 1, name: "南家", closed_hand: ["2m", "3m", "4m", "2p", "3p", "4p", "2s", "3s", "4s", "南", "南", "發", "發"], melds: [], last_draw: "6p", last_discard: "1s", riichi_declared: false },
      { seat: 2, name: "西家", closed_hand: ["5m", "5m", "6m", "7m", "7p", "8p", "9p", "5s", "6s", "7s", "西", "西", "中"], melds: [], last_draw: "中", last_discard: "1m", riichi_declared: false },
      { seat: 3, name: "北家", closed_hand: ["1p", "1p", "2p", "3p", "6m", "7m", "8m", "6s", "7s", "8s", "北", "北", "白"], melds: [], last_draw: "2s", last_discard: "3m", riichi_declared: true },
    ],
    focus_trace: [{ turn: 1, phase: "draw", tile: "5m" }, { turn: 1, phase: "discard", tile: "9m" }],
  },
};

const state = {
  tab: "overview",
  status: null,
  accounts: [],
  paipus: [],
  selectedPaipu: null,
  selectedRound: null,
  rounds: [],
  players: [],
};

const el = (id) => document.getElementById(id);
const BRIDGE_CHANNEL = "astrbot-plugin-page";

function createPostMessageBridge() {
  const pending = new Map();
  let contextResolver = null;
  const contextPromise = new Promise((resolve) => {
    contextResolver = resolve;
  });

  function request(action, payload = {}) {
    const requestId = `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    window.parent.postMessage({ channel: BRIDGE_CHANNEL, kind: "request", requestId, action, ...payload }, "*");
    return new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        pending.delete(requestId);
        reject(new Error("请求超时"));
      }, 60000);
      pending.set(requestId, { resolve, reject, timeout });
    });
  }

  window.addEventListener("message", (event) => {
    const message = event.data;
    if (!message || message.channel !== BRIDGE_CHANNEL) return;

    if (message.kind === "context") {
      contextResolver(message.context || {});
      return;
    }

    if (message.kind === "response" && message.requestId) {
      const item = pending.get(message.requestId);
      if (!item) return;
      pending.delete(message.requestId);
      window.clearTimeout(item.timeout);
      if (message.ok) {
        item.resolve(message.data);
      } else {
        item.reject(new Error(message.error || "请求失败"));
      }
    }
  });

  return {
    ready() {
      window.parent.postMessage({ channel: BRIDGE_CHANNEL, kind: "ready" }, "*");
      return contextPromise;
    },
    apiGet(endpoint, params = {}) {
      return request("api:get", { endpoint, params });
    },
    apiPost(endpoint, body = {}) {
      return request("api:post", { endpoint, body });
    },
    download(endpoint, params = {}, filename = "") {
      return request("files:download", { endpoint, params, filename });
    },
  };
}

const mockBridge = {
  async ready() {
    return { pluginName: "astrbot_plugin_majsoul", displayName: "雀魂管理" };
  },
  async apiGet(endpoint) {
    if (endpoint === "status") return mockData.status;
    if (endpoint === "accounts") return mockData.accounts;
    if (endpoint === "paipus") return mockData.paipus;
    if (endpoint === "paipus/detail") return mockDetail;
    if (endpoint === "analysis/rounds") return mockRounds;
    if (endpoint === "analysis/round-result") return mockRoundResult;
    if (endpoint === "analysis/turn-state") return mockTurnState;
    return { ok: true, data: {} };
  },
  async apiPost() {
    return { ok: true, data: {}, message: "本地预览模式" };
  },
  async download() {},
};
const bridge = window.AstrBotPluginPage || (window.parent !== window ? createPostMessageBridge() : mockBridge);

function unwrap(response) {
  if (response && typeof response === "object" && "ok" in response) {
    if (response.ok !== true) {
      throw new Error(response?.message || "请求失败");
    }
    return response.data;
  }
  return response;
}

async function apiGet(endpoint, params = {}) {
  return unwrap(await bridge.apiGet(endpoint, params));
}

async function apiPost(endpoint, body = {}) {
  return unwrap(await bridge.apiPost(endpoint, body));
}

function showNotice(message, type = "info") {
  const node = el("notice");
  node.textContent = message;
  node.classList.toggle("error", type === "error");
  node.classList.remove("hidden");
  clearTimeout(showNotice.timer);
  showNotice.timer = setTimeout(() => node.classList.add("hidden"), 4200);
}

function formatBytes(value) {
  const n = Number(value || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function text(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((node) => {
    node.classList.toggle("active", node.dataset.tab === tab);
  });
  document.querySelectorAll(".view").forEach((node) => {
    node.classList.toggle("active", node.id === `view-${tab}`);
  });
  if (tab === "analysis") renderAnalysisSelector();
}

async function refreshAll() {
  try {
    const [status, accounts, paipus] = await Promise.all([
      apiGet("status"),
      apiGet("accounts"),
      apiGet("paipus", { q: el("paipuSearch").value.trim() }),
    ]);
    state.status = status;
    state.accounts = accounts.items || [];
    state.paipus = paipus.items || [];
    renderOverview();
    renderAccounts();
    renderPaipus();
    renderAnalysisSelector();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderOverview() {
  const status = state.status || {};
  el("metricAccounts").textContent = status.accounts?.total ?? "-";
  el("metricFailedAccounts").textContent = status.accounts?.failed ?? "-";
  el("metricPaipus").textContent = status.paipus?.total ?? "-";
  el("metricSize").textContent = formatBytes(status.paipus?.total_size_bytes || 0);

  const items = [
    ["插件", status.plugin_name],
    ["版本", status.version],
    ["插件目录", status.plugin_root],
    ["数据目录", status.data_root],
    ["最近缓存", status.paipus?.latest_modified_at || "-"],
    ["WebUI", status.webui_enable ? "启用" : "关闭"],
  ];
  el("statusList").innerHTML = items.map(([key, value]) => `<dt>${key}</dt><dd>${text(value)}</dd>`).join("");

  const errors = status.accounts?.recent_errors || [];
  el("recentErrors").innerHTML = errors.length
    ? errors.map((item) => `<div class="round-card"><strong>${text(item.nickname || item.uid)}</strong><p class="muted">${text(item.last_error || item.last_status)}</p></div>`).join("")
    : "暂无异常";
}

function renderAccounts() {
  const tbody = el("accountsTable");
  if (!state.accounts.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty">暂无账号</div></td></tr>`;
    return;
  }
  tbody.innerHTML = state.accounts.map((account) => `
    <tr>
      <td>${account.index}</td>
      <td class="mono">${text(account.uid)}</td>
      <td>${text(account.nickname || "-")}</td>
      <td>${text(account.username_masked)}</td>
      <td><span class="badge ${account.has_token ? "ok" : ""}">${account.has_token ? "有" : "无"}</span></td>
      <td><span class="badge ${account.last_status === "ok" ? "ok" : "bad"}">${text(account.last_status)}</span></td>
      <td>${text(account.updated_at || "-")}</td>
      <td>
        <div class="actions">
          <button class="ghost-button" data-action="test-account" data-id="${account.index}">测试</button>
          <button class="danger-button" data-action="delete-account" data-id="${account.index}">删除</button>
        </div>
      </td>
    </tr>
    ${account.last_error ? `<tr><td></td><td colspan="7" class="muted">${text(account.last_error)}</td></tr>` : ""}
  `).join("");
}

function renderPaipus() {
  const tbody = el("paipusTable");
  if (!state.paipus.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty">暂无牌谱</div></td></tr>`;
    return;
  }
  tbody.innerHTML = state.paipus.map((item) => `
    <tr class="${state.selectedPaipu?.file_name === item.file_name ? "selected" : ""}">
      <td class="mono">${text(item.game_id)}</td>
      <td>${(item.players || []).map(text).join(" / ") || "-"}</td>
      <td>${item.round_count ?? 0}</td>
      <td>${formatBytes(item.size_bytes)}</td>
      <td>${text(item.modified_at || "-")}</td>
      <td>
        <div class="actions">
          <button class="ghost-button" data-action="open-paipu" data-file="${encodeURIComponent(item.file_name)}">打开</button>
          <button class="ghost-button" data-action="download-paipu" data-file="${encodeURIComponent(item.file_name)}">下载</button>
          <button class="danger-button" data-action="delete-paipu" data-file="${encodeURIComponent(item.file_name)}">删除</button>
        </div>
      </td>
    </tr>
  `).join("");
}

async function openPaipu(fileName) {
  try {
    const detail = await apiGet("paipus/detail", { file_name: fileName });
    state.selectedPaipu = detail.paipu;
    state.rounds = detail.rounds?.rounds || [];
    state.players = detail.rounds?.players || [];
    renderPaipuDetail(detail);
    renderPaipus();
    renderAnalysisSelector();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderPaipuDetail(detail) {
  const paipu = detail.paipu;
  const rounds = detail.rounds?.rounds || [];
  el("paipuDetail").innerHTML = `
    <div class="detail-title">${text(paipu.game_id)}</div>
    <dl class="kv-list">
      <dt>文件</dt><dd class="mono">${text(paipu.file_name)}</dd>
      <dt>玩家</dt><dd>${(paipu.players || []).map(text).join(" / ") || "-"}</dd>
      <dt>局数</dt><dd>${paipu.round_count}</dd>
      <dt>大小</dt><dd>${formatBytes(paipu.size_bytes)}</dd>
      <dt>路径</dt><dd class="mono">${text(paipu.raw_json_path)}</dd>
    </dl>
    <div class="round-stack">
      ${rounds.slice(0, 12).map((round) => `
        <article class="round-card">
          <h3>${round.round_index}. ${text(round.round_label)}</h3>
          <p>${text(round.result_type)} ${text(round.point_text || "")}</p>
          <p class="muted">${(round.yakus || []).join(" / ") || "无役种"}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderAnalysisSelector() {
  const select = el("analysisFile");
  select.innerHTML = state.paipus.map((item) => `<option value="${encodeURIComponent(item.file_name)}">${text(item.game_id)}</option>`).join("");
  if (state.selectedPaipu) {
    select.value = encodeURIComponent(state.selectedPaipu.file_name);
  }
}

async function loadAnalysis(fileName) {
  if (!fileName) return;
  try {
    const rounds = await apiGet("analysis/rounds", { file_name: fileName });
    state.selectedPaipu = state.paipus.find((item) => item.file_name === fileName) || { file_name: fileName };
    state.rounds = rounds.rounds || [];
    state.players = rounds.players || [];
    state.selectedRound = null;
    renderRoundList();
    renderSeatOptions();
    el("roundResult").innerHTML = `<div class="empty">选择一局</div>`;
    el("turnState").innerHTML = "";
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderRoundList() {
  const node = el("roundList");
  if (!state.rounds.length) {
    node.innerHTML = `<div class="empty">暂无局数据</div>`;
    return;
  }
  node.innerHTML = state.rounds.map((round) => `
    <button class="round-item ${state.selectedRound?.round_index === round.round_index ? "active" : ""}" data-round="${round.round_index}">
      <strong>${round.round_index}. ${text(round.round_label)}</strong>
      <div class="muted">${text(round.result_type)} ${text(round.point_text || "")}</div>
    </button>
  `).join("");
}

function renderSeatOptions() {
  const seat = el("turnSeat");
  seat.innerHTML = `<option value="-1">无</option>` + state.players.map((player) => `<option value="${player.seat}">${player.seat} ${text(player.name)}</option>`).join("");
}

async function openRound(roundIndex) {
  if (!state.selectedPaipu) return;
  try {
    const result = await apiGet("analysis/round-result", {
      file_name: state.selectedPaipu.file_name,
      round_selector: String(roundIndex),
    });
    state.selectedRound = state.rounds.find((round) => round.round_index === roundIndex);
    renderRoundList();
    renderRoundResult(result);
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderRoundResult(result) {
  const agari = result.agari || [];
  el("roundResult").innerHTML = `
    <article class="round-card">
      <h3>${text(result.round_label)}</h3>
      <dl class="kv-list">
        <dt>结果</dt><dd>${text(result.result_type)}</dd>
        <dt>起始点</dt><dd>${(result.start_scores || []).join(" / ")}</dd>
        <dt>点差</dt><dd>${(result.score_delta || []).join(" / ")}</dd>
      </dl>
      ${agari.map((item) => `
        <div class="round-card">
          <strong>${text(item.winner_name)} ${item.win_type === "tsumo" ? "自摸" : `荣和 ${text(item.from_name)}`}</strong>
          <p>${text(item.point_text)}</p>
          <p class="muted">${(item.yakus || []).join(" / ") || "-"}</p>
        </div>
      `).join("")}
    </article>
  `;
}

function tileClass(tile) {
  const value = String(tile);
  if (value.endsWith("m")) return "man";
  if (value.endsWith("p")) return "pin";
  if (value.endsWith("s")) return "sou";
  return "honor";
}

function tileNode(tile) {
  return `<span class="tile ${tileClass(tile)}">${text(tile)}</span>`;
}

function renderTurnState(result) {
  const players = result.players || [];
  el("turnState").innerHTML = `
    <div class="player-grid">
      ${players.map((player) => `
        <article class="player-card">
          <header>
            <strong>${player.seat} ${text(player.name)}</strong>
            <span class="badge ${player.riichi_declared ? "bad" : ""}">${player.riichi_declared ? "立直" : "未立直"}</span>
          </header>
          <div class="tile-row">${(player.closed_hand || []).map(tileNode).join("")}</div>
          <p class="muted">副露：${(player.melds || []).join(" / ") || "-"}</p>
          <p class="muted">摸牌：${text(player.last_draw || "-")}　弃牌：${text(player.last_discard || "-")}</p>
        </article>
      `).join("")}
    </div>
    ${(result.focus_trace || []).length ? `
      <h2 style="margin: 14px 0 8px">轨迹</h2>
      <div class="trace-list">
        ${result.focus_trace.slice(-80).map((item) => `<div>${Object.entries(item).map(([key, value]) => `${key}: ${text(value)}`).join("　")}</div>`).join("")}
      </div>
    ` : ""}
  `;
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((node) => node.addEventListener("click", () => setTab(node.dataset.tab)));
  el("refreshBtn").addEventListener("click", refreshAll);

  el("showLoginForm").addEventListener("click", () => el("loginForm").classList.remove("hidden"));
  el("hideLoginForm").addEventListener("click", () => el("loginForm").classList.add("hidden"));
  el("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await apiPost("accounts/login", { username: el("loginUsername").value.trim(), password: el("loginPassword").value });
      el("loginPassword").value = "";
      el("loginForm").classList.add("hidden");
      showNotice("账号已更新");
      await refreshAll();
    } catch (error) {
      showNotice(error.message, "error");
    }
  });

  el("accountsTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const id = button.dataset.id;
    try {
      if (button.dataset.action === "test-account") {
        await apiPost("accounts/test", { identifier: id });
        showNotice("账号测试完成");
      }
      if (button.dataset.action === "delete-account" && confirm("删除这个账号？")) {
        await apiPost("accounts/delete", { identifier: id });
        showNotice("账号已删除");
      }
      await refreshAll();
    } catch (error) {
      showNotice(error.message, "error");
    }
  });

  el("showFetchForm").addEventListener("click", () => el("fetchForm").classList.remove("hidden"));
  el("hideFetchForm").addEventListener("click", () => el("fetchForm").classList.add("hidden"));
  el("fetchForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const data = await apiPost("paipus/fetch", { source: el("fetchSource").value.trim() });
      showNotice(data.cache_hit ? "命中缓存" : "牌谱已拉取");
      el("fetchForm").classList.add("hidden");
      await refreshAll();
      if (data.file_name) await openPaipu(data.file_name);
    } catch (error) {
      showNotice(error.message, "error");
    }
  });

  el("paipuSearch").addEventListener("input", () => {
    clearTimeout(el("paipuSearch").timer);
    el("paipuSearch").timer = setTimeout(refreshAll, 280);
  });

  el("paipusTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const fileName = decodeURIComponent(button.dataset.file || "");
    try {
      if (button.dataset.action === "open-paipu") await openPaipu(fileName);
      if (button.dataset.action === "download-paipu") await bridge.download("paipus/download", { file_name: fileName }, fileName);
      if (button.dataset.action === "delete-paipu" && confirm("删除这个牌谱缓存？")) {
        await apiPost("paipus/delete", { file_name: fileName });
        state.selectedPaipu = null;
        el("paipuDetail").innerHTML = `<div class="empty">选择一个牌谱</div>`;
        await refreshAll();
      }
    } catch (error) {
      showNotice(error.message, "error");
    }
  });

  el("analysisFile").addEventListener("change", () => loadAnalysis(decodeURIComponent(el("analysisFile").value)));
  el("roundList").addEventListener("click", (event) => {
    const button = event.target.closest(".round-item");
    if (button) openRound(Number(button.dataset.round));
  });
  el("turnForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedPaipu || !state.selectedRound) {
      showNotice("请先选择牌谱和局", "error");
      return;
    }
    try {
      const result = await apiGet("analysis/turn-state", {
        file_name: state.selectedPaipu.file_name,
        round_selector: String(state.selectedRound.round_index),
        turn_mode: el("turnMode").value,
        turn_number: el("turnNumber").value,
        seat: el("turnSeat").value,
        phase: el("turnPhase").value,
      });
      renderTurnState(result);
    } catch (error) {
      showNotice(error.message, "error");
    }
  });
}

async function boot() {
  const context = await bridge.ready();
  el("subtitle").textContent = context?.displayName || context?.pluginName || "astrbot_plugin_majsoul";
  bindEvents();
  await refreshAll();
  if (state.paipus[0]) {
    await openPaipu(state.paipus[0].file_name);
    await loadAnalysis(state.paipus[0].file_name);
  }
}

boot().catch((error) => showNotice(error.message, "error"));
