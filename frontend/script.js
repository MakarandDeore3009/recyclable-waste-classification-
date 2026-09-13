
/*
 * ============================================================
 * SORTWISE FRONTEND SCRIPT
 * ============================================================
 */

const API_BASE = "";

/* ============================================================
AUTHENTICATION
============================================================ */

const authToken = localStorage.getItem("sortwiseToken");
const loggedIn = localStorage.getItem("sortwiseLoggedIn");

if (!authToken || loggedIn !== "true") {
  window.location.replace("login.html");
}

function getAuthHeaders(extraHeaders = {}) {
  const token = localStorage.getItem("sortwiseToken");

  return {
    ...extraHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function logoutUser() {
  localStorage.removeItem("sortwiseToken");
  localStorage.removeItem("sortwiseLoggedIn");
  localStorage.removeItem("sortwiseUser");
  window.location.replace("login.html");
}

/* ============================================================
STATE
============================================================ */

const state = {
  username: localStorage.getItem("sortwise_username") || "",
  selectedFile: null,

  // Groq chatbot conversation
  chatMessages: [],
  chatBusy: false,
};

const el = (id) => document.getElementById(id);

const dropzone = el("dropzone");
const fileInput = el("fileInput");
const dropzoneEmpty = el("dropzoneEmpty");
const previewImg = el("previewImg");
const classifyBtn = el("classifyBtn");
const resetBtn = el("resetBtn");
const loadingRow = el("loadingRow");
const errorBox = el("errorBox");
const resultTicket = el("resultTicket");
const verifyBanner = el("verifyBanner");
const nameBtn = el("nameBtn");
const userStats = el("userStats");
const nameModal = el("nameModal");
const nameInput = el("nameInput");
const nameSaveBtn = el("nameSaveBtn");
const nameCancelBtn = el("nameCancelBtn");

/* ============================================================
INIT
============================================================ */

init();

async function init() {
  wireTabs();
  wireUpload();
  wireNameModal();

  // Initialize Groq chatbot
  wireChatbot();

  updateUserPill();

  try {
    const health = await fetchJSON("/api/health");

    if (health && !health.class_order_verified && verifyBanner) {
      verifyBanner.classList.remove("hidden");
    }
  } catch (e) {
    console.warn("Health check failed:", e);
  }

  if (state.username) {
    refreshProfile();
  } else {
    loadLoggedInUser();
  }
}

/* ============================================================
LOAD LOGGED-IN USER
============================================================ */

function loadLoggedInUser() {
  try {
    const savedUser = localStorage.getItem("sortwiseUser");

    if (!savedUser) return;

    const user = JSON.parse(savedUser);

    const username =
      user.username ||
      user.name ||
      user.email;

    if (username) {
      state.username = username;

      localStorage.setItem(
        "sortwise_username",
        username
      );

      updateUserPill();

      refreshProfile();
    }
  } catch (error) {
    console.warn(
      "Could not load saved user:",
      error
    );
  }
}

/* ============================================================
TABS
============================================================ */

function wireTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {

      document
        .querySelectorAll(".tab")
        .forEach((t) =>
          t.classList.remove("active")
        );

      document
        .querySelectorAll(".view")
        .forEach((v) =>
          v.classList.remove("active")
        );

      tab.classList.add("active");

      const view =
        el(`view-${tab.dataset.tab}`);

      if (view) {
        view.classList.add("active");
      }

      if (tab.dataset.tab === "leaderboard") {
        loadLeaderboard();
      }

      if (tab.dataset.tab === "history") {
        loadHistory();
      }
    });
  });
}

/* ============================================================
NAME / USER
============================================================ */

function wireNameModal() {
  if (
    !nameBtn ||
    !nameInput ||
    !nameModal ||
    !nameSaveBtn ||
    !nameCancelBtn
  ) {
    return;
  }

  nameBtn.addEventListener("click", () => {
    nameInput.value = state.username;

    nameModal.classList.remove("hidden");

    nameInput.focus();
  });

  if (userStats) {
    userStats.addEventListener("click", () => {
      nameInput.value = state.username;

      nameModal.classList.remove("hidden");
    });
  }

  nameCancelBtn.addEventListener(
    "click",
    () => {
      nameModal.classList.add("hidden");
    }
  );

  nameSaveBtn.addEventListener(
    "click",
    saveUsername
  );

  nameInput.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Enter") {
        saveUsername();
      }
    }
  );
}

