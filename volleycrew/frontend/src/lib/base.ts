// Nginx renders the base for this response; direct access and Vite use /.
export const basePath = new URL(document.baseURI).pathname.replace(/\/$/, "");
export const csrfCookieName = basePath ? "vc_csrf_ingress" : "vc_csrf";
