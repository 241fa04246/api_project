const API_ROOT = "/api";
const TOKEN_KEY = "libraryToken";
const API_KEY = "libraryApiKey";

function showMessage(element, message, success = false) {
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("success", success);
}

async function request(path, { method = "GET", body, authenticated = true } = {}) {
  const headers = { "X-API-Key": sessionStorage.getItem(API_KEY) || "" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authenticated) {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response.");
  }
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

function redirectToLogin() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(API_KEY);
  window.location.assign("/login.html");
}

function handleAuthForms() {
  const form = document.querySelector("form[data-form='login'], form[data-form='register']");
  if (!form) return;
  const isLogin = form.dataset.form === "login";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = form.querySelector(".form-message");
    const values = Object.fromEntries(new FormData(form).entries());
    sessionStorage.setItem(API_KEY, values.api_key);
    showMessage(message, isLogin ? "Signing you in…" : "Creating your account…");
    try {
      if (isLogin) {
        const result = await request("/auth/login", {
          method: "POST",
          authenticated: false,
          body: { username: values.username, password: values.password },
        });
        sessionStorage.setItem(TOKEN_KEY, result.access_token);
        window.location.assign("/dashboard.html");
      } else {
        await request("/auth/register", {
          method: "POST",
          authenticated: false,
          body: { username: values.username, password: values.password },
        });
        showMessage(message, "Account created. Sign in to continue.", true);
        window.setTimeout(() => window.location.assign("/login.html"), 900);
      }
    } catch (error) {
      showMessage(message, error.message);
    }
  });
}

function requireSession() {
  if (!sessionStorage.getItem(API_KEY) || !sessionStorage.getItem(TOKEN_KEY)) {
    redirectToLogin();
    return false;
  }
  return true;
}

function makeCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value == null ? "" : String(value);
  return cell;
}

async function loadDashboard() {
  if (!requireSession()) return;
  const message = document.querySelector("[data-page-message]");
  try {
    const [profile, result] = await Promise.all([
      request("/auth/me"),
      request("/loans"),
    ]);
    document.querySelector("[data-user-name]").textContent = profile.user.username;
    document.querySelector("[data-loan-count]").textContent =
      result.loans.filter((loan) => !loan.returned_at).length;
    const body = document.querySelector("[data-loans]");
    body.replaceChildren();
    if (!result.loans.length) {
      const row = document.createElement("tr");
      const cell = makeCell("No loans yet. Browse the catalog to find a book.");
      cell.colSpan = 3;
      row.append(cell);
      body.append(row);
      return;
    }
    for (const loan of result.loans) {
      const row = document.createElement("tr");
      row.append(
        makeCell(loan.title),
        makeCell(loan.borrowed_at),
        makeCell(loan.returned_at ? "Returned" : "On loan"),
      );
      body.append(row);
    }
  } catch (error) {
    showMessage(message, error.message);
    if (error.message.includes("bearer token")) redirectToLogin();
  }
}

function renderBook(book, role, hasActiveLoan) {
  const article = document.createElement("article");
  article.className = "book-card";
  const cover = document.createElement("div");
  cover.className = "book-cover";
  cover.textContent = book.title.slice(0, 1).toUpperCase();
  cover.setAttribute("aria-hidden", "true");
  const details = document.createElement("div");
  details.className = "book-details";
  const title = document.createElement("h2");
  title.textContent = book.title;
  const author = document.createElement("p");
  author.textContent = `by ${book.author}`;
  const meta = document.createElement("p");
  meta.className = "book-meta";
  meta.textContent = `${book.year} · ISBN ${book.isbn} · ${book.copies} available`;
  details.append(title, author, meta);
  const actions = document.createElement("div");
  actions.className = "book-actions";
  const actionButton = document.createElement("button");
  actionButton.className = "button";
  actionButton.type = "button";
  actionButton.textContent = role === "admin" ? "Remove book" : "Borrow";
  actionButton.disabled = role !== "admin" && book.copies < 1;
  actionButton.addEventListener("click", async () => {
    try {
      if (role === "admin") {
        await request(`/books/${book.id}`, { method: "DELETE" });
      } else {
        await request(`/books/${book.id}/borrow`, { method: "POST" });
      }
      await loadBooks();
    } catch (error) {
      showMessage(document.querySelector("[data-page-message]"), error.message);
    }
  });
  actions.append(actionButton);
  if (role !== "admin" && hasActiveLoan) {
    const returnButton = document.createElement("button");
    returnButton.className = "text-link link-button";
    returnButton.type = "button";
    returnButton.textContent = "Return";
    returnButton.addEventListener("click", async () => {
      try {
        await request(`/books/${book.id}/return`, { method: "POST" });
        await loadBooks();
      } catch (error) {
        showMessage(document.querySelector("[data-page-message]"), error.message);
      }
    });
    actions.append(returnButton);
  }
  details.append(actions);
  article.append(cover, details);
  return article;
}

let currentRole = "member";
async function loadBooks(search = "") {
  if (!requireSession()) return;
  const list = document.querySelector("[data-books]");
  const message = document.querySelector("[data-page-message]");
  try {
    const profile = await request("/auth/me");
    currentRole = profile.user.role;
    document.querySelector("[data-admin-panel]").hidden = currentRole !== "admin";
    const [result, loanResult] = await Promise.all([
      request(`/books${search ? `?q=${encodeURIComponent(search)}` : ""}`),
      roleIsMember(profile.user.role) ? request("/loans") : Promise.resolve({ loans: [] }),
    ]);
    const activeBookIds = new Set(
      loanResult.loans.filter((loan) => !loan.returned_at).map((loan) => loan.book_id),
    );
    list.replaceChildren();
    if (!result.books.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = search ? "No books match that search." : "The catalog is empty for now.";
      list.append(empty);
      return;
    }
    for (const book of result.books) {
      list.append(renderBook(book, currentRole, activeBookIds.has(book.id)));
    }
  } catch (error) {
    showMessage(message, error.message);
    if (error.message.includes("bearer token")) redirectToLogin();
  }
}

function roleIsMember(role) {
  return role === "member";
}

function handlePageForms() {
  const searchForm = document.querySelector("form[data-form='search']");
  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadBooks(new FormData(searchForm).get("q").trim());
  });
  const createForm = document.querySelector("form[data-form='create-book']");
  createForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(createForm).entries());
    values.year = Number(values.year);
    values.copies = Number(values.copies);
    const message = document.querySelector("[data-page-message]");
    try {
      await request("/books", { method: "POST", body: values });
      createForm.reset();
      showMessage(message, "Book added to the catalog.", true);
      await loadBooks();
    } catch (error) {
      showMessage(message, error.message);
    }
  });
}

function handleLogout() {
  document.querySelectorAll("[data-action='logout']").forEach((button) => {
    button.addEventListener("click", () => {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(API_KEY);
      window.location.assign("/login.html");
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  handleAuthForms();
  handlePageForms();
  handleLogout();
  if (document.body.dataset.page === "dashboard") loadDashboard();
  if (document.body.dataset.page === "books") loadBooks();
});
