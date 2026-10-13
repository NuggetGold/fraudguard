let currentFilter = "ALL";
let searchQuery = "";
let loadedTransactions = [];
let activeModalTxId = null;

function formatCurrency(amount, currency = "RUB") {
  const sym = currency === "RUB" ? "₽" : currency;
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + " " + sym;
}

function formatDateTime(isoString) {
  if (!isoString) return "--";
  const date = new Date(isoString);
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getStatusBadgeHtml(status) {
  switch (status) {
    case "APPROVED":
      return '<span class="status-badge status-approved">Одобрено</span>';
    case "MANUAL_REVIEW":
      return '<span class="status-badge status-manual-review">На проверке</span>';
    case "REJECTED":
      return '<span class="status-badge status-rejected">Заблокировано</span>';
    default:
      return `<span class="status-badge">${status}</span>`;
  }
}

function getScoreBadgeClass(score) {
  if (score >= 70) return "critical";
  if (score >= 45) return "high";
  if (score >= 25) return "medium";
  return "low";
}

function getSeverityBadgeText(severity) {
  switch (severity) {
    case "CRITICAL":
      return "Критический";
    case "HIGH":
      return "Высокий";
    case "MEDIUM":
      return "Средний";
    case "LOW":
      return "Низкий";
    default:
      return severity;
  }
}

function showToast(message, type = "success") {
  const toast = document.getElementById("simulation-toast");
  if (!toast) return;
  toast.className = `toast-notice ${type}`;
  toast.textContent = message;
  toast.classList.remove("hidden");

  clearTimeout(toast.dataset.timeoutId);
  const timeoutId = setTimeout(() => {
    toast.classList.add("hidden");
  }, 5000);
  toast.dataset.timeoutId = timeoutId;
}

async function fetchMetrics() {
  try {
    const res = await fetch("/api/v1/metrics");
    if (!res.ok) throw new Error("Ошибка получения метрик");
    const data = await res.json();

    document.getElementById("metric-total").textContent = data.total_transactions;
    document.getElementById("metric-approved").textContent = data.approved_count;
    document.getElementById("metric-review").textContent = data.review_count;
    document.getElementById("metric-rejected").textContent = data.rejected_count;
    document.getElementById("metric-avg-score").textContent = data.average_risk_score.toFixed(1);
  } catch (err) {
    console.error(err);
  }
}

async function fetchTransactions() {
  try {
    let url = "/api/v1/transactions?limit=100";
    if (currentFilter !== "ALL") {
      url += `&status=${encodeURIComponent(currentFilter)}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error("Ошибка загрузки транзакций");
    loadedTransactions = await res.json();
    applyFilterAndRender();
  } catch (err) {
    console.error(err);
  }
}

function getFilteredTransactions() {
  if (!searchQuery) return loadedTransactions;
  const q = searchQuery.toLowerCase();
  return loadedTransactions.filter((tx) => {
    return (
      tx.transaction_id.toLowerCase().includes(q) ||
      tx.account_id.toLowerCase().includes(q) ||
      tx.recipient_id.toLowerCase().includes(q) ||
      (tx.location?.city && tx.location.city.toLowerCase().includes(q)) ||
      (tx.ip_address && tx.ip_address.toLowerCase().includes(q)) ||
      (tx.device_id && tx.device_id.toLowerCase().includes(q))
    );
  });
}

function applyFilterAndRender() {
  const filtered = getFilteredTransactions();
  renderTransactionsTable(filtered);
}

function renderTransactionsTable(transactions) {
  const tbody = document.getElementById("tx-tbody");
  if (!tbody) return;

  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="8">
          <div class="empty-state">
            <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="2" y="5" width="20" height="14" rx="2"/>
              <line x1="2" y1="10" x2="22" y2="10"/>
            </svg>
            <p>Нет транзакций по заданным критериям</p>
            <span>Измените строку поиска или выберите другой статус</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = transactions
    .map((tx) => {
      const scoreClass = getScoreBadgeClass(tx.risk_score);
      const shortId = tx.transaction_id.slice(0, 8);
      return `
        <tr data-id="${tx.transaction_id}">
          <td class="mono-cell" title="${tx.transaction_id}">#${shortId}</td>
          <td class="mono-cell">${formatDateTime(tx.timestamp)}</td>
          <td>
            <div class="cell-parties">
              <span class="party-from">${tx.account_id}</span>
              <span class="party-to">→ ${tx.recipient_id}</span>
            </div>
          </td>
          <td class="cell-amount">${formatCurrency(tx.amount, tx.currency)}</td>
          <td>
            <div class="cell-location">
              <span class="loc-city">${tx.location.city}</span>
              <span class="loc-ip">${tx.ip_address}</span>
            </div>
          </td>
          <td>
            <span class="score-badge ${scoreClass}">${tx.risk_score}</span>
          </td>
          <td>${getStatusBadgeHtml(tx.status)}</td>
          <td>
            <div class="row-actions">
              <button class="table-btn btn-inspect" data-id="${tx.transaction_id}" type="button">Инфо</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll("tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => {
      openDetailModal(row.dataset.id);
    });
  });
}

