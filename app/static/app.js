"use strict";

const viewLabels = {
  import: "IMPORT",
  overview: "OVERVIEW",
  transactions: "TRANSACTIONS",
  invalid: "INVALID RECORDS",
  rules: "RULES",
};

let dataset = null;
let rules = null;
let currentPage = 0;
let sortField = "timestamp";
let sortAscending = false;

const byId = (id) => document.getElementById(id);

function node(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== null && text !== undefined) element.textContent = String(text);
  return element;
}

function showView(name) {
  const viewName = Object.hasOwn(viewLabels, name) ? name : "import";
  document.querySelectorAll(".view").forEach((view) => {
    const active = view.id === `view-${viewName}`;
    view.classList.toggle("is-visible", active);
    view.hidden = !active;
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    const active = link.hash === `#${viewName}`;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  byId("current-view").textContent = viewLabels[viewName];
}

function setFeedback(message, isError = true) {
  const feedback = byId("import-feedback");
  feedback.textContent = message;
  feedback.hidden = !message;
  feedback.classList.toggle("feedback-success", !isError);
  feedback.classList.toggle("feedback-error", isError);
}

function formatAmount(value, currency) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function metricCard(label, value, note = "") {
  const card = node("article", "metric-card");
  card.append(node("span", "metric-label", label));
  card.append(node("strong", "metric-value", value));
  if (note) card.append(node("span", "metric-note", note));
  return card;
}

function makeSectionHeading(eyebrow, title, description = "") {
  const heading = node("div", "section-heading");
  const text = node("div");
  text.append(node("p", "eyebrow", eyebrow));
  text.append(node("h2", "", title));
  if (description) text.append(node("p", "subtitle", description));
  heading.append(text);
  return heading;
}

function renderImportSummary() {
  const summary = byId("import-summary");
  summary.replaceChildren(
    metricCard("PROCESSED", dataset.metrics.processed, "records in this file"),
    metricCard("VALID", dataset.metrics.valid, "retained normalized records"),
    metricCard("INVALID", dataset.metrics.invalid, "separated for inspection"),
  );
  summary.hidden = false;
}

function renderOverview() {
  const empty = byId("overview-empty");
  const content = byId("overview-content");
  empty.hidden = dataset !== null;
  content.hidden = dataset === null;
  content.replaceChildren();
  if (!dataset) return;

  const label = node("p", "scope-label", "FULL DATASET OVERVIEW");
  const totals = node("div", "metric-grid");
  totals.append(
    metricCard("TOTAL PROCESSED", dataset.metrics.processed, "valid + invalid"),
    metricCard("VALID", dataset.metrics.valid, "retained after duplicate handling"),
    metricCard("INVALID", dataset.metrics.invalid, "includes duplicates"),
  );

  const statusPanel = node("section", "panel data-panel");
  statusPanel.append(makeSectionHeading("NORMALIZED STATUS", "Valid records by status"));
  const statusGrid = node("div", "status-grid");
  Object.entries(dataset.metrics.status_counts).forEach(([status, count]) => {
    const item = node("div", `status-count status-${status.toLowerCase()}`);
    item.append(node("span", "status-indicator", status));
    item.append(node("strong", "", count));
    statusGrid.append(item);
  });
  statusPanel.append(statusGrid);

  const currencyPanel = node("section", "panel data-panel");
  currencyPanel.append(makeSectionHeading(
    "SUCCESSFUL TRANSACTION TOTALS BY CURRENCY",
    "Successful transaction totals by currency",
    "Only valid retained SUCCESS transactions are included. Currencies are never combined.",
  ));
  const currencyGrid = node("div", "currency-grid");
  Object.entries(dataset.metrics.currency_totals_display).forEach(([currency, total]) => {
    const item = node("div", "currency-total");
    item.append(node("span", "currency-code", currency));
    item.append(node("strong", "", `${currency} ${total}`));
    currencyGrid.append(item);
  });
  currencyPanel.append(currencyGrid);

  content.append(label, totals, statusPanel, currencyPanel);
}

function option(select, value, label) {
  select.append(new Option(label, value));
}

function control(labelText, controlElement, className = "") {
  const wrapper = node("label", `filter-control ${className}`.trim());
  wrapper.append(node("span", "", labelText), controlElement);
  return wrapper;
}

function buildSelect(label, values, placeholder) {
  const select = node("select", "control-input");
  select.setAttribute("aria-label", label);
  option(select, "", placeholder);
  values.forEach((value) => option(select, value, value));
  return select;
}

function renderTransactionTable() {
  const content = byId("transactions-content");
  const filters = {
    search: byId("filter-search").value.trim().toLocaleLowerCase(),
    status: byId("filter-status").value,
    currency: byId("filter-currency").value,
    source: byId("filter-source").value,
    from: byId("filter-from").value,
    to: byId("filter-to").value,
  };
  let results = dataset.transactions.filter((entry) => {
    const transaction = entry.normalized;
    const date = transaction.timestamp.slice(0, 10);
    return (!filters.search || transaction.id.toLocaleLowerCase().includes(filters.search))
      && (!filters.status || transaction.status === filters.status)
      && (!filters.currency || transaction.currency === filters.currency)
      && (!filters.source || transaction.source === filters.source)
      && (!filters.from || date >= filters.from)
      && (!filters.to || date <= filters.to);
  });

  results = [...results].sort((left, right) => {
    const a = left.normalized[sortField];
    const b = right.normalized[sortField];
    let order;
    if (sortField === "amount") order = Number(a) - Number(b);
    else order = String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
    if (order === 0) order = left.index - right.index;
    return (sortAscending ? 1 : -1) * order;
  });

  const pageSize = Number(byId("page-size").value);
  const pageCount = Math.max(1, Math.ceil(results.length / pageSize));
  currentPage = Math.min(currentPage, pageCount - 1);
  const start = currentPage * pageSize;
  const visible = results.slice(start, start + pageSize);
  byId("matching-count").textContent = `Matching valid transactions: ${results.length}`;

  const tableRegion = byId("transaction-table-region");
  tableRegion.replaceChildren();
  if (results.length === 0) {
    const empty = node("div", "inline-empty");
    empty.append(node("strong", "", "No matching transactions"));
    empty.append(node("p", "", "Adjust or clear the filters to see valid records."));
    tableRegion.append(empty);
  } else {
    const table = node("table", "data-table");
    const tableHead = node("thead");
    const headerRow = node("tr");
    rules.schema.forEach((field) => {
      const th = node("th");
      th.scope = "col";
      const button = node("button", "sort-button", field.name);
      button.type = "button";
      button.setAttribute("aria-label", `Sort by ${field.name}`);
      button.setAttribute("aria-sort", sortField === field.name
        ? (sortAscending ? "ascending" : "descending")
        : "none");
      if (sortField === field.name) button.append(node("span", "sort-indicator", sortAscending ? " ↑" : " ↓"));
      button.addEventListener("click", () => {
        if (sortField === field.name) sortAscending = !sortAscending;
        else {
          sortField = field.name;
          sortAscending = true;
        }
        currentPage = 0;
        renderTransactionTable();
      });
      th.append(button);
      headerRow.append(th);
    });
    const actionHeader = node("th", "", "Details");
    actionHeader.scope = "col";
    headerRow.append(actionHeader);
    tableHead.append(headerRow);
    table.append(tableHead);

    const body = node("tbody");
    visible.forEach((entry) => {
      const row = node("tr");
      rules.schema.forEach((field) => {
        const cell = node("td");
        const value = entry.normalized[field.name];
        if (field.name === "amount") cell.textContent = formatAmount(value, entry.normalized.currency);
        else if (field.name === "status") {
          const badge = node("span", `badge badge-${String(value).toLowerCase()}`, value);
          cell.append(badge);
        } else {
          cell.textContent = String(value);
        }
        row.append(cell);
      });
      const actionCell = node("td");
      const details = node("button", "text-button", "Inspect");
      details.type = "button";
      details.addEventListener("click", () => showValidDetails(entry));
      actionCell.append(details);
      row.append(actionCell);
      body.append(row);
    });
    table.append(body);
    tableRegion.append(table);
  }

  byId("page-summary").textContent = results.length
    ? `Page ${currentPage + 1} of ${pageCount} · Showing ${start + 1}–${Math.min(start + visible.length, results.length)}`
    : "Page 0 of 0 · Showing 0";
  byId("previous-page").disabled = currentPage <= 0 || results.length === 0;
  byId("next-page").disabled = currentPage >= pageCount - 1 || results.length === 0;
}

function renderTransactions() {
  const empty = byId("transactions-empty");
  const content = byId("transactions-content");
  empty.hidden = dataset !== null;
  content.hidden = dataset === null;
  content.replaceChildren();
  if (!dataset) return;

  const filters = node("section", "panel filters-panel");
  filters.append(makeSectionHeading("FILTERS", "Find transactions"));
  const fields = node("div", "filter-grid");
  const search = node("input", "control-input");
  search.type = "search";
  search.id = "filter-search";
  search.placeholder = "Search transaction ID";
  fields.append(control("Transaction ID", search, "filter-search-field"));
  const uniqueStatuses = [...new Set(Object.values(rules.status_rules.mappings).flatMap(Object.values))];
  const status = buildSelect("Status", uniqueStatuses, "All statuses");
  status.id = "filter-status";
  fields.append(control("Status", status));
  const currency = buildSelect("Currency", rules.currency_rules.supported, "All currencies");
  currency.id = "filter-currency";
  fields.append(control("Currency", currency));
  const source = buildSelect("Source", Object.keys(rules.source_detection.formats), "All sources");
  source.id = "filter-source";
  fields.append(control("Source", source));
  const from = node("input", "control-input");
  from.type = "date";
  from.id = "filter-from";
  fields.append(control("From date", from));
  const to = node("input", "control-input");
  to.type = "date";
  to.id = "filter-to";
  fields.append(control("To date", to));
  filters.append(fields);
  const filterActions = node("div", "filter-actions");
  const clear = node("button", "button button-secondary", "Clear filters");
  clear.type = "button";
  clear.addEventListener("click", () => {
    byId("filter-search").value = "";
    byId("filter-status").value = "";
    byId("filter-currency").value = "";
    byId("filter-source").value = "";
    byId("filter-from").value = "";
    byId("filter-to").value = "";
    currentPage = 0;
    sortField = "timestamp";
    sortAscending = false;
    renderTransactionTable();
  });
  filterActions.append(clear);
  filters.append(filterActions);

  const resultsPanel = node("section", "panel results-panel");
  const resultsHeader = node("div", "results-heading");
  const resultInfo = node("div");
  resultInfo.append(node("p", "eyebrow", "VALID NORMALIZED RECORDS"));
  resultInfo.append(node("h2", "", "Transactions"));
  resultInfo.append(node("p", "scope-label", "Matching valid transactions"));
  resultInfo.append(node("p", "subtitle", "Filters affect this list only; overview metrics always use the full dataset."));
  resultsHeader.append(resultInfo);
  const pageSizer = node("label", "page-size-control");
  pageSizer.append(node("span", "", "Rows"));
  const pageSize = node("select", "control-input");
  pageSize.id = "page-size";
  pageSize.setAttribute("aria-label", "Rows per page");
  [10, 25, 50].forEach((size) => option(pageSize, size, size));
  pageSize.addEventListener("change", () => {
    currentPage = 0;
    renderTransactionTable();
  });
  pageSizer.append(pageSize);
  resultsHeader.append(pageSizer);
  resultsPanel.append(resultsHeader);
  const matchingCount = node("p", "matching-count", "");
  matchingCount.id = "matching-count";
  resultsPanel.append(matchingCount);
  const tableRegion = node("div", "table-scroll");
  tableRegion.id = "transaction-table-region";
  resultsPanel.append(tableRegion);
  const pagination = node("div", "pagination");
  const pageSummary = node("span", "page-summary", "");
  pageSummary.id = "page-summary";
  const pageActions = node("div", "pagination-actions");
  const previous = node("button", "button button-secondary", "← Previous");
  previous.id = "previous-page";
  previous.type = "button";
  previous.addEventListener("click", () => {
    currentPage -= 1;
    renderTransactionTable();
  });
  const next = node("button", "button button-secondary", "Next →");
  next.id = "next-page";
  next.type = "button";
  next.addEventListener("click", () => {
    currentPage += 1;
    renderTransactionTable();
  });
  pageActions.append(previous, next);
  pagination.append(pageSummary, pageActions);
  resultsPanel.append(pagination);

  content.append(filters, resultsPanel);
  ["filter-search", "filter-status", "filter-currency", "filter-source", "filter-from", "filter-to"]
    .forEach((id) => byId(id).addEventListener("input", () => {
      currentPage = 0;
      renderTransactionTable();
    }));
  renderTransactionTable();
}

function detailsBlock(title, value) {
  const section = node("section", "detail-block");
  section.append(node("h3", "", title));
  const pre = node("pre", "json-view", JSON.stringify(value, null, 2));
  section.append(pre);
  return section;
}

function openDialog(eyebrow, title, blocks) {
  byId("dialog-eyebrow").textContent = eyebrow;
  byId("dialog-title").textContent = title;
  const content = byId("dialog-content");
  content.replaceChildren(...blocks);
  byId("record-dialog").showModal();
}

function showValidDetails(entry) {
  const transaction = entry.normalized;
  const normalized = {};
  rules.schema.forEach(({ name }) => { normalized[name] = transaction[name]; });
  const transformations = node("section", "detail-block");
  transformations.append(node("h3", "", "Transformations applied"));
  const list = node("ul", "reason-list");
  entry.transformations.forEach((explanation) => list.append(node("li", "", explanation)));
  transformations.append(list);
  openDialog(
    `VALID RECORD · INPUT POSITION ${entry.position}`,
    `Transaction ${transaction.id}`,
    [
      detailsBlock(`Normalized record · ${entry.position} fields`, normalized),
      detailsBlock("Original record", entry.original),
      detailsBlock("Detected source", { source: transaction.source }),
      transformations,
    ],
  );
}

function renderInvalidRecords() {
  const empty = byId("invalid-empty");
  const content = byId("invalid-content");
  const records = dataset?.invalid_records ?? [];
  empty.hidden = dataset === null || records.length > 0;
  content.hidden = dataset === null || records.length === 0;
  content.replaceChildren();
  if (!dataset || records.length === 0) return;

  const panel = node("section", "panel invalid-panel");
  panel.append(makeSectionHeading(
    "REJECTED INPUT",
    `${records.length} invalid ${records.length === 1 ? "record" : "records"}`,
    "Each original entry is retained with the validation reasons that could be determined.",
  ));
  const list = node("div", "invalid-list");
  records.forEach((record) => {
    const card = node("article", "invalid-card");
    const top = node("div", "invalid-card-top");
    const identity = node("div");
    identity.append(node("span", "record-position", `INPUT POSITION ${record.position}`));
    identity.append(node("h3", "", record.identifier || "Identifier unavailable"));
    top.append(identity);
    top.append(node("span", "source-tag", record.source || "Source unavailable"));
    card.append(top);
    if (record.source_candidates.length > 1) {
      card.append(node("p", "source-candidates", `Candidate formats: ${record.source_candidates.join(", ")}`));
    }
    const reasons = node("ul", "reason-list");
    record.errors.forEach((reason) => reasons.append(node("li", "", reason)));
    card.append(reasons);
    const inspect = node("button", "text-button", "Inspect original record →");
    inspect.type = "button";
    inspect.addEventListener("click", () => showInvalidDetails(record));
    card.append(inspect);
    list.append(card);
  });
  panel.append(list);
  content.append(panel);
}

function showInvalidDetails(record) {
  const sourceDetails = {
    detected_source: record.source,
    candidate_formats: record.source_candidates,
    identifier: record.identifier,
    zero_based_index: record.index,
    one_based_input_position: record.position,
  };
  const errors = node("section", "detail-block");
  errors.append(node("h3", "", "Validation reasons"));
  const list = node("ul", "reason-list");
  record.errors.forEach((reason) => list.append(node("li", "", reason)));
  errors.append(list);
  openDialog(
    `INVALID RECORD · INPUT POSITION ${record.position}`,
    record.identifier ? `Record ${record.identifier}` : "Record inspection",
    [
      detailsBlock("Detection and position", sourceDetails),
      detailsBlock("Original record", record.original),
      errors,
    ],
  );
}

function displayRuleValue(value) {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function renderRules() {
  const empty = byId("rules-empty");
  const content = byId("rules-content");
  if (!rules) {
    empty.hidden = false;
    content.hidden = true;
    return;
  }
  empty.hidden = true;
  content.hidden = false;
  content.replaceChildren();

  const policy = node("p", "scope-label", "READ-ONLY · LIVE PROCESSING CONFIGURATION");
  content.append(policy);
  Object.entries(rules).forEach(([sectionName, sectionValue]) => {
    const panel = node("section", "panel rule-panel");
    panel.append(makeSectionHeading("CONFIGURATION", sectionName.replaceAll("_", " ")));
    const entries = node("dl", "rule-list");
    Object.entries(sectionValue).forEach(([key, value]) => {
      const row = node("div", "rule-row");
      row.append(node("dt", "", key.replaceAll("_", " ")));
      row.append(node("dd", "", displayRuleValue(value)));
      entries.append(row);
    });
    panel.append(entries);
    content.append(panel);
  });
}

async function loadRules() {
  try {
    const response = await fetch("/api/rules");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not load processing rules.");
    rules = result;
    renderRules();
  } catch (error) {
    byId("rules-empty").querySelector("h2").textContent = "Rules could not be loaded";
    byId("rules-empty").querySelector("p").textContent = error.message;
    renderRules();
  }
}

async function processSelectedFile() {
  const file = byId("json-file").files[0];
  if (!file) return;

  const button = byId("process-file");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = "Processing…";
  setFeedback("");
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/import", { method: "POST", body: formData });
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`);
    }
    if (!response.ok) throw new Error(result.error || `Import failed (HTTP ${response.status}).`);

    dataset = result;
    currentPage = 0;
    sortField = "timestamp";
    sortAscending = false;
    byId("dataset-chip").textContent = result.filename;
    setFeedback(
      `${result.filename} processed: ${result.processed} total, ${result.valid_count} valid, ${result.invalid_count} invalid.`,
      false,
    );
    renderImportSummary();
    renderOverview();
    renderTransactions();
    renderInvalidRecords();
  } catch (error) {
    setFeedback(`${error.message} The previously loaded dataset, if any, is unchanged.`);
  } finally {
    button.disabled = !byId("json-file").files.length;
    button.removeAttribute("aria-busy");
    button.innerHTML = 'Process dataset <span aria-hidden="true">→</span>';
  }
}

byId("json-file").addEventListener("change", (event) => {
  const [file] = event.target.files;
  byId("selected-file").textContent = file ? file.name : "No file selected";
  byId("process-file").disabled = !file;
  setFeedback("");
});
byId("process-file").addEventListener("click", processSelectedFile);
byId("dialog-close").addEventListener("click", () => byId("record-dialog").close());
window.addEventListener("hashchange", () => showView(location.hash.slice(1)));
showView(location.hash.slice(1));
loadRules();