function saveUsername() {
  const val = nameInput.value.trim();

  if (!val) {
    showError("Please enter your name.");
    return;
  }

  state.username = val;

  localStorage.setItem(
    "sortwise_username",
    val
  );

  nameModal.classList.add("hidden");

  updateUserPill();

  refreshProfile();
}

function updateUserPill() {
  if (state.username) {

    if (nameBtn) {
      nameBtn.classList.add("hidden");
    }

    if (userStats) {
      userStats.classList.remove("hidden");
    }

  } else {

    if (nameBtn) {
      nameBtn.classList.remove("hidden");
    }

    if (userStats) {
      userStats.classList.add("hidden");
    }
  }
}

/* ============================================================
PROFILE
============================================================ */

async function refreshProfile() {
  if (!state.username) return;

  try {

    const profile =
      await fetchJSON(
        `/api/profile/${encodeURIComponent(
          state.username
        )}`
      );

    renderProfile(profile);

  } catch (e) {

    console.warn(
      "Could not load profile:",
      e
    );
  }
}

function renderProfile(profile) {
  if (!profile) return;

  const levelTitle = el("levelTitle");

  if (levelTitle) {
    levelTitle.textContent =
      profile.level_title ||
      "Seedling";
  }

  const pointsTotal =
    el("pointsTotal");

  if (pointsTotal) {
    pointsTotal.textContent =
      profile.points ?? 0;
  }

  const growthLevelTitle =
    el("growthLevelTitle");

  if (growthLevelTitle) {
    growthLevelTitle.textContent =
      `Level ${profile.level ?? 1} · ${
        profile.level_title || "Seedling"
      }`;
  }

  const toNext =
    profile.points_to_next_level ?? 0;

  const growthPointsLabel =
    el("growthPointsLabel");

  if (growthPointsLabel) {

    growthPointsLabel.textContent =
      toNext > 0
        ? `${toNext} pts to next level`
        : "Max level reached 🌲";
  }

  const withinLevel =
    (profile.points ?? 0) % 100;

  const growthFill =
    el("growthFill");

  if (growthFill) {

    growthFill.style.width =
      `${toNext > 0 ? withinLevel : 100}%`;
  }

  renderBadges(
    profile.badges || []
  );
}

const ALL_BADGES = [
  "First Scan",
  "Recycler",
  "E-Waste Hero",
  "Century Club",
  "Half-K Hero",
  "Eco Champion",
  "7-Day Streak",
];

function renderBadges(
  earnedBadges = []
) {
  const row = el("badgesRow");

  if (!row) return;

  row.innerHTML = "";

  const earnedNames =
    new Set(
      (
        Array.isArray(earnedBadges)
          ? earnedBadges
          : []
      ).map((b) => b.name)
    );

  ALL_BADGES.forEach((name) => {

    const span =
      document.createElement("span");

    const isEarned =
      earnedNames.has(name);

    span.className =
      `badge-medal${
        isEarned ? "" : " locked"
      }`;

    span.textContent =
      `${isEarned ? "🏅 " : "🔒 "}${name}`;

    row.appendChild(span);
  });
}

/* ============================================================
UPLOAD
============================================================ */

