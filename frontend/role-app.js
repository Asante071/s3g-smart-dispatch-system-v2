const S3G_API = "/api";
const S3G_DEMO_PASSWORD = "DispatchDemo!2026";
const s3gState = { token: sessionStorage.getItem("s3gToken"), user: null };

const s3g = (id) => document.getElementById(id);
const s3gElements = {
    loginView: s3g("loginView"), appView: s3g("roleAppView"), loginForm: s3g("companyLoginForm"),
    loginError: s3g("loginError"), email: s3g("companyEmail"), password: s3g("companyPassword"),
    pageEyebrow: s3g("pageEyebrow"), pageTitle: s3g("pageTitle"), pageSubtitle: s3g("pageSubtitle"),
    roleBadge: s3g("roleBadge"), signedInName: s3g("signedInName"), signedInEmail: s3g("signedInEmail"),
    connection: s3g("apiStatus"), message: s3g("appMessage"), portalNav: s3g("portalNav"),
    operationsNav: s3g("operationsNav"),
};
const s3gCharts = {};

function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = value ?? "";
    return node.innerHTML;
}

function setMessage(message = "", error = false) {
    s3gElements.message.textContent = message;
    s3gElements.message.style.color = error ? "var(--s3g-danger)" : "var(--s3g-good)";
}

function setConnection(online) {
    s3gElements.connection.textContent = online ? "● API connected" : "● API unavailable";
    s3gElements.connection.className = `s3g-connection ${online ? "online" : "offline"}`;
}

async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (s3gState.token) headers.Authorization = `Bearer ${s3gState.token}`;
    if (options.body) headers["Content-Type"] = "application/json";
    const response = await fetch(`${S3G_API}${path}`, { ...options, headers });
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && path !== "/auth/login") {
        logout("Your session has expired. Please sign in again.");
        throw new Error("Your session has expired.");
    }
    if (!response.ok) throw new Error(body.detail || "The request could not be completed.");
    return body;
}

function metric(label, value) {
    return `<article class="s3g-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>`;
}

function priorityPill(priority) {
    return `<span class="s3g-priority-pill s3g-priority-${escapeHtml((priority || "").toLowerCase())}">${escapeHtml(priority)}</span>`;
}

function statusPill(status) {
    const statusClass = status === "IN_PROGRESS" ? "s3g-status-progress" : `s3g-status-${(status || "").toLowerCase()}`;
    return `<span class="s3g-status-pill ${statusClass}">${escapeHtml((status || "").replace("_", " "))}</span>`;
}

function employeeStatusUpdate(status) {
    const updates = {
        OPEN: "Queued for triage",
        IN_PROGRESS: "A technician is working on it",
        RESOLVED: "Resolution recorded",
        CLOSED: "Request closed",
    };
    return updates[status] || "Status updated";
}

function showPortal() {
    s3gElements.loginView.hidden = true;
    s3gElements.appView.hidden = false;
    const { user } = s3gState;
    const roleLabel = user.role.charAt(0) + user.role.slice(1).toLowerCase();
    s3gElements.roleBadge.textContent = `Account: ${roleLabel}`;
    s3gElements.signedInName.textContent = user.display_name;
    s3gElements.signedInEmail.textContent = user.email;
    document.querySelectorAll(".s3g-role-view").forEach((view) => { view.hidden = true; });
    const content = {
        EMPLOYEE: ["EMPLOYEE PORTAL", "My incident portal", "Report incidents and track the status of your own requests.", "My portal"],
        TECHNICIAN: ["TECHNICIAN DASHBOARD", "My dispatch queue", "Manage assigned incidents, workload and SLA-risk checks.", "My queue"],
        SUPERVISOR: ["SUPERVISOR DASHBOARD", "Dispatch oversight", "Monitor all incidents, team workload, SLA risk and dispatch decisions.", "Operations dashboard"],
    }[user.role];
    s3gElements.pageEyebrow.textContent = content[0];
    s3gElements.pageTitle.textContent = content[1];
    s3gElements.pageSubtitle.textContent = content[2];
    s3gElements.portalNav.textContent = content[3];
    s3gElements.portalNav.href = `#${user.role.toLowerCase()}Portal`;
    s3gElements.operationsNav.hidden = user.role !== "SUPERVISOR";
    s3g(`${user.role.toLowerCase()}Portal`).hidden = false;
}

