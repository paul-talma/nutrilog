// script.js
// DOM element references
const todayBtn = document.querySelector("#today-btn");
const dailySummary = document.querySelector("#daily-summary");
const dailyLog = document.querySelector("#daily-log");
const form = document.querySelector("#form");
let chart = null;

// rendering
/**
 * Renders the daily nutritional summary table.
 * @param {object} log - The daily log object containing total nutrition data.
 */
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

/**
 * Renders the detailed daily log of food entries, organized by meal.
 * @param {object} log - The daily log object containing meal and food item details.
 */
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

/**
 * Fetches all historical logs and renders a chart displaying calorie trends over time.
 */
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
                        borderColor: "#263743",
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
        chart.data.labels = allLogs.map((d) => d.date);
        chart.data.datasets[0].data = allLogs.map((d) => d.total_calories);
        chart.update();
    }
}

/**
 * Checks if a given log object contains any food entries.
 * @param {object} log - The log object to check.
 * @returns {boolean} - True if the log is empty, false otherwise.
 */
function isEmpty(log) {
    for (let meal of log.meals) {
        if (meal.items.length > 0) {
            return false;
        }
    }
    return true;
}

/**
 * Populates the food entry form with default values for meal, date, food name, and weight.
 */
function populateFormWithDefault() {
    document.querySelector("#meal").value = "breakfast";
    document.querySelector("#date").value = new Date().toLocaleDateString(
        "en-CA",
    );
    document.querySelector("#food_name").value = "greek yogurt";
    document.querySelector("#weight").value = 100;
}

function displayFetchError(detail) {
    const foodNameField = form.querySelector("#food_name_field");
    const errMsg = document.createElement("div");
    errMsg.id = "err-msg";
    errMsg.append(detail);
    foodNameField.append(errMsg);
}

/**
 * Toggles the application's visual theme between light and dark modes.
 */
function toggleTheme() {
    if (document.documentElement.dataset.theme === "dark") {
        document.documentElement.dataset.theme = "dark";
    } else {
        document.documentElement.dataset.theme = "dark";
    }
}

// data functions
/**
 * Fetches today's daily log from the backend API.
 * @returns {Promise<object>} - A promise that resolves to the daily log object for today.
 */
async function getTodayLog() {
    const response = await fetch("/logs/today", {
        method: "GET",
        headers: { "content-type": "application/json" },
    });
    const log = await response.json();
    return log;
}

/**
 * Fetches all historical daily logs from the backend API.
 * @returns {Promise<Array<object>>} - A promise that resolves to an array of all daily log objects.
 */
async function getAllLogs() {
    const response = await fetch("/logs/all", {
        method: "GET",
    });

    const logs = await response.json();
    return logs;
}

/**
 * Processes raw log data into a format suitable for charting.
 * @param {Array<object>} logs - An array of daily log objects.
 * @returns {Array<object>} - An array of objects with date and total calorie information, sorted by date.
 */
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
/**
 * Handles the submission of a new food entry form.
 * Sends the new entry data to the backend API and then updates the displayed daily summary and log.
 * @param {Event} e - The submit event object.
 */
async function newEntry(e) {
    e.preventDefault();

    const errDiv = form.querySelector("#err-msg");
    if (errDiv) {
        errDiv.remove();
    }
    const data = Object.fromEntries(new FormData(e.target));
    const response = await fetch("/logs/new_entry", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!response.ok) {
        const error = await response.json();
        displayFetchError(error.detail);
    } else {
        const log = await getTodayLog();
        drawDailySummary(log);
        drawDailyLog(log);
        drawChart();
    }
}

/**
 * Deletes a specific food entry from the log via the backend API.
 * After deletion, it refreshes the daily summary and log display.
 * @param {string} dataId - The unique identifier of the food item to delete.
 */
async function deleteEntry(dataId) {
    const response = await fetch(`/logs/delete_entry/${dataId}`, {
        method: "DELETE",
    });
    const log = await getTodayLog();
    drawDailySummary(log);
    drawDailyLog(log);
    drawChart();
}

// set up event listeners
/**
 * Sets up all necessary event listeners for user interactions.
 * This includes handling delete button clicks, setting today's date, and form submissions.
 */
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
/**
 * Initializes the application once the DOM is fully loaded.
 * Populates the form, sets up event listeners, fetches and displays today's log, and draws the chart.
 * Handles display of loading indicators and error states.
 */
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