function wireUpload() {
  if (
    !dropzone ||
    !fileInput ||
    !classifyBtn ||
    !resetBtn
  ) {
    return;
  }

  dropzone.addEventListener(
    "click",
    () => fileInput.click()
  );

  fileInput.addEventListener(
    "change",
    () => {

      if (
        fileInput.files &&
        fileInput.files[0]
      ) {
        handleFile(
          fileInput.files[0]
        );
      }
    }
  );

  ["dragover", "dragenter"].forEach(
    (evt) => {

      dropzone.addEventListener(
        evt,
        (e) => {

          e.preventDefault();

          dropzone.classList.add(
            "drag-over"
          );
        }
      );
    }
  );

  [
    "dragleave",
    "dragend",
    "drop"
  ].forEach((evt) => {

    dropzone.addEventListener(
      evt,
      (e) => {

        e.preventDefault();

        dropzone.classList.remove(
          "drag-over"
        );
      }
    );
  });

  dropzone.addEventListener(
    "drop",
    (e) => {

      const file =
        e.dataTransfer.files[0];

      if (file) {
        handleFile(file);
      }
    }
  );

  classifyBtn.addEventListener(
    "click",
    classifySelectedImage
  );

  resetBtn.addEventListener(
    "click",
    resetScanView
  );
}

function handleFile(file) {

  if (
    !file ||
    !file.type.startsWith("image/")
  ) {

    showError(
      "Please choose an image file."
    );

    return;
  }

  const maxSize =
    8 * 1024 * 1024;

  if (file.size > maxSize) {

    showError(
      "Image is too large. Please choose an image up to 8MB."
    );

    return;
  }

  state.selectedFile = file;

  const url =
    URL.createObjectURL(file);

  if (previewImg) {

    previewImg.src = url;

    previewImg.classList.remove(
      "hidden"
    );
  }

  if (dropzoneEmpty) {

    dropzoneEmpty.classList.add(
      "hidden"
    );
  }

  if (classifyBtn) {
    classifyBtn.disabled = false;
  }

  if (resetBtn) {
    resetBtn.classList.remove(
      "hidden"
    );
  }

  if (resultTicket) {
    resultTicket.classList.add(
      "hidden"
    );
  }

  if (errorBox) {
    errorBox.classList.add(
      "hidden"
    );
  }
}

function resetScanView() {

  state.selectedFile = null;

  if (fileInput) {
    fileInput.value = "";
  }

  if (previewImg) {
    previewImg.src = "";

    previewImg.classList.add(
      "hidden"
    );
  }

  if (dropzoneEmpty) {

    dropzoneEmpty.classList.remove(
      "hidden"
    );
  }

  if (classifyBtn) {
    classifyBtn.disabled = true;
  }

  if (resetBtn) {
    resetBtn.classList.add(
      "hidden"
    );
  }

  if (resultTicket) {
    resultTicket.classList.add(
      "hidden"
    );
  }

  if (errorBox) {
    errorBox.classList.add(
      "hidden"
    );
  }
}

/* ============================================================
CLASSIFY IMAGE
============================================================ */

async function classifySelectedImage() {

  if (!state.selectedFile) return;

  if (errorBox) {
    errorBox.classList.add(
      "hidden"
    );
  }

  if (resultTicket) {
    resultTicket.classList.add(
      "hidden"
    );
  }

  if (loadingRow) {
    loadingRow.classList.remove(
      "hidden"
    );
  }

  if (classifyBtn) {
    classifyBtn.disabled = true;
  }

  const formData =
    new FormData();

  formData.append(
    "image",
    state.selectedFile
  );

  formData.append(
    "username",
    state.username || "guest"
  );

  try {

    const token =
      localStorage.getItem(
        "sortwiseToken"
      );

    if (!token) {
      logoutUser();
      return;
    }

    const res =
      await fetch(
        `${API_BASE}/api/classify`,
        {
          method: "POST",

          headers:
            getAuthHeaders(),

          body: formData,
        }
      );

    if (
      res.status === 401 ||
      res.status === 403
    ) {
      logoutUser();
      return;
    }

    const data =
      await res.json();

    if (!res.ok) {

      throw new Error(
        data.error ||
          data.message ||
          "Classification failed."
      );
    }

    renderResult(data);

    if (!state.username) {

      showError(
        "Tip: set your name (top right) so your points and badges are saved under your account, not shared 'guest' points.",
        true
      );
    }

  } catch (e) {

    console.error(
      "Classification error:",
      e
    );

    showError(
      e.message ||
        "Something went wrong talking to the server."
    );

  } finally {

    if (loadingRow) {
      loadingRow.classList.add(
        "hidden"
      );
    }

    if (classifyBtn) {
      classifyBtn.disabled = false;
    }
  }
}