async function loadDashboard() {
    if (!s3gState.user) return;
    try {
        setMessage();
        if (s3gState.user.role === "EMPLOYEE") renderEmployee(await api("/dashboard/employee"));
        if (s3gState.user.role === "TECHNICIAN") renderTechnician(await api("/dashboard/technician"));
        if (s3gState.user.role === "SUPERVISOR") renderSupervisor(await api("/dashboard/supervisor"));
        setConnection(true);
    } catch (error) {
        setConnection(false);
        setMessage(error.message, true);
    }
}

function renderEmployee(data) {
    s3g("employeeTickets").innerHTML = data.tickets.map((ticket) => `<tr><td>#${ticket.id}</td><td>${escapeHtml(ticket.issue)}</td><td>${priorityPill(ticket.risk)}</td><td>${statusPill(ticket.status)}</td><td>${escapeHtml(employeeStatusUpdate(ticket.status))}</td></tr>`).join("");
    s3g("employeeEmpty").hidden = data.tickets.length !== 0;
}

function renderTechnician(data) {
    s3g("technicianMetrics").innerHTML = [metric("Assigned", data.summary.assigned), metric("In progress", data.summary.in_progress), metric("SLA at risk", data.summary.at_risk), metric("Workload", data.workload), metric("Availability", data.availability ? "Available" : "Unavailable")].join("");
    s3g("technicianTickets").innerHTML = data.tickets.map((ticket) => `<tr>
        <td>#${ticket.id}</td><td>${escapeHtml(ticket.issue)}</td><td>${priorityPill(ticket.risk)}</td><td>${escapeHtml(ticket.sla_remaining)} hrs</td>
        <td><select class="s3g-status-select" data-status-for="${ticket.id}">${["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"].map((value) => `<option value="${value}" ${ticket.status === value ? "selected" : ""}>${value.replace("_", " ")}</option>`).join("")}</select></td>
        <td><button class="s3g-inline-button" type="button" data-update-ticket="${ticket.id}">Save</button></td></tr>`).join("");
    s3g("technicianEmpty").hidden = data.tickets.length !== 0;
    const workload = document.querySelector('#slaPredictionForm [name="engineer_workload"]');
    if (workload) workload.value = data.workload;
    const predictionTicket = s3g("predictionTicket");
    const predictionButton = s3g("slaPredictionForm").querySelector("button[type=submit]");
    predictionTicket.innerHTML = data.tickets.map((ticket) => `<option value="${ticket.id}">#${ticket.id} · ${escapeHtml(ticket.issue)}</option>`).join("");
    predictionTicket.disabled = data.tickets.length === 0;
    predictionButton.disabled = data.tickets.length === 0;
}

