const $ = (selector) => document.querySelector(selector);

let language = localStorage.getItem("world-loop-language") === "en" ? "en" : "zh";
let serviceStatusKey = "statusChecking";
let lastHealth = null;
let lastReport = null;

const translations = {
  zh: {
    brandEyebrow: "WORLD LEARNING LOOP · MVP v0.1",
    brandTitle: "传播规律学习引擎 <span>Content Propagation Learning</span>",
    brandSubtitle: "从真实内容传播中学习规律，把证据蒸馏成创作直觉。<br>用证据驱动下一次创作判断。",
    statusDetail: "LOCAL API · LOOPBACK",
    refresh: "刷新状态",
    heroEyebrow: "A RESEARCH WORKBENCH FOR CREATORS",
    heroTitle: "让每一次分析，都留下可追溯的下一步。",
    heroDescription: "从公开样本开始，沿着采集、对照、证据到候选的路径推进。你看到的不是“爆款答案”，而是一条能继续验证的学习记录。",
    observe: "观察",
    compare: "对照",
    validate: "验证",
    evidenceFirst: "Evidence first.",
    evidenceNotice: "这里展示观察、证据与候选，不把单条爆款包装成因果结论。",
    platformCount: "2 个平台",
    objectCount: "8 个核心对象",
    endpointCount: "1 个终点",
    executionEyebrow: "01 / EXECUTION",
    executionTitle: "运行实验 <span>Run an experiment</span>",
    contractProof: "Contract proof",
    safe: "SAFE",
    contractDescription: "用本地 fixture 验证评分、证据链和 Pattern Candidate。<br>在本地验证评分、证据链和候选生成。",
    runFixture: "运行 Fixture Proof",
    liveMetadata: "Live metadata",
    public: "PUBLIC",
    liveDescription: "只采集公开 metadata；两个 seed 不足以产生真实规律。<br>只用于验证采集链路，不代表真实规律。",
    seedUrl: "seed URL",
    runLive: "运行 Live Proof",
    localOnly: "Local-only interface",
    localOnlyDescription: "默认仅监听 127.0.0.1，不提供登录或公网服务。",
    safeByDefault: "SAFE BY DEFAULT",
    pipelineEyebrow: "02 / EVIDENCE PIPELINE",
    pipelineTitle: "从世界到候选 <span>World to candidate</span>",
    platformStep: "平台<br><em>Platforms</em>",
    collectStep: "采集<br><em>Collect</em>",
    compareStep: "对照<br><em>Compare</em>",
    evidenceStep: "证据<br><em>Evidence</em>",
    candidateStep: "候选<br><em>Candidate</em>",
    summaryStatus: "状态",
    summarySamples: "样本",
    summaryGates: "验收门",
    summaryCandidate: "候选",
    waiting: "等待运行",
    emptyTitle: "选择一个实验开始",
    emptyDescription: "运行实验后，这里会显示证据链和候选结果。",
    runtimeEyebrow: "03 / RUNTIME / GOVERNANCE",
    runtimeTitle: "能力与健康 <span>Capabilities & health</span>",
    registryCaption: "Registry-routed · isolated failures",
    pluginHeader: "插件",
    capabilitiesHeader: "能力",
    platformsHeader: "平台",
    healthHeader: "健康",
    footerPrinciples: "Local-first · Evidence-first · Plugin-first · LLM-last",
    footerEndpoint: "Core endpoint: Pattern Candidate",
    statusChecking: "检查中",
    statusReady: "运行正常",
    statusError: "服务异常",
    running: "执行中…",
    fixtureVerified: "Fixture 已验证",
    modeLive: "LIVE METADATA",
    modeFixture: "FIXTURE CONTRACT",
    candidateStatus: "CANDIDATE",
    notFormed: "证据不足",
    acceptanceGates: "验收门",
    candidateBox: "Pattern Candidate",
    evidenceStatus: "证据状态",
    currentEvidence: "当前证据不足，保持开放状态。",
    support: "支持",
    counterexample: "反例",
    controls: "对照",
    collectedSamples: "已采集样本",
    platform: "平台",
    collection: "采集",
    provider: "提供方",
    generic: "通用",
    failures: "次失败",
    noPlugins: "没有已注册插件",
    loadingHealth: "正在读取插件状态",
    operationFailed: "操作失败",
    gate_raw_to_canonical_traceable: "Raw → canonical 可追溯",
    gate_creator_baseline_computed: "Creator baseline 已计算",
    gate_outlier_and_controls_found: "异常样本与对照已找到",
    gate_local_extractor_registered: "本地解构器已注册",
    gate_support_and_counterevidence_present: "支持证据与反证齐备",
    gate_pattern_candidate_traceable: "Pattern Candidate 可追溯",
    gate_live_platform_samples: "Live 平台样本"
  },
  en: {
    brandEyebrow: "WORLD LEARNING LOOP · MVP v0.1",
    brandTitle: "Content Propagation Learning <span>传播规律学习引擎</span>",
    brandSubtitle: "Learn from real content distribution and distill evidence into creative intuition.<br>Make the next creative decision traceable.",
    statusDetail: "LOCAL API · LOOPBACK",
    refresh: "Refresh status",
    heroEyebrow: "A RESEARCH WORKBENCH FOR CREATORS",
    heroTitle: "Every analysis should leave a traceable next step.",
    heroDescription: "Start with public samples and move through collection, comparison, evidence, and candidate formation. This is a verifiable learning record—not a packaged viral answer.",
    observe: "OBSERVE",
    compare: "COMPARE",
    validate: "VALIDATE",
    evidenceFirst: "Evidence first.",
    evidenceNotice: "This surface separates observations, evidence, and candidates instead of turning one viral sample into a causal conclusion.",
    platformCount: "2 platforms",
    objectCount: "8 core objects",
    endpointCount: "1 endpoint",
    executionEyebrow: "01 / EXECUTION",
    executionTitle: "Run an experiment <span>运行实验</span>",
    contractProof: "Contract proof",
    safe: "SAFE",
    contractDescription: "Use a local fixture to verify scoring, evidence, and Pattern Candidate wiring.<br>Verify the contract without touching the outside world.",
    runFixture: "Run Fixture Proof",
    liveMetadata: "Live metadata",
    public: "PUBLIC",
    liveDescription: "Collect public metadata only; two seeds cannot establish a real pattern.<br>This validates collection, not a conclusion.",
    seedUrl: "seed URL",
    runLive: "Run Live Proof",
    localOnly: "Local-only interface",
    localOnlyDescription: "Listens on 127.0.0.1 by default; no login or public service.",
    safeByDefault: "SAFE BY DEFAULT",
    pipelineEyebrow: "02 / EVIDENCE PIPELINE",
    pipelineTitle: "World to candidate <span>从世界到候选</span>",
    platformStep: "Platforms<br><em>平台</em>",
    collectStep: "Collect<br><em>采集</em>",
    compareStep: "Compare<br><em>对照</em>",
    evidenceStep: "Evidence<br><em>证据</em>",
    candidateStep: "Candidate<br><em>候选</em>",
    summaryStatus: "Status",
    summarySamples: "Samples",
    summaryGates: "Gates",
    summaryCandidate: "Candidate",
    waiting: "Waiting",
    emptyTitle: "Choose an experiment to begin",
    emptyDescription: "Run an experiment to populate the evidence chain and candidate result.",
    runtimeEyebrow: "03 / RUNTIME / GOVERNANCE",
    runtimeTitle: "Capabilities & health <span>能力与健康</span>",
    registryCaption: "Registry-routed · isolated failures",
    pluginHeader: "Plugin",
    capabilitiesHeader: "Capabilities",
    platformsHeader: "Platforms",
    healthHeader: "Health",
    footerPrinciples: "Local-first · Evidence-first · Plugin-first · LLM-last",
    footerEndpoint: "Core endpoint: Pattern Candidate",
    statusChecking: "Checking",
    statusReady: "Ready",
    statusError: "Service error",
    running: "Running…",
    fixtureVerified: "Fixture verified",
    modeLive: "LIVE METADATA",
    modeFixture: "FIXTURE CONTRACT",
    candidateStatus: "CANDIDATE",
    notFormed: "Not formed",
    acceptanceGates: "Acceptance gates",
    candidateBox: "Pattern Candidate",
    evidenceStatus: "Evidence status",
    currentEvidence: "Evidence is insufficient; the state remains open.",
    support: "Support",
    counterexample: "Counterexample",
    controls: "Controls",
    collectedSamples: "Collected samples",
    platform: "Platform",
    collection: "Collection",
    provider: "Provider",
    generic: "generic",
    failures: "failures",
    noPlugins: "No registered plugins",
    loadingHealth: "Loading plugin health…",
    operationFailed: "Operation failed",
    gate_raw_to_canonical_traceable: "Raw → canonical traceable",
    gate_creator_baseline_computed: "Creator baseline computed",
    gate_outlier_and_controls_found: "Outlier and controls found",
    gate_local_extractor_registered: "Local extractor registered",
    gate_support_and_counterevidence_present: "Support and counterevidence present",
    gate_pattern_candidate_traceable: "Pattern Candidate traceable",
    gate_live_platform_samples: "Live platform samples"
  }
};