function showError(
  msg,
  isNotice = false
) {

  if (!errorBox) return;

  errorBox.textContent = msg;

  errorBox.classList.remove(
    "hidden"
  );

  if (isNotice) {

    errorBox.style.background =
      "var(--marigold)";

    errorBox.style.color =
      "#4A320A";

    errorBox.style.borderColor =
      "var(--marigold-deep)";

  } else {

    errorBox.style.background = "";
    errorBox.style.color = "";
    errorBox.style.borderColor = "";
  }
}

/* ============================================================
RENDER CLASSIFICATION RESULT
============================================================ */

function renderResult(data) {

  const {
    prediction,
    disposal_guide,
    reward,
    class_order_verified
  } = data;

  if (!prediction) {

    showError(
      "The server did not return a prediction."
    );

    return;
  }

  if (!disposal_guide) {

    showError(
      "The server did not return disposal instructions."
    );

    return;
  }

  if (
    !class_order_verified &&
    verifyBanner
  ) {

    verifyBanner.classList.remove(
      "hidden"
    );
  }

  const stamp =
    el("stamp");

  if (stamp) {

    stamp.className =
      `stamp ${prediction.category}`;
  }

  const stampLabel =
    el("stampLabel");

  if (stampLabel) {

    stampLabel.textContent =
      disposal_guide.label;
  }

  const confidenceText =
    el("confidenceText");

  if (confidenceText) {

    confidenceText.textContent =
      `${Math.round(
        prediction.confidence * 100
      )}% confident`;
  }

  const lowConfidenceNote =
    el("lowConfidenceNote");

  if (lowConfidenceNote) {

    lowConfidenceNote.classList.toggle(
      "hidden",
      !prediction.low_confidence_warning
    );
  }

  const probBars =
    el("probBars");

  if (probBars) {

    probBars.innerHTML = "";

    if (prediction.all_probabilities) {

      Object.entries(
        prediction.all_probabilities
      ).forEach(
        ([name, prob]) => {

          const row =
            document.createElement(
              "div"
            );

          row.className =
            "prob-bar-row";

          const percentage =
            Math.round(prob * 100);

          row.innerHTML = `
            <span class="prob-bar-label">
              ${formatCategoryName(name)}
            </span>

            <span class="prob-bar-track">
              <span
                class="prob-bar-fill"
                style="width:${percentage}%"
              ></span>
            </span>

            <span>
              ${percentage}%
            </span>
          `;

          probBars.appendChild(row);
        }
      );
    }
  }

  const guideSummary =
    el("guideSummary");

  if (guideSummary) {

    guideSummary.textContent =
      disposal_guide.summary || "";
  }

  const stepsList =
    el("guideSteps");

  if (stepsList) {

    stepsList.innerHTML = "";

    (
      disposal_guide.steps || []
    ).forEach((step) => {

      const li =
        document.createElement(
          "li"
        );

      li.innerHTML = `
        <span></span>

        <span>

          <span
            class="step-title"
            style="display:block"
          >
            ${escapeHTML(
              step.title || ""
            )}
          </span>

          <span class="step-detail">
            ${escapeHTML(
              step.detail || ""
            )}
          </span>

        </span>
      `;

      stepsList.appendChild(li);
    });
  }

  const avoidBox =
    el("guideAvoid");

  if (avoidBox) {

    if (
      disposal_guide.avoid &&
      disposal_guide.avoid.length
    ) {

      avoidBox.innerHTML = `
        <p>Keep in mind</p>

        <ul>
          ${
            disposal_guide.avoid
              .map(
                (a) =>
                  `<li>${escapeHTML(a)}</li>`
              )
              .join("")
          }
        </ul>
      `;

      avoidBox.classList.remove(
        "hidden"
      );

    } else {

      avoidBox.innerHTML = "";

      avoidBox.classList.add(
        "hidden"
      );
    }
  }

  const pointsEarned =
    reward?.points_earned ?? 0;

  const pointsEarnedNum =
    el("pointsEarnedNum");

  if (pointsEarnedNum) {

    pointsEarnedNum.textContent =
      pointsEarned;
  }

  const badgeToast =
    el("badgeToast");

  if (badgeToast) {

    if (
      reward?.newly_earned_badges &&
      reward.newly_earned_badges.length
    ) {

      badgeToast.textContent =
        `🎉 New badge: ${
          reward.newly_earned_badges
            .map((b) => b.name)
            .join(", ")
        }`;

      badgeToast.classList.remove(
        "hidden"
      );

    } else {

      badgeToast.classList.add(
        "hidden"
      );
    }
  }

  if (resultTicket) {

    resultTicket.classList.remove(
      "hidden"
    );

    resultTicket.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }

  refreshProfile();
}