function escapeCsvField(val) {
  if (val === null || val === undefined) return "";
  const str = String(val).replace(/"/g, '""');
  if (str.includes(";") || str.includes("\n") || str.includes('"')) {
    return `"${str}"`;
  }
  return str;
}

function exportToCsv() {
  const transactions = getFilteredTransactions();
  if (!transactions || transactions.length === 0) {
    showToast("Нет доступных транзакций для выгрузки в CSV", "warning");
    return;
  }

  const headers = [
    "ID транзакции",
    "Время",
    "Счёт списания",
    "Получатель",
    "Сумма",
    "Валюта",
    "Город",
    "IP-адрес",
    "ID устройства",
    "Риск-скор",
    "Уровень риска",
    "Статус",
    "Нарушения",
    "Решение офицера",
    "Время решения",
  ];

  const rows = transactions.map((tx) => {
    const violationsStr = (tx.violations || [])
      .map((v) => `${v.rule_name} (+${v.risk_score_impact})`)
      .join(" | ");

    return [
      escapeCsvField(tx.transaction_id),
      escapeCsvField(tx.timestamp),
      escapeCsvField(tx.account_id),
      escapeCsvField(tx.recipient_id),
      escapeCsvField(tx.amount),
      escapeCsvField(tx.currency),
      escapeCsvField(tx.location?.city),
      escapeCsvField(tx.ip_address),
      escapeCsvField(tx.device_id),
      escapeCsvField(tx.risk_score),
      escapeCsvField(tx.risk_level),
      escapeCsvField(tx.status),
      escapeCsvField(violationsStr),
      escapeCsvField(tx.reviewer_note || ""),
      escapeCsvField(tx.resolved_at || ""),
    ].join(";");
  });

  const csvContent = "\uFEFF" + [headers.join(";"), ...rows].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestampStr = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);

  link.setAttribute("href", url);
  link.setAttribute("download", `fraudguard_transactions_${timestampStr}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  showToast(`Экспорт завершён: выгружено ${transactions.length} транзакций в CSV`, "success");
}

async function openDetailModal(transactionId) {
  try {
    const res = await fetch(`/api/v1/transactions/${transactionId}`);
    if (!res.ok) throw new Error("Не удалось получить данные о транзакции");
    const tx = await res.json();
    activeModalTxId = tx.transaction_id;

    document.getElementById("modal-tx-id").textContent = tx.transaction_id;
    document.getElementById("modal-amount").textContent = formatCurrency(tx.amount, tx.currency);
    document.getElementById("modal-status-badge").innerHTML = getStatusBadgeHtml(tx.status);

    const scoreClass = getScoreBadgeClass(tx.risk_score);
    const scoreNum = document.getElementById("modal-risk-score");
    scoreNum.textContent = tx.risk_score;
    scoreNum.className = `score-number score-badge ${scoreClass}`;

    const scoreLevel = document.getElementById("modal-risk-level");
    scoreLevel.textContent = getSeverityBadgeText(tx.risk_level);
    scoreLevel.className = `score-level-badge score-badge ${scoreClass}`;

    document.getElementById("modal-timestamp").textContent = formatDateTime(tx.timestamp);
    document.getElementById("modal-account").textContent = tx.account_id;
    document.getElementById("modal-recipient").textContent = tx.recipient_id;
    document.getElementById("modal-ip").textContent = tx.ip_address;
    document.getElementById("modal-device").textContent = tx.device_id;
    document.getElementById("modal-geo").textContent = `${tx.location.city} (${tx.location.latitude.toFixed(4)}, ${tx.location.longitude.toFixed(4)})`;

    const violationsContainer = document.getElementById("modal-violations-list");
    if (!tx.violations || tx.violations.length === 0) {
      violationsContainer.innerHTML = `
        <div class="no-violations">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <span>Нарушений не выявлено — операция признана штатной</span>
        </div>
      `;
    } else {
      violationsContainer.innerHTML = tx.violations
        .map(
          (v) => `
          <div class="violation-card severity-${v.severity}">
            <div class="violation-header">
              <span class="violation-rule-name">${v.rule_name}</span>
              <span class="violation-impact">+${v.risk_score_impact} баллов</span>
            </div>
            <div class="violation-desc">${v.description}</div>
          </div>
        `
        )
        .join("");
    }

    const reviewControls = document.getElementById("modal-review-controls");
    const reviewResolved = document.getElementById("modal-review-resolved");
    const reviewNoteInput = document.getElementById("review-note-input");

    if (tx.status === "MANUAL_REVIEW") {
      reviewControls.classList.remove("hidden");
      reviewResolved.classList.add("hidden");
      reviewNoteInput.value = "";
    } else {
      reviewControls.classList.add("hidden");
      if (tx.reviewer_note) {
        reviewResolved.classList.remove("hidden");
        document.getElementById("modal-resolved-time").textContent = formatDateTime(tx.resolved_at);
        document.getElementById("modal-resolved-note").textContent = tx.reviewer_note;
      } else {
        reviewResolved.classList.add("hidden");
      }
    }

    document.getElementById("modal-backdrop").classList.remove("hidden");
  } catch (err) {
    console.error(err);
    showToast("Ошибка при открытии карточки транзакции", "danger");
  }
}

function closeDetailModal() {
  document.getElementById("modal-backdrop").classList.add("hidden");
  activeModalTxId = null;
}

async function submitReview(action) {
  if (!activeModalTxId) return;

  const noteInput = document.getElementById("review-note-input");
  let note = noteInput.value.trim();
  if (!note) {
    note = action === "APPROVE" ? "Операция подтверждена офицером" : "Операция отклонена офицером безопасности";
  }

  try {
    const res = await fetch(`/api/v1/transactions/${activeModalTxId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action, reviewer_note: note }),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || "Не удалось зафиксировать решение");
    }

    const updated = await res.json();
    showToast(
      action === "APPROVE" ? "Транзакция успешно одобрена" : "Транзакция успешно заблокирована",
      action === "APPROVE" ? "success" : "danger"
    );

    openDetailModal(updated.transaction_id);
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error(err);
    showToast(err.message || "Ошибка при принятии решения", "danger");
  }
}

