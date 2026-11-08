const key = "volleycrew:last-profile";

export function rememberedProfile() {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function rememberProfile(id: string) {
  try {
    localStorage.setItem(key, id);
  } catch {
    // Login also works when the browser blocks local storage.
  }
}