/* ============================================================
LEADERBOARD
============================================================ */

async function loadLeaderboard() {

  const list =
    el("leaderboardList");

  if (!list) return;

  list.innerHTML =
    "<li>Loading…</li>";

  try {

    const rows =
      await fetchJSON(
        "/api/leaderboard"
      );

    if (
      !rows ||
      !rows.length
    ) {

      list.innerHTML =
        "<li>No scans yet — be the first!</li>";

      return;
    }

    list.innerHTML = "";

    rows.forEach(
      (row, i) => {

        const li =
          document.createElement(
            "li"
          );

        li.innerHTML = `
          <span class="lb-rank">
            #${i + 1}
          </span>

          <span class="lb-name">
            ${escapeHTML(
              row.username || ""
            )}
          </span>

          <span class="lb-points">
            ${row.points ?? 0} pts
          </span>

          <span class="lb-streak">
            🔥 ${row.streak ?? 0}d
          </span>
        `;

        list.appendChild(li);
      }
    );

  } catch (e) {

    console.error(
      "Leaderboard error:",
      e
    );

    list.innerHTML =
      "<li>Could not load leaderboard.</li>";
  }
}

/* ============================================================
HISTORY
============================================================ */

async function loadHistory() {

  const list =
    el("historyList");

  const sub =
    el("historySub");

  if (!list || !sub) {
    return;
  }

  if (!state.username) {

    sub.textContent =
      "Set your name (top right) to start tracking scans.";

    list.innerHTML = "";

    return;
  }

  sub.textContent =
    `Recent scans for ${state.username}.`;

  list.innerHTML =
    "<li>Loading…</li>";

  try {

    const rows =
      await fetchJSON(
        `/api/history/${encodeURIComponent(
          state.username
        )}`
      );

    if (
      !rows ||
      !rows.length
    ) {

      list.innerHTML =
        "<li>No scans yet — go classify something!</li>";

      return;
    }

    list.innerHTML = "";

    rows.forEach(
      (row) => {

        const li =
          document.createElement(
            "li"
          );

        const date =
          new Date(row.timestamp);

        li.innerHTML = `
          <span class="hist-cat ${escapeHTML(
            row.category || ""
          )}">
            ${formatCategoryName(
              row.category || ""
            )}
          </span>

          <span class="hist-meta">
            ${date.toLocaleString()}
            ·
            ${Math.round(
              (row.confidence || 0) * 100
            )}% confident
          </span>

          <span class="hist-points">
            +${row.points_earned ?? 0}
          </span>
        `;

        list.appendChild(li);
      }
    );

  } catch (e) {

    console.error(
      "History error:",
      e
    );

    list.innerHTML =
      "<li>Could not load history.</li>";
  }
}

/* ============================================================
SORTWISE AI CHATBOT - OLLAMA / FLOATING ASSISTANT
============================================================ */

function wireChatbot() {
  const floatingBtn = el("chatbotFloatingBtn");
  const chatWindow = el("chatbotWindow");
  const closeBtn = el("chatCloseBtn");
  const clearBtn = el("chatClearBtn");
  const chatInput = el("chatInput");
  const chatSendBtn = el("chatSendBtn");

  // Chatbot is optional. Do not affect the rest of the app if
  // the floating chatbot HTML is not present.
  if (!floatingBtn || !chatWindow || !chatInput || !chatSendBtn) {
    return;
  }

  // Prevent duplicate event listeners.
  if (floatingBtn.dataset.chatWired === "true") {
    initializeChatbotView();
    return;
  }

  floatingBtn.dataset.chatWired = "true";

  floatingBtn.addEventListener("click", () => {
    chatWindow.classList.remove("hidden");
    floatingBtn.classList.add("hidden");

    initializeChatbotView();

    setTimeout(() => {
      chatInput.focus();
    }, 50);
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      chatWindow.classList.add("hidden");
      floatingBtn.classList.remove("hidden");
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", clearChatConversation);
  }

  chatSendBtn.addEventListener("click", sendChatMessage);

  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChatMessage();
    }
  });

  initializeChatbotView();
}

/* ============================================================
CHAT INITIALIZATION
============================================================ */

function initializeChatbotView() {
  const chatMessages = el("chatMessages");

  if (!chatMessages) {
    return;
  }

  // Display the welcome message only once per page load.
  if (
    state.chatMessages.length === 0 &&
    chatMessages.children.length === 0
  ) {
    addChatMessage(
      "Hi! I'm SortWise AI 🌱\n\n" +
        "Ask me about recyclable waste, non-recyclable waste, " +
        "e-waste, recycling, segregation, or disposal instructions.",
      "bot",
      false
    );
  }

  scrollChatToBottom();
}

/* ============================================================
ADD CHAT MESSAGE
============================================================ */

function addChatMessage(message, sender, saveToState = true) {
  const chatMessages = el("chatMessages");

  if (!chatMessages) {
    return;
  }

  const text = String(message || "").trim();

  if (!text) {
    return;
  }

  if (saveToState) {
    state.chatMessages.push({
      role: sender === "user" ? "user" : "assistant",
      content: text,
    });
  }

  const wrapper = document.createElement("div");
  wrapper.className =
    sender === "user"
      ? "chat-message user-message"
      : "chat-message bot-message";

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.textContent = sender === "user" ? "👤" : "🌱";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";

  // textContent prevents model output from injecting HTML/JavaScript.
  bubble.textContent = text;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);

  scrollChatToBottom();
}

/* ============================================================
CHAT SCROLL
============================================================ */

