const dataNode = document.getElementById("timer-data");

if (dataNode) {
  initTimer(JSON.parse(dataNode.textContent));
}

function initTimer(timerData) {
  const splits = timerData.splits;
  let comparison = timerData.comparison;
  let comparisonSplits = new Map(
    Object.entries(comparison?.splits ?? {}),
  );
  let bestSegments = new Map(Object.entries(timerData.best_segments ?? {}));
  let upcomingComparison;
  let upcomingBestSegments;

  let phase = "idle";
  let startedAt = null;
  let segmentStart = null;
  let attemptStartedWall = null;
  let results = [];
  let currentIndex = 0;
  let savedRunId = null;
  let saving = false;
  let rafId = null;

  const refs = {
    main: document.querySelector(".timer-main"),
    status: document.querySelector("[data-status]"),
    comparison: document.querySelector("[data-comparison]"),
    clock: document.querySelector("[data-clock]"),
    currentName: document.querySelector("[data-current-name]"),
    delta: document.querySelector("[data-delta]"),
    primary: document.querySelector("[data-primary]"),
    undo: document.querySelector("[data-undo]"),
    reset: document.querySelector("[data-reset]"),
    splitList: document.querySelector("[data-split-list]"),
    summary: document.querySelector("[data-summary]"),
  };

  function formatClock(milliseconds, showMs = true) {
    const total = Math.max(0, Math.floor(Number(milliseconds) || 0));
    const hours = Math.floor(total / 3_600_000);
    const minutes = Math.floor((total % 3_600_000) / 60_000);
    const seconds = Math.floor((total % 60_000) / 1_000);
    const millis = total % 1_000;
    const suffix = showMs ? `.${String(millis).padStart(3, "0")}` : "";
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}${suffix}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}${suffix}`;
  }

  function formatDelta(milliseconds) {
    const value = Math.round(Number(milliseconds) || 0);
    return `${value < 0 ? "−" : "+"}${formatClock(Math.abs(value))}`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => {
      const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return map[char];
    });
  }

  function showToast(message, tone = "info", timeout = 3_400) {
    const root = document.getElementById("toast-root");
    if (!root) return;
    const node = document.createElement("div");
    node.className = "toast";
    node.dataset.tone = tone;
    node.textContent = message;
    root.append(node);
    window.setTimeout(() => {
      node.style.opacity = "0";
      node.style.transform = "translateY(8px)";
      window.setTimeout(() => node.remove(), 200);
    }, timeout);
  }

  function paintSplits() {
    refs.splitList.innerHTML = splits
      .map((split, index) => {
        const result = results[index];
        const target = comparisonSplits.get(String(split.id));
        const classes = ["timer-split"];
        if (result) classes.push("done");
        if (index === currentIndex && phase !== "finished") {
          classes.push("current");
        }

        const best = bestSegments.get(String(split.id));
        if (result && best != null && result.segmentMs <= best) {
          classes.push("gold");
        }

        let delta = `<span class="timer-split-delta"></span>`;
        if (result && target != null) {
          const difference = result.cumulativeMs - target;
          const tone =
            difference < 0 ? "ahead" : difference > 0 ? "behind" : "";
          delta = `<span class="timer-split-delta ${tone}">${formatDelta(difference)}</span>`;
        }

        const time = result
          ? formatClock(result.cumulativeMs)
          : target != null
            ? formatClock(target)
            : "—";

        return `
          <li class="${classes.join(" ")}">
            <span class="timer-split-index">${String(index + 1).padStart(2, "0")}</span>
            <span class="timer-split-name">${escapeHtml(split.name)}</span>
            <span class="timer-split-time">${time}</span>
            ${delta}
          </li>`;
      })
      .join("");
  }

  function comparisonText() {
    if (!comparison) return "No comparison yet";
    if (comparison.total_ms != null) {
      return `${comparison.label} ${formatClock(comparison.total_ms)}`;
    }
    return `${comparison.label} splits`;
  }

  function paintStatus() {
    refs.main.dataset.state = phase;
    refs.status.textContent =
      phase === "idle" ? "Ready" : phase === "running" ? "Running" : "Finished";
    refs.comparison.textContent = comparisonText();
    refs.primary.textContent =
      phase === "idle" ? "Start" : phase === "running" ? "Split" : "Run again";
    refs.primary.disabled = saving;
    refs.undo.disabled = saving || results.length === 0;
    refs.reset.disabled = saving;

    const next = splits[currentIndex];
    refs.currentName.textContent =
      phase === "finished"
        ? "Run complete"
        : next
          ? `Next: ${next.name}`
          : "Route complete";
  }

  function setDelta(elapsed) {
    if (phase === "finished" && comparison?.total_ms != null) {
      const difference = elapsed - comparison.total_ms;
      refs.delta.textContent = formatDelta(difference);
      refs.delta.className = `timer-delta ${difference < 0 ? "ahead" : difference > 0 ? "behind" : ""}`;
      return;
    }

    const split = splits[currentIndex];
    const target = split ? comparisonSplits.get(String(split.id)) : null;
    if (phase === "running" && target != null) {
      const difference = elapsed - target;
      refs.delta.textContent = formatDelta(difference);
      refs.delta.className = `timer-delta ${difference < 0 ? "ahead" : difference > 0 ? "behind" : ""}`;
      return;
    }

    refs.delta.textContent = "—";
    refs.delta.className = "timer-delta";
  }

  function tick() {
    if (phase !== "running") return;
    const elapsed = performance.now() - startedAt;
    refs.clock.textContent = formatClock(elapsed);
    setDelta(elapsed);
    rafId = requestAnimationFrame(tick);
  }

  function startTicking() {
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(tick);
  }

  function start() {
    if (saving) return;

    if (upcomingComparison !== undefined) {
      comparison = upcomingComparison;
      comparisonSplits = new Map(
        Object.entries(comparison?.splits ?? {}),
      );
      upcomingComparison = undefined;
    }
    if (upcomingBestSegments !== undefined) {
      bestSegments = new Map(Object.entries(upcomingBestSegments));
      upcomingBestSegments = undefined;
    }

    phase = "running";
    startedAt = performance.now();
    segmentStart = startedAt;
    attemptStartedWall = new Date();
    results = [];
    currentIndex = 0;
    savedRunId = null;

    refs.summary.hidden = true;
    refs.clock.textContent = "00:00.000";
    paintSplits();
    paintStatus();
    startTicking();
  }

  async function finish(totalMs) {
    phase = "finished";
    saving = true;
    cancelAnimationFrame(rafId);

    refs.clock.textContent = formatClock(totalMs);
    setDelta(totalMs);
    refs.summary.hidden = false;
    refs.summary.dataset.tone = "saved";
    refs.summary.innerHTML = `
      <span class="summary-label">Saving run…</span>
      <strong>${formatClock(totalMs)}</strong>
      <span class="summary-detail">Sending the attempt to FastAPI.</span>`;
    paintSplits();
    paintStatus();

    const payload = {
      category_id: timerData.category_id,
      started_at: attemptStartedWall.toISOString(),
      finished_at: new Date().toISOString(),
      total_ms: Math.round(totalMs),
      splits: results.map((result, index) => ({
        split_id: result.splitId,
        name: result.name,
        position: index,
        segment_ms: Math.round(result.segmentMs),
        cumulative_ms: Math.round(result.cumulativeMs),
      })),
    };

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || "Could not save the run.");
      }

      savedRunId = body.run_id;
      upcomingComparison = body.comparison ?? null;
      upcomingBestSegments = body.best_segments ?? {};

      const isPB = Boolean(body.is_pb);
      const previous = body.previous_pb_ms;
      refs.summary.dataset.tone = isPB ? "pb" : "saved";
      refs.summary.innerHTML = `
        <span class="summary-label">${isPB ? "New personal best" : "Run saved"}</span>
        <strong>${formatClock(totalMs)}</strong>
        <span class="summary-detail"></span>
        <a class="summary-link" href="/categories/${timerData.category_id}">View route →</a>`;
      refs.summary.querySelector(".summary-detail").textContent =
        previous == null
          ? "First completed run"
          : `${formatDelta(totalMs - previous)} vs previous PB`;
      showToast(
        isPB ? "New personal best!" : "Run saved.",
        isPB ? "success" : "info",
      );
    } catch (error) {
      refs.summary.dataset.tone = "saved";
      refs.summary.innerHTML = `
        <span class="summary-label">Run not saved</span>
        <strong>${formatClock(totalMs)}</strong>
        <span class="summary-detail"></span>`;
      refs.summary.querySelector(".summary-detail").textContent =
        error.message;
      showToast(error.message, "error", 5_000);
    } finally {
      saving = false;
      paintStatus();
    }
  }

  function split() {
    if (phase === "idle") {
      start();
      return;
    }
    if (phase === "finished") {
      reset();
      start();
      return;
    }

    const now = performance.now();
    const cumulativeMs = now - startedAt;
    const segmentMs = now - segmentStart;
    const split = splits[currentIndex];

    results.push({
      splitId: split.id,
      name: split.name,
      segmentMs,
      cumulativeMs,
    });
    currentIndex += 1;
    segmentStart = now;

    if (currentIndex >= splits.length) {
      finish(cumulativeMs);
      return;
    }

    paintSplits();
    paintStatus();
  }

  function undo() {
    if (saving) {
      showToast("The run is still saving.", "info");
      return;
    }
    if (results.length === 0) return;

    if (phase === "finished") {
      if (savedRunId != null) {
        const runId = savedRunId;
        savedRunId = null;
        fetch(`/api/runs/${runId}`, { method: "DELETE" }).catch(() => {});
      }
      upcomingComparison = undefined;
      upcomingBestSegments = undefined;
      phase = "running";
      refs.summary.hidden = true;
    }

    results.pop();
    currentIndex = Math.max(0, currentIndex - 1);
    segmentStart = results.length
      ? startedAt + results.at(-1).cumulativeMs
      : startedAt;

    paintSplits();
    paintStatus();

    if (phase === "running") {
      refs.clock.textContent = formatClock(performance.now() - startedAt);
      startTicking();
    }
  }

  function reset() {
    if (saving) return;
    phase = "idle";
    cancelAnimationFrame(rafId);

    startedAt = null;
    segmentStart = null;
    attemptStartedWall = null;
    results = [];
    currentIndex = 0;
    savedRunId = null;

    refs.clock.textContent = "00:00.000";
    refs.delta.textContent = "—";
    refs.delta.className = "timer-delta";
    refs.summary.hidden = true;

    paintSplits();
    paintStatus();
  }

  function primaryAction() {
    if (saving) return;
    if (phase === "idle") start();
    else if (phase === "running") split();
    else {
      reset();
      start();
    }
  }

  function onKeyDown(event) {
    if (
      event.target instanceof Element &&
      event.target.closest("input, textarea, select")
    ) {
      return;
    }

    if (event.code === "Space") {
      event.preventDefault();
      primaryAction();
      return;
    }
    if (event.key === "Backspace") {
      event.preventDefault();
      undo();
      return;
    }
    if (
      event.key.toLowerCase() === "r" &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.altKey
    ) {
      event.preventDefault();
      reset();
    }
  }

  refs.primary.addEventListener("click", primaryAction);
  refs.undo.addEventListener("click", undo);
  refs.reset.addEventListener("click", reset);
  window.addEventListener("keydown", onKeyDown);

  paintSplits();
  paintStatus();
}