function t(key) {
  return translations[language][key] ?? translations.zh[key] ?? key;
}

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.body.dataset.language = language;
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach((element) => { element.innerHTML = t(element.dataset.i18nHtml); });
  const toggle = $("#language-toggle");
  toggle.textContent = language === "zh" ? "EN" : "中文";
  toggle.setAttribute("aria-pressed", String(language === "en"));
  toggle.setAttribute("aria-label", language === "zh" ? "切换到英文" : "Switch to Chinese");
  $("#service-status").textContent = t(serviceStatusKey);
  if (lastHealth) renderPlugins(lastHealth);
  if (lastReport) renderReport(lastReport);
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setServiceStatus(textKey, kind) {
  const element = $("#service-status");
  serviceStatusKey = textKey;
  element.textContent = t(textKey);
  element.className = `status status-${kind}`;
  element.setAttribute("aria-live", "polite");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));
}

function renderPlugins(payload) {
  const rows = payload.plugins.map(({ manifest, health }) => `
    <tr>
      <td><span class="plugin-id">${escapeHtml(manifest.plugin_id)}</span><span class="plugin-version">v${escapeHtml(manifest.version)}</span></td>
      <td>${manifest.capabilities.map((item) => `<span class="capability">${escapeHtml(item)}</span>`).join("")}</td>
      <td>${escapeHtml(manifest.platforms.length ? manifest.platforms.join(", ") : t("generic"))}</td>
      <td class="health health-${escapeHtml(health.status)}">${escapeHtml(health.status)}${health.failure_count ? ` · ${escapeHtml(health.failure_count)} ${t("failures")}` : ""}</td>
    </tr>`).join("");
  $("#plugin-table").innerHTML = rows || `<tr><td colspan="4" class="table-empty">${t("noPlugins")}</td></tr>`;
}

