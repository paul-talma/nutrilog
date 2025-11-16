// script.js

document.getElementById("form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = Object.fromEntries(new FormData(e.target));

    const response = await fetch("http://localhost:500/process", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
    });

    const result = await response.json();

    document.getElementById("output").textContent = results.message;
});
