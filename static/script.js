// script.js
function populateFormWithDefault() {
    document.getElementById("meal").value = "breakfast";
    document.getElementById("date").value = new Date()
        .toISOString()
        .split("T")[0];
    document.getElementById("food_name").value = "greek yogurt";
    document.getElementById("weight").value = 100;
}
function toggleTheme() {
    document.documentElement.dataset.theme = "dark";
}

document.addEventListener("DOMContentLoaded", () => {
    toggleTheme();
    populateFormWithDefault();
    updateDailyPanel();
});

document.getElementById("form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = Object.fromEntries(new FormData(e.target));

    const response = await fetch("/new_entry", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
    });

    const result = await response.json();

    updateDailyPanel();
});

async function updateDailyPanel() {
    const table = document.getElementById("daily-summary-table");
    table.replaceChildren();
    let header = document.createElement("tr");
    ["meal", "food", "weight", "calories"].forEach((text) => {
        head = document.createElement("td");
        head.textContent = text;
        header.append(head);
    });
    table.appendChild(header);

    const response = await fetch("/logs/today", {
        method: "GET",
        headers: { "content-type": "application/json" },
    });
    const log = await response.json();

    for (let meal of log.meals) {
        // put meal name in first column
        let row = document.createElement("tr");
        const mealName = document.createElement("td");
        mealName.textContent = meal.name;
        row.appendChild(mealName);
        for (let foodItem of meal.items) {
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
            const delCell = document.createElement("td");
            delCell.appendChild(delButton);

            if (row.children.length === 0) {
                row.appendChild(document.createElement("td"));
            }
            row.append(foodName, weight, calories, delCell);

            row.dataset.id = foodItem.data_id;
            table.appendChild(row);

            row = document.createElement("tr");
        }
    }
}