async function postTransaction(payload) {
  const res = await fetch("/api/v1/transactions/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(errorData.detail || "Ошибка проверки транзакции");
  }
  return await res.json();
}

async function simulateNormal() {
  const btn = document.getElementById("btn-sim-normal");
  btn.disabled = true;
  try {
    const payload = {
      account_id: "ACC-CLIENT-101",
      recipient_id: "RECIP-COFFEE-01",
      amount: 4500.0,
      currency: "RUB",
      ip_address: "178.62.204.15",
      device_id: "DEV-MAC-BOOK-01",
      location: {
        city: "Москва",
        latitude: 55.7558,
        longitude: 37.6173,
      },
    };
    const result = await postTransaction(payload);
    showToast(`Штатный перевод на ${formatCurrency(result.amount)}: Статус ${result.status}`, "success");
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error(err);
    showToast("Сбой симуляции: " + err.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

async function simulateVelocity() {
  const btn = document.getElementById("btn-sim-velocity");
  btn.disabled = true;
  try {
    const account = `ACC-VELOCITY-${Math.floor(100 + Math.random() * 900)}`;
    showToast("Запуск серии из 4 транзакций за короткий интервал...", "warning");

    for (let i = 1; i <= 4; i++) {
      const payload = {
        account_id: account,
        recipient_id: `RECIP-STORE-${i}`,
        amount: 2500.0,
        currency: "RUB",
        ip_address: "94.25.180.44",
        device_id: "DEV-BOT-AGENT",
        location: {
          city: "Санкт-Петербург",
          latitude: 59.9343,
          longitude: 30.3351,
        },
      };
      await postTransaction(payload);
    }

    showToast("Серия завершена: Сработал детектор высокой частоты (Velocity)", "warning");
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error(err);
    showToast("Сбой симуляции серии: " + err.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

async function simulateAnomalousAmount() {
  const btn = document.getElementById("btn-sim-amount");
  btn.disabled = true;
  try {
    const payload = {
      account_id: "ACC-WHALE-999",
      recipient_id: "RECIP-OFFSHORE-99",
      amount: 750000.0,
      currency: "RUB",
      ip_address: "185.120.45.67",
      device_id: "DEV-UNKNOWN-99",
      location: {
        city: "Казань",
        latitude: 55.8304,
        longitude: 49.0661,
      },
    };
    const result = await postTransaction(payload);
    showToast(
      `Критическая сумма ${formatCurrency(result.amount)}: Статус ${result.status} (Риск ${result.risk_score})`,
      "danger"
    );
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error(err);
    showToast("Сбой симуляции: " + err.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

async function simulateGeoTeleport() {
  const btn = document.getElementById("btn-sim-geo");
  btn.disabled = true;
  try {
    const account = `ACC-GEO-${Math.floor(100 + Math.random() * 900)}`;
    const tx1 = {
      account_id: account,
      recipient_id: "RECIP-TERMINAL-01",
      amount: 3200.0,
      currency: "RUB",
      ip_address: "178.62.204.10",
      device_id: "DEV-PHONE-GEO",
      location: {
        city: "Москва",
        latitude: 55.7558,
        longitude: 37.6173,
      },
    };
    await postTransaction(tx1);

    const tx2 = {
      account_id: account,
      recipient_id: "RECIP-TERMINAL-02",
      amount: 8900.0,
      currency: "RUB",
      ip_address: "212.19.0.55",
      device_id: "DEV-PHONE-GEO",
      location: {
        city: "Владивосток",
        latitude: 43.1155,
        longitude: 131.8855,
      },
    };
    const result = await postTransaction(tx2);

    showToast(
      `Гео-аномалия (Москва → Владивосток за 5 секунд): Статус ${result.status}`,
      "danger"
    );
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error(err);
    showToast("Сбой гео-симуляции: " + err.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

function updateClock() {
  const clock = document.getElementById("current-clock");
  if (!clock) return;
  const now = new Date();
  clock.textContent = now.toLocaleTimeString("ru-RU");
}

document.addEventListener("DOMContentLoaded", () => {
  updateClock();
  setInterval(updateClock, 1000);

  fetchMetrics();
  fetchTransactions();

  const filterButtons = document.querySelectorAll("#status-filters .filter-btn");
  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      currentFilter = btn.dataset.status;
      fetchTransactions();
    });
  });

  const searchInput = document.getElementById("tx-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.trim();
      applyFilterAndRender();
    });
  }

  document.getElementById("btn-export-csv")?.addEventListener("click", exportToCsv);

  document.getElementById("btn-refresh")?.addEventListener("click", () => {
    fetchMetrics();
    fetchTransactions();
    showToast("Данные журнала обновлены", "success");
  });

  document.getElementById("btn-sim-normal")?.addEventListener("click", simulateNormal);
  document.getElementById("btn-sim-velocity")?.addEventListener("click", simulateVelocity);
  document.getElementById("btn-sim-amount")?.addEventListener("click", simulateAnomalousAmount);
  document.getElementById("btn-sim-geo")?.addEventListener("click", simulateGeoTeleport);

  document.getElementById("modal-close")?.addEventListener("click", closeDetailModal);
  document.getElementById("modal-backdrop")?.addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") {
      closeDetailModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDetailModal();
    }
  });

  document.getElementById("btn-action-approve")?.addEventListener("click", () => {
    submitReview("APPROVE");
  });

  document.getElementById("btn-action-reject")?.addEventListener("click", () => {
    submitReview("REJECT");
  });
});
