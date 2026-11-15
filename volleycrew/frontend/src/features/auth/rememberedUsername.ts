const key = "volleycrew:last-username";

export function rememberedUsername() {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function rememberUsername(username: string) {
  try {
    localStorage.setItem(key, username);
  } catch {
    // Login also works when the browser blocks local storage.
  }
}
