// script.js
// DOM element references
const todayBtn = document.querySelector("#today-btn");
const dailySummary = document.querySelector("#daily-summary");
const dailyLog = document.querySelector("#daily-log");
const form = document.querySelector("#form");
let chart = null;

// rendering
function drawDailySummary(log) {
    dailySummary.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = "Daily Summary";
    dailySummary.append(title);
    if (!log || isEmpty(log)) {
        const p = document.createElement("p");
        p.textContent = "No entries yet!";
        dailySummary.append(p);
        return;
    }
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");
    const header = document.createElement("tr");
    thead.append(header);

    ["nutrient", "value"].forEach((text) => {
        const th = document.createElement("th");
        th.textContent = text;
        header.append(th);
    });

    ["calories", "protein", "carbs", "fat"].forEach((text) => {
        const row = document.createElement("tr");
        const nameCell = document.createElement("td");
        nameCell.textContent =
            text === "calories" ? `${text} (kcal):` : `${text}:`;
        const valueCell = document.createElement("td");
        const units = text === "calories" ? "" : "g";
        valueCell.textContent = log[`total_${text}`].toFixed(0) + units;
        valueCell.style.textAlign = "right";

        row.append(nameCell, valueCell);
        tbody.append(row);
    });
    table.append(tbody);
    table.append(thead);
    dailySummary.append(table);
}

function drawDailyLog(log) {
    dailyLog.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = "Daily Log";
    dailyLog.append(title);
    if (!log || isEmpty(log)) {
        const p = document.createElement("p");
        p.textContent = "No entries yet!";
        dailyLog.append(p);
        return;
    }
    // draw header
    const dailyLogTable = document.createElement("table");
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    ["meal", "food", "weight (g)", "calories (kcal)", ""].forEach((text) => {
        const th = document.createElement("th");
        th.textContent = text;
        header.append(th);
    });
    thead.appendChild(header);
    dailyLogTable.appendChild(thead);

    // draw data
    const tbody = document.createElement("tbody");

    for (let meal of log.meals) {
        let isFirstItem = true;
        let row = document.createElement("tr");

        const mealName = document.createElement("td");
        mealName.textContent = meal.name;
        row.appendChild(mealName);

        for (let foodItem of meal.items) {
            const row = document.createElement("tr");
            const mealCell = document.createElement("td");
            if (isFirstItem) {
                mealCell.textContent = meal.name;
                mealCell.style["font-weight"] = "bold";
                isFirstItem = false;
            }
            const foodName = document.createElement("td");
            foodName.textContent = foodItem.name;
            const weight = document.createElement("td");
            weight.textContent = foodItem.weight;
            weight.style.textAlign = "right";
            const calories = document.createElement("td");
            calories.textContent = foodItem.calories.toFixed();
            calories.style.textAlign = "right";

            const delButton = document.createElement("button");
            delButton.textContent = "remove";
            delButton.classList.add("delete-btn");
            const delCell = document.createElement("td");
            delCell.appendChild(delButton);

            row.append(mealCell, foodName, weight, calories, delCell);

            row.dataset.id = foodItem.data_id;
            tbody.appendChild(row);
        }
    }
    dailyLogTable.appendChild(tbody);
    const div = document.createElement("div");
    div.classList.add("table-container");
    div.appendChild(dailyLogTable);
    dailyLog.append(div);
}

async function drawChart() {
    const allLogs = await getAllLogs();
    // const chartData = getChartData(allLogs);

    // Create chart
    if (!chart) {
        const ctx = document.getElementById("nutritionChart").getContext("2d");
        chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: allLogs.map((d) => d.date),
                datasets: [
                    {
                        label: "Calories",
                        data: allLogs.map((d) => d.total_calories),
                        borderColor: "Red",
                        tension: 0.1,
                    },
                ],
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true },
                },
            },
        });
    } else {
        chart.data.labels = chartData.map((d) => d.date);
        chart.data.datasets[0].data = chartData.map((d) => d.calories);
        chart.update();
    }
}

function isEmpty(log) {
    for (let meal of log.meals) {
        if (meal.items.length > 0) {
            return false;
        }
    }
    return true;
}

function populateFormWithDefault() {
    document.querySelector("#meal").value = "breakfast";
    document.querySelector("#date").value = new Date().toLocaleDateString(
        "en-CA",
    );
    document.querySelector("#food_name").value = "greek yogurt";
    document.querySelector("#weight").value = 100;
}

function toggleTheme() {
    if (document.documentElement.dataset.theme === "dark") {
        document.documentElement.dataset.theme = "dark";
    } else {
        document.documentElement.dataset.theme = "dark";
    }
}

// data functions
async function getTodayLog() {
    const response = await fetch("/logs/today", {
        method: "GET",
        headers: { "content-type": "application/json" },
    });
    const log = await response.json();
    return log;
}

async function getAllLogs() {
    const response = await fetch("/logs/all", {
        method: "GET",
    });

    const logs = await response.json();
    return logs;
}

function getChartData(logs) {
    const result = [];
    for (let log of logs) {
        const day = {
            date: log.date,
            totals: {
                calories: log.total_calories,
                protein: log.total_protein,
                carbs: log.total_carbs,
                fat: log.total_fat,
            },
            meals: {},
        };
        result.push(day);
    }
    return result.sort((a, b) => new Date(a.date) - new Date(b.date));
}

// action functions
async function newEntry(e) {
    e.preventDefault();

    const data = Object.fromEntries(new FormData(e.target));
    const response = await fetch("/logs/new_entry", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
    });

    const log = await getTodayLog();
    drawDailySummary(log);
    drawDailyLog(log);
}

async function deleteEntry(dataId) {
    const response = await fetch(`/logs/delete_entry/${dataId}`, {
        method: "DELETE",
    });
    const log = await getTodayLog();
    drawDailySummary(log);
    drawDailyLog(log);
}

// set up event listeners
function setupEventListeners() {
    dailyLog.addEventListener("click", (e) => {
        if (e.target.classList.contains("delete-btn")) {
            const row = e.target.closest("tr");
            deleteEntry(row.dataset.id);
        }
    });

    todayBtn.addEventListener("click", (e) => {
        document.querySelector("#date").value = new Date().toLocaleDateString(
            "en-CA",
        );
    });

    form.addEventListener("submit", newEntry);
}

// initialization
document.addEventListener("DOMContentLoaded", async () => {
    const loading = document.querySelector("#loading");
    const app = document.querySelector("#app");
    // toggleTheme();
    try {
        populateFormWithDefault();
        setupEventListeners();
        const log = await getTodayLog();
        drawDailySummary(log);
        drawDailyLog(log);
        drawChart();

        loading.style.display = "none";
        app.style.display = "block";
    } catch (error) {
        loading.textContent = "❌ Failed to load. Please refresh.";
    }
});