async function refresh() {
  try {
    const health = await request("/api/health");
    lastHealth = health;
    setServiceStatus("statusReady", "ok");
    renderPlugins(health);
  } catch (error) {
    setServiceStatus("statusError", "error");
    $("#plugin-table").innerHTML = `<tr><td colspan="4" class="table-empty">${escapeHtml(error.message)}</td></tr>`;
  }
}

function setBusy(button, busy) {
  button.disabled = busy;
  if (busy) {
    button.dataset.originalHtml = button.innerHTML;
    button.innerHTML = `<span>${escapeHtml(t("running"))}</span>`;
  } else if (button.dataset.originalHtml) {
    button.innerHTML = button.dataset.originalHtml;
  }
}

function renderSummary(report) {
  const acceptance = report.acceptance || {};
  const values = [
    report.mode === "live" ? t("liveMetadata") : t("fixtureVerified"),
    report.sample_count ?? (report.samples || []).length,
    Object.values(acceptance).filter(Boolean).length,
    report.pattern_candidate ? t("candidateStatus") : t("notFormed"),
  ];
  $("#summary").innerHTML = [t("summaryStatus"), t("summarySamples"), t("summaryGates"), t("summaryCandidate")].map((label, index) => `<div class="summary-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(values[index])}</strong></div>`).join("");
}

