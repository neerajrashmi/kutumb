document.addEventListener("DOMContentLoaded", function () {
    const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    function formatDateDisplay(dateStr) {
        if (!dateStr) return "";
        const parts = dateStr.split("-");
        if (parts.length !== 3) return dateStr;
        const d = parseInt(parts[2], 10);
        const m = parseInt(parts[1], 10) - 1;
        return `${String(d).padStart(2, '0')}-${MONTH_NAMES[m]}-${parts[0]}`;
    }

    function formatMonthYearDisplay(ymStr) {
        if (!ymStr) return "";
        const parts = ymStr.split("-");
        if (parts.length !== 2) return ymStr;
        const m = parseInt(parts[1], 10) - 1;
        return `${MONTH_NAMES[m]}-${parts[0]}`;
    }

    document.querySelectorAll(".date-block-container").forEach(container => {
        const prefix = container.getAttribute("data-prefix");
        const precSelect = container.querySelector(".date-precision-select");
        const startWrapper = document.getElementById(`${prefix}_start_wrapper`);
        const startLabel = document.getElementById(`${prefix}_start_label`);
        const startInput = container.querySelector(".date-start-input");
        const endWrapper = document.getElementById(`${prefix}_end_wrapper`);
        const endInput = container.querySelector(".date-end-input");
        const yearWrapper = document.getElementById(`${prefix}_year_wrapper`);
        const yearInput = container.querySelector(".date-year-input");
        const monthWrapper = document.getElementById(`${prefix}_month_wrapper`);
        const monthInput = container.querySelector(".date-month-input");
        const textDisplay = container.querySelector(".date-display-text");

        function updateDateUIAndText() {
            const prec = precSelect.value;

            startWrapper.classList.add("d-none");
            endWrapper.classList.add("d-none");
            yearWrapper.classList.add("d-none");
            monthWrapper.classList.add("d-none");

            if (prec === "EXACT") {
                startWrapper.classList.remove("d-none");
                if (startLabel) startLabel.innerText = "Date";
            } else if (prec === "YEAR") {
                yearWrapper.classList.remove("d-none");
            } else if (prec === "YEAR_MONTH") {
                monthWrapper.classList.remove("d-none");
            } else if (prec === "BEFORE" || prec === "AFTER") {
                startWrapper.classList.remove("d-none");
                if (startLabel) startLabel.innerText = "Reference Date";
            } else if (prec === "BETWEEN") {
                startWrapper.classList.remove("d-none");
                endWrapper.classList.remove("d-none");
                if (startLabel) startLabel.innerText = "Start Date";
            }

            let generated = "";
            if (prec === "EXACT" && startInput && startInput.value) {
                generated = formatDateDisplay(startInput.value);
            } else if (prec === "YEAR" && yearInput && yearInput.value) {
                generated = `Year ${yearInput.value}`;
            } else if (prec === "YEAR_MONTH" && monthInput && monthInput.value) {
                generated = formatMonthYearDisplay(monthInput.value);
            } else if (prec === "BEFORE" && startInput && startInput.value) {
                generated = `Before ${formatDateDisplay(startInput.value)}`;
            } else if (prec === "AFTER" && startInput && startInput.value) {
                generated = `After ${formatDateDisplay(startInput.value)}`;
            } else if (prec === "BETWEEN") {
                const s = startInput ? formatDateDisplay(startInput.value) : "?";
                const e = endInput ? formatDateDisplay(endInput.value) : "?";
                if ((startInput && startInput.value) || (endInput && endInput.value)) {
                    generated = `Between ${s || '?'} and ${e || '?'}`;
                }
            }

            if (textDisplay) textDisplay.value = generated;
        }

        if (precSelect) {
            precSelect.addEventListener("change", updateDateUIAndText);
            [startInput, endInput, yearInput, monthInput].forEach(inp => {
                if (inp) inp.addEventListener("input", updateDateUIAndText);
            });
            updateDateUIAndText();
        }
    });
});