import { track } from "@vercel/analytics";
import { AUTHOR, REPO } from "../data/author";

/** Fixed action names; never send destination URLs, queries, or email addresses. */
export function engagementEvent(
	destination: URL,
	origin: string,
): string | null {
	if (destination.protocol === "mailto:") return "email_click";
	if (destination.origin === new URL(AUTHOR.contact).origin) {
		if (destination.pathname === new URL(AUTHOR.contact).pathname)
			return "contact_click";
		if (destination.pathname === new URL(AUTHOR.research).pathname)
			return "research_click";
	}
	if (destination.href === REPO || destination.href.startsWith(`${REPO}/`))
		return "code_data_click";
	if (destination.origin !== origin) return null;
	if (destination.pathname.startsWith("/paper/")) return "paper_click";
	if (destination.pathname.startsWith("/data/")) return "code_data_click";
	return null;
}

export function trackEngagement(event: MouseEvent): void {
	const link =
		event.target instanceof Element ? event.target.closest("a[href]") : null;
	if (!(link instanceof HTMLAnchorElement)) return;
	const action = engagementEvent(new URL(link.href), window.location.origin);
	if (action) track(action, { source_path: window.location.pathname });
}