function renderGates(acceptance) {
  return Object.entries(acceptance).map(([key, value]) => `<div class="gate ${value ? "gate-pass" : "gate-fail"}"><span>${escapeHtml(t(`gate_${key}`))}</span><b>${value ? "PASS" : "OPEN"}</b></div>`).join("");
}

function renderReport(report) {
  lastReport = report;
  $("#result-mode").textContent = report.mode === "live" ? t("modeLive") : t("modeFixture");
  renderSummary(report);
  const candidate = report.pattern_candidate;
  const samples = (report.samples || []).map((item) => `<tr><td>${escapeHtml(item.platform)}</td><td>${escapeHtml(item.collect?.status || "—")}</td><td>${escapeHtml(item.collect?.plugin_id || "—")}</td></tr>`).join("");
  $("#result-content").className = "result-content";
  $("#result-content").innerHTML = `
    <h3>${escapeHtml(t("acceptanceGates"))}</h3>
    <div class="gate-grid">${renderGates(report.acceptance || {})}</div>
    ${candidate ? `<div class="candidate-box"><strong>${escapeHtml(t("candidateBox"))} · ${escapeHtml(candidate.lifecycle)}</strong><p>${escapeHtml(candidate.statement)}</p><p>${escapeHtml(t("support"))} ${candidate.metrics.support_count} · ${escapeHtml(t("counterexample"))} ${candidate.metrics.counterexample_count} · ${escapeHtml(t("controls"))} ${candidate.metrics.control_count}</p></div>` : `<div class="candidate-box"><strong>${escapeHtml(t("evidenceStatus"))}</strong><p>${escapeHtml(report.note || t("currentEvidence"))}</p></div>`}
    ${samples ? `<h3 style="margin-top:18px">${escapeHtml(t("collectedSamples"))}</h3><table class="samples-table"><thead><tr><th>${escapeHtml(t("platform"))}</th><th>${escapeHtml(t("collection"))}</th><th>${escapeHtml(t("provider"))}</th></tr></thead><tbody>${samples}</tbody></table>` : ""}
  `;
}

async function runFixture() {
  const button = $("#fixture-btn");
  setBusy(button, true);
  try { renderReport(await request("/api/proof/fixture", { method: "POST", body: "{}" })); }
  catch (error) { showError(error); }
  finally { setBusy(button, false); }
}

async function runLive() {
  const button = $("#live-btn");
  setBusy(button, true);
  try {
    renderReport(await request("/api/proof/live", { method: "POST", body: JSON.stringify({ youtube_url: $("#youtube-url").value, bilibili_url: $("#bilibili-url").value }) }));
  } catch (error) { showError(error); }
  finally { setBusy(button, false); }
}

function showError(error) {
  $("#result-mode").textContent = "ERROR";
  $("#result-content").className = "result-content";
  $("#result-content").innerHTML = `<div class="candidate-box"><strong>${escapeHtml(t("operationFailed"))}</strong><p>${escapeHtml(error.message)}</p></div>`;
}

$("#language-toggle").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  localStorage.setItem("world-loop-language", language);
  applyLanguage();
});
$("#refresh-btn").addEventListener("click", refresh);
$("#fixture-btn").addEventListener("click", runFixture);
$("#live-btn").addEventListener("click", runLive);
applyLanguage();
refresh();
