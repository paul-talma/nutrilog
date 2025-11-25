// script.js
// DOM element references
const todayBtn = document.querySelector("#today-btn");
const summary = document.querySelector("#daily-summary-table");
const form = document.querySelector("#form");

// rendering
function drawDailySummary(log) {
    summary.replaceChildren();

    // draw header
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    ["meal", "food", "weight", "calories"].forEach((text) => {
        const th = document.createElement("th");
        th.textContent = text;
        header.append(th);
    });
    thead.appendChild(header);
    summary.appendChild(thead);

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
                isFirstItem = false;
            }
            const foodName = document.createElement("td");
            foodName.textContent = foodItem.name;
            const weight = document.createElement("td");
            weight.textContent = foodItem.weight;
            weight.style.textAlign = "right";
            const calories = document.createElement("td");
            calories.textContent = foodItem.calories;
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
    summary.appendChild(tbody);
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
async function getCurrentLog() {
    const response = await fetch("/logs/today", {
        method: "GET",
        headers: { "content-type": "application/json" },
    });
    const log = await response.json();
    console.log(log);
    return log;
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

    const result = await response.json();
    const log = await getCurrentLog();
    drawDailySummary(log);
}

async function deleteEntry(dataId) {
    // send DELETE request to backend
    const response = await fetch(`/logs/delete_entry/${dataId}`, {
        method: "DELETE",
    });
    // redraw table
    const log = await getCurrentLog();
    drawDailySummary(log);
}

// set up event listeners
function setupEventListeners() {
    summary.addEventListener("click", (e) => {
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
    toggleTheme();
    populateFormWithDefault();
    setupEventListeners();
    const log = await getCurrentLog();
    drawDailySummary(log);
});