function renderSupervisor(data) {
    const analytics = data.analytics;
    const availableEngineers = data.engineer_workload.filter((engineer) => engineer.availability).length;
    s3g("supervisorMetrics").innerHTML = [
        metric("All incidents", analytics.total_incidents),
        metric("Open", analytics.open_incidents),
        metric("Critical", analytics.critical_incidents),
        metric("SLA at risk", analytics.at_risk_incidents),
        metric("Available engineers", availableEngineers),
    ].join("");
    const technicians = [...new Set([
        ...data.engineer_workload.map((engineer) => engineer.name),
        ...data.tickets.map((ticket) => ticket.engineer).filter((name) => name && name !== "Unassigned"),
        "Unassigned",
    ])];
    s3g("supervisorTickets").innerHTML = data.tickets.map((ticket) => `<tr>
        <td>#${ticket.id}</td><td>${escapeHtml(ticket.issue)}</td><td>${priorityPill(ticket.risk)}</td><td>${statusPill(ticket.status)}</td><td>${escapeHtml(ticket.engineer || "Unassigned")}</td><td>${escapeHtml(ticket.sla_remaining)} hrs</td>
        <td><div class="s3g-dispatch-control"><select data-assignee-for="${ticket.id}">${technicians.map((name) => `<option value="${escapeHtml(name)}" ${ticket.engineer === name ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}</select><button class="s3g-inline-button" type="button" data-assign-ticket="${ticket.id}">Assign</button></div></td></tr>`).join("");
    s3g("supervisorEmpty").hidden = data.tickets.length !== 0;
    s3g("workloadTable").innerHTML = data.engineer_workload.map((engineer) => `<tr><td>${escapeHtml(engineer.name)}</td><td>${escapeHtml(engineer.workload)}</td><td>${engineer.assigned_incidents}</td><td>${engineer.availability ? "Available" : "Unavailable"}</td></tr>`).join("");
    s3g("workloadEmpty").hidden = data.engineer_workload.length !== 0;
    s3g("predictionHistory").innerHTML = data.recent_predictions.map((prediction) => `<tr><td>${escapeHtml(new Date(prediction.created_at).toLocaleString())}</td><td>${escapeHtml(prediction.priority)} · ${escapeHtml(prediction.category)}</td><td>${(prediction.breach_probability * 100).toFixed(1)}%</td><td>${escapeHtml(prediction.risk_level)}</td></tr>`).join("");
    s3g("predictionEmpty").hidden = data.recent_predictions.length !== 0;
    renderOperationalInsights(data);
    renderSupervisorCharts(data);
}

function renderOperationalInsights(data) {
    const tickets = data.tickets;
    const unassigned = tickets.filter((ticket) => !ticket.engineer || ticket.engineer === "Unassigned").length;
    const atRisk = tickets.filter((ticket) => ticket.status !== "CLOSED" && ticket.sla_remaining <= 2).length;
    const unavailable = data.engineer_workload.filter((engineer) => !engineer.availability).length;
    s3g("operationalInsights").innerHTML = [
        `<li><strong>${unassigned}</strong> incident${unassigned === 1 ? "" : "s"} awaiting assignment.</li>`,
        `<li><strong>${atRisk}</strong> open incident${atRisk === 1 ? "" : "s"} with two or fewer SLA hours remaining.</li>`,
        `<li><strong>${unavailable}</strong> engineer profile${unavailable === 1 ? " is" : "s are"} currently unavailable.</li>`,
    ].join("");
}

function upsertChart(id, type, labels, datasets) {
    if (typeof Chart !== "function") return;
    const canvas = s3g(id);
    if (!canvas) return;
    if (s3gCharts[id]) {
        s3gCharts[id].data.labels = labels;
        s3gCharts[id].data.datasets = datasets;
        s3gCharts[id].update();
        return;
    }
    s3gCharts[id] = new Chart(canvas, {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#dceaff" } } },
            scales: type === "doughnut" ? {} : {
                x: { ticks: { color: "#c2d3ec" }, grid: { color: "#2b405f" } },
                y: { beginAtZero: true, ticks: { color: "#c2d3ec", precision: 0 }, grid: { color: "#2b405f" } },
            },
        },
    });
}

function renderSupervisorCharts(data) {
    const priorities = ["LOW", "AMBER", "HIGH"];
    const priorityCounts = priorities.map((priority) => data.tickets.filter((ticket) => ticket.risk === priority).length);
    upsertChart("priorityChart", "doughnut", ["Low", "Moderate", "High"], [{
        data: priorityCounts, backgroundColor: ["#3ecf8e", "#f5b942", "#fb7185"], borderWidth: 0,
    }]);

    const statuses = Object.keys(data.analytics.status_breakdown);
    upsertChart("statusChart", "bar", statuses.map((status) => status.replace("_", " ")), [{
        label: "Incidents", data: statuses.map((status) => data.analytics.status_breakdown[status]), backgroundColor: "#53a2ff", borderRadius: 6,
    }]);

    const openTickets = data.tickets.filter((ticket) => ticket.status !== "CLOSED");
    const breached = openTickets.filter((ticket) => ticket.sla_remaining <= 0).length;
    const atRisk = openTickets.filter((ticket) => ticket.sla_remaining > 0 && ticket.sla_remaining <= 2).length;
    const onTrack = openTickets.filter((ticket) => ticket.sla_remaining > 2).length;
    upsertChart("slaRiskChart", "doughnut", ["Breached", "At risk (≤2h)", "More than 2h"], [{
        data: [breached, atRisk, onTrack], backgroundColor: ["#fb7185", "#f5b942", "#3ecf8e"], borderWidth: 0,
    }]);

    upsertChart("workloadChart", "bar", data.engineer_workload.map((engineer) => engineer.name), [
        { label: "Profile workload", data: data.engineer_workload.map((engineer) => engineer.workload), backgroundColor: "#53a2ff", borderRadius: 6 },
        { label: "Assigned incidents", data: data.engineer_workload.map((engineer) => engineer.assigned_incidents), backgroundColor: "#3ecf8e", borderRadius: 6 },
    ]);
}

async function signIn(event) {
    event.preventDefault();
    s3gElements.loginError.textContent = "";
    const submit = s3gElements.loginForm.querySelector("button[type=submit]");
    submit.disabled = true;
    try {
        const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: s3gElements.email.value, password: s3gElements.password.value }) });
        s3gState.token = result.access_token;
        s3gState.user = result.user;
        sessionStorage.setItem("s3gToken", s3gState.token);
        showPortal();
        await loadDashboard();
    } catch (error) { s3gElements.loginError.textContent = error.message; } finally { submit.disabled = false; }
}

function logout(message = "") {
    sessionStorage.removeItem("s3gToken");
    s3gState.token = null;
    s3gState.user = null;
    s3gElements.appView.hidden = true;
    s3gElements.loginView.hidden = false;
    s3gElements.password.value = "";
    s3gElements.loginError.textContent = message;
}

async function submitIncident(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const title = formData.get("title");
    if (typeof title !== "string" || !title.trim()) {
        setMessage("Enter an incident title before submitting.", true);
        return;
    }
    try {
        // FormData avoids the HTMLFormElement.title property collision and
        // sends the complete title exactly as entered.
        const ticket = await api("/tickets", { method: "POST", body: JSON.stringify({ title, priority: formData.get("priority") }) });
        form.reset(); setMessage(`Incident #${ticket.id} submitted successfully.`); await loadDashboard();
    } catch (error) { setMessage(error.message, true); }
}

