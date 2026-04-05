document.addEventListener("DOMContentLoaded", function() {
  // Pie chart
  const pieCanvas = document.getElementById("pieChart");
  if (pieCanvas) {
    const labels = JSON.parse(pieCanvas.dataset.labels || "[]");
    const values = JSON.parse(pieCanvas.dataset.values || "[]");
    new Chart(pieCanvas.getContext("2d"), {
      type: 'pie',
      data: { labels: labels, datasets: [{ data: values }] },
      options: { responsive: true }
    });
  }

  // Line chart for trend
  const lineCanvas = document.getElementById("lineChart");
  if (lineCanvas) {
    const trend = JSON.parse(lineCanvas.dataset.trend || "[]");
    const labels = trend.map(t => t.label);
    const incomes = trend.map(t => t.income);
    const expenses = trend.map(t => t.expense);
    new Chart(lineCanvas.getContext("2d"), {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          { label: 'Income', data: incomes, fill: false },
          { label: 'Expense', data: expenses, fill: false }
        ]
      },
      options: { responsive: true }
    });
  }
});