function scrollChatToBottom() {
  const chatMessages = el("chatMessages");

  if (!chatMessages) {
    return;
  }

  requestAnimationFrame(() => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

/* ============================================================
CHAT STATUS
============================================================ */

function setChatStatus(message = "", visible = false) {
  const chatStatus = el("chatStatus");

  if (!chatStatus) {
    return;
  }

  chatStatus.textContent =
    message || "SortWise AI is thinking...";

  chatStatus.classList.toggle("hidden", !visible);
}

/* ============================================================
CHAT BUTTON / INPUT STATE
============================================================ */

function setChatBusy(busy) {
  state.chatBusy = busy;

  const chatInput = el("chatInput");
  const chatSendBtn = el("chatSendBtn");
  const chatClearBtn = el("chatClearBtn");

  if (chatInput) {
    chatInput.disabled = busy;
  }

  if (chatSendBtn) {
    chatSendBtn.disabled = busy;

    // Supports both text-based and icon-based send buttons.
    if (busy) {
      chatSendBtn.dataset.originalText =
        chatSendBtn.textContent || "";
      chatSendBtn.textContent = "…";
    } else if (chatSendBtn.dataset.originalText !== undefined) {
      chatSendBtn.textContent =
        chatSendBtn.dataset.originalText;
      delete chatSendBtn.dataset.originalText;
    }
  }

  if (chatClearBtn) {
    chatClearBtn.disabled = busy;
  }
}

/* ============================================================
SEND CHAT MESSAGE
============================================================ */

async function sendChatMessage() {
  const chatInput = el("chatInput");

  if (!chatInput || state.chatBusy) {
    return;
  }

  const message = chatInput.value.trim();

  if (!message) {
    return;
  }

  const token = localStorage.getItem("sortwiseToken");

  if (!token) {
    logoutUser();
    return;
  }

  /*
   * Keep only previous messages in history.
   * The current message is sent separately as "message", so it
   * is not duplicated in the Groq API request.
   */
  const history = state.chatMessages
    .slice(-12)
    .map((item) => ({
      role: item.role,
      content: item.content,
    }));

  // Show the user's message immediately.
  addChatMessage(message, "user");
  chatInput.value = "";

  setChatBusy(true);
  setChatStatus("SortWise AI is thinking…", true);

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: getAuthHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify({
        message,
        history,
        username: state.username || "",
      }),
    });

    if (response.status === 401 || response.status === 403) {
      logoutUser();
      return;
    }

    let data = {};

    try {
      data = await response.json();
    } catch (_) {
      throw new Error(
        "The server returned an invalid response."
      );
    }

    if (!response.ok || !data.success) {
      throw new Error(
        data.error ||
          data.message ||
          "The AI assistant could not process your message."
      );
    }

    const answer =
      data.response ||
      data.message ||
      data.reply ||
      "I couldn't generate a response. Please try again.";

    addChatMessage(answer, "bot");
  } catch (error) {
    console.error("SortWise chatbot error:", error);

    let errorMessage =
      "Sorry, I couldn't connect to SortWise AI.";

    const errorText = error?.message || "";
    const lowerError = errorText.toLowerCase();

    if (
      lowerError.includes("failed to fetch") ||
      lowerError.includes("network")
    ) {
      errorMessage =
        "I couldn't connect to the SortWise server. " +
        "Please make sure Flask and AI service is available.";
    } else if (errorText) {
      errorMessage = errorText;
    }

    addChatMessage(errorMessage, "bot");
  } finally {
    setChatBusy(false);
    setChatStatus("", false);

    if (chatInput) {
      chatInput.focus();
    }
  }
}

/* ============================================================
CLEAR CHAT
============================================================ */

function clearChatConversation() {
  if (state.chatBusy) {
    return;
  }

  const chatMessages = el("chatMessages");

  if (!chatMessages) {
    return;
  }

  state.chatMessages = [];
  chatMessages.innerHTML = "";

  addChatMessage(
    "Chat cleared 🌱\n\n" +
      "Hi! I'm SortWise AI. " +
      "What would you like to know about waste disposal?",
    "bot",
    false
  );

  const chatInput = el("chatInput");

  if (chatInput) {
    chatInput.focus();
  }
}

/* ============================================================
FETCH JSON
============================================================ */

async function fetchJSON(
  path,
  options = {}
) {

  const token =
    localStorage.getItem(
      "sortwiseToken"
    );

  if (!token) {

    logoutUser();

    throw new Error(
      "Authentication required."
    );
  }

  const response =
    await fetch(
      `${API_BASE}${path}`,
      {
        ...options,

        headers:
          getAuthHeaders(
            options.headers || {}
          ),
      }
    );

  if (
    response.status === 401 ||
    response.status === 403
  ) {

    logoutUser();

    throw new Error(
      "Your session has expired. Please login again."
    );
  }

  if (!response.ok) {

    let message =
      `Request failed: ${path}`;

    try {

      const data =
        await response.json();

      message =
        data.error ||
          data.message ||
          message;

    } catch (_) {

      // Response wasn't JSON.
    }

    throw new Error(
      message
    );
  }

  return response.json();
}

/* ============================================================
UTILITIES
============================================================ */

function formatCategoryName(
  name
) {

  return String(name)
    .replace(
      /_/g,
      " "
    )
    .replace(
      /\b\w/g,
      (c) =>
        c.toUpperCase()
    );
}

function escapeHTML(
  value
) {

  return String(value)
    .replace(
      /&/g,
      "&amp;"
    )
    .replace(
      /</g,
      "&lt;"
    )
    .replace(
      />/g,
      "&gt;"
    )
    .replace(
      /"/g,
      "&quot;"
    )
    .replace(
      /'/g,
      "&#39;"
    );
}