async function updateTicketStatus(button) {
    const id = button.dataset.updateTicket;
    const select = document.querySelector(`[data-status-for="${id}"]`);
    button.disabled = true;
    try { await api(`/tickets/${id}/status`, { method: "PUT", body: JSON.stringify({ status: select.value }) }); setMessage(`Incident #${id} updated.`); await loadDashboard(); }
    catch (error) { setMessage(error.message, true); } finally { button.disabled = false; }
}

async function assignTicket(button) {
    const id = button.dataset.assignTicket;
    const select = document.querySelector(`[data-assignee-for="${id}"]`);
    button.disabled = true;
    try { await api(`/tickets/${id}/assign`, { method: "PUT", body: JSON.stringify({ engineer: select.value }) }); setMessage(`Incident #${id} assigned to ${select.value}.`); await loadDashboard(); }
    catch (error) { setMessage(error.message, true); } finally { button.disabled = false; }
}

async function submitPrediction(event) {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget));
    ["ticket_id", "complexity", "engineer_experience", "engineer_workload", "previous_incidents", "sla_allowed_hours", "incident_age_hours", "sla_remaining_hours"].forEach((key) => { payload[key] = Number(payload[key]); });
    const result = s3g("predictionResult");
    try {
        const prediction = await api("/predict", { method: "POST", body: JSON.stringify(payload) });
        const high = prediction.risk_level === "HIGH RISK";
        result.hidden = false; result.className = `s3g-prediction-result ${high ? "high-risk" : "low-risk"}`;
        result.innerHTML = `<strong>${escapeHtml(prediction.risk_level)}</strong><br>${(prediction.breach_probability * 100).toFixed(1)}% predicted SLA-breach probability.`;
    } catch (error) { setMessage(error.message, true); }
}

async function submitDispatch(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const result = s3g("dispatchResult");
    const payload = { incident_category: form.incident_category.value.trim() || null, required_skills: form.required_skills.value.split(",").map((skill) => skill.trim()).filter(Boolean) };
    try {
        const recommendation = await api("/dispatch/recommendations", { method: "POST", body: JSON.stringify(payload) });
        result.hidden = false;
        if (!recommendation.recommendation) { result.textContent = "No available engineer meets the current dispatch criteria."; return; }
        const engineer = recommendation.recommendation;
        result.innerHTML = `<strong>${escapeHtml(engineer.name)}</strong> is the top recommendation (score ${escapeHtml(engineer.score)}). ${escapeHtml(recommendation.limitations || "")}`;
    } catch (error) { setMessage(error.message, true); }
}

s3gElements.loginForm.addEventListener("submit", signIn);
s3g("logoutButton").addEventListener("click", () => logout());
s3g("incidentForm").addEventListener("submit", submitIncident);
s3g("slaPredictionForm").addEventListener("submit", submitPrediction);
s3g("dispatchForm").addEventListener("submit", submitDispatch);
document.querySelectorAll(".s3g-account-choice").forEach((button) => button.addEventListener("click", () => { s3gElements.email.value = button.dataset.email; s3gElements.password.value = S3G_DEMO_PASSWORD; s3gElements.loginError.textContent = ""; }));
document.querySelectorAll(".s3g-refresh-button").forEach((button) => button.addEventListener("click", loadDashboard));
document.addEventListener("click", (event) => {
    const update = event.target.closest("[data-update-ticket]");
    const assign = event.target.closest("[data-assign-ticket]");
    if (update) updateTicketStatus(update);
    if (assign) assignTicket(assign);
});

(async function restoreSession() {
    if (!s3gState.token) return;
    try { s3gState.user = await api("/auth/me"); showPortal(); await loadDashboard(); } catch (_) { /* api handles expired sessions */ }
})();

setInterval(() => { if (s3gState.user) loadDashboard(); }, 30000);
