// One delegated handler covers static markup and late-hydrated React islands.
let active: HTMLElement | null = null;
let leaveTimer: ReturnType<typeof setTimeout> | undefined;
const nativePopover = typeof HTMLElement.prototype.showPopover === "function";

function wrapper(target: EventTarget | null): HTMLElement | null {
	return target instanceof Element
		? target.closest<HTMLElement>("[data-tip]")
		: null;
}

function dismiss(): void {
	clearTimeout(leaveTimer);
	const tip = active?.querySelector<HTMLElement>("[role=tooltip]");
	if (tip) {
		if (nativePopover) tip.hidePopover();
		else delete tip.dataset.open;
	}
	active = null;
}

function show(container: HTMLElement): void {
	clearTimeout(leaveTimer);
	if (active === container) return;
	dismiss();
	const tip = container.querySelector<HTMLElement>("[role=tooltip]");
	const trigger = container.querySelector<HTMLElement>("button, a");
	if (!tip || !trigger) return;
	active = container;
	if (nativePopover) tip.showPopover();
	else tip.dataset.open = "";
	position(container);
}

function position(container: HTMLElement): void {
	const tip = container.querySelector<HTMLElement>("[role=tooltip]");
	const trigger = container.querySelector<HTMLElement>("button, a");
	if (!tip || !trigger) return;
	const anchor = trigger.getBoundingClientRect();
	if (
		anchor.bottom < 0 ||
		anchor.top > innerHeight ||
		anchor.right < 0 ||
		anchor.left > innerWidth
	) {
		dismiss();
		return;
	}
	const box = tip.getBoundingClientRect();
	const gap = 8;
	let left = anchor.left + (anchor.width - box.width) / 2;
	if (container.dataset.align === "start") left = anchor.left;
	if (container.dataset.align === "end") left = anchor.right - box.width;
	const above = anchor.top - box.height - gap;
	const below = anchor.bottom + gap;
	const preferBelow = container.dataset.side === "bottom";
	const top = preferBelow
		? below + box.height <= innerHeight - gap
			? below
			: above
		: above >= gap
			? above
			: below;
	tip.style.left = `${Math.max(gap, Math.min(left, innerWidth - box.width - gap))}px`;
	tip.style.top = `${Math.max(gap, Math.min(top, innerHeight - box.height - gap))}px`;
}

document.addEventListener("focusin", (event) => {
	const container = wrapper(event.target);
	if (container) show(container);
	else dismiss();
});
document.addEventListener("focusout", (event) => {
	if (
		active &&
		!active.matches(":hover") &&
		!active.contains(event.relatedTarget as Node | null)
	)
		dismiss();
});
document.addEventListener("pointerover", (event) => {
	if (event.pointerType === "touch") return;
	const container = wrapper(event.target);
	if (container && !container.contains(event.relatedTarget as Node | null))
		show(container);
});
document.addEventListener("pointerout", (event) => {
	const container = wrapper(event.target);
	if (
		container !== active ||
		container?.contains(event.relatedTarget as Node | null)
	)
		return;
	// Leave a short bridge across the gap so hover users can read/select the text.
	leaveTimer = setTimeout(() => {
		if (
			active &&
			!active.matches(":hover") &&
			!active.contains(document.activeElement)
		)
			dismiss();
	}, 150);
});
document.addEventListener("click", (event) => {
	const container = wrapper(event.target);
	if (container) show(container); // A tap works even on browsers that do not focus buttons.
});
document.addEventListener("pointerdown", (event) => {
	if (wrapper(event.target) !== active) dismiss();
});
document.addEventListener("keydown", (event) => {
	if (event.key === "Escape") dismiss();
});
// Focus can itself scroll a table/page; do not dismiss that newly opened tip.
const reposition = () => {
	if (active) position(active);
};
document.addEventListener("scroll", reposition, true);
window.addEventListener("resize", reposition);
