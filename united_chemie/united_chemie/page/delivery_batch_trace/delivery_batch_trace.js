frappe.pages["delivery-batch-trace"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Delivery Batch Traceability"), single_column: true });
	$(wrapper).find(".layout-main-section").html(`
		<div class="traceability-help text-muted">Select a submitted Delivery Note. Every delivered item and batch will be traced through its actual In Qty Stock Entry until Manufacture is reached.</div>
		<div class="trace-filter-card card"><div class="card-body"><div class="trace-delivery-note"></div><button class="btn btn-primary trace-run-btn">${__("Trace Delivery Note")}</button><button class="btn btn-default trace-print-btn" disabled>${__("Print Trace")}</button></div></div>
		<div class="trace-guide"><b>${__("How to read")}</b><span>1. ${__("Delivered item")}</span><span>2. ${__("Delivered batch")}</span><span>3. ${__("Previous stock entry")}</span><span>4. ${__("Input batch used")}</span><span>5. ${__("Manufacture reached")}</span></div>
		<div class="trace-toolbar"><button class="btn btn-default btn-sm trace-expand-all">${__("Show full trace")}</button><button class="btn btn-default btn-sm trace-collapse-all">${__("Show summary")}</button></div>
		<div class="delivery-trace-tree"></div>
	`);
	const delivery_note = frappe.ui.form.make_control({
		parent: $(wrapper).find(".trace-delivery-note"),
		df: { fieldname: "delivery_note", label: __("Delivery Note"), fieldtype: "Link", options: "Delivery Note", reqd: 1 },
		render_input: true,
	});
	delivery_note.$input.on("change", load_trace);
	$(wrapper).find(".trace-run-btn").on("click", load_trace);
	$(wrapper).find(".trace-print-btn").on("click", print_trace);
	$(wrapper).find(".trace-expand-all").on("click", () => set_all_branches(true));
	$(wrapper).find(".trace-collapse-all").on("click", () => set_all_branches(false));
	page.set_primary_action(__("Trace"), load_trace, "search");
	let current_root = null;

	function load_trace() {
		if (!delivery_note.get_value()) {
			frappe.show_alert({ message: __("Select a Delivery Note first"), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "united_chemie.united_chemie.page.delivery_batch_trace.delivery_batch_trace.get_delivery_trace",
			args: { delivery_note: delivery_note.get_value() },
			freeze: true,
			freeze_message: __("Tracing batches…"),
			callback(r) {
				if (r.message) render(r.message);
			},
		});
	}

	function render(root, focus_node = null) {
		current_root = root;
		const tree = $(wrapper).find(".delivery-trace-tree").empty();
		tree.append(render_node(root, 0));
		set_all_branches(false);
		// Keep the Delivery Note, item and delivered batch visible initially.
		tree.find(".trace-children-level-0, .trace-children-level-1, .trace-children-level-2").show();
		// Keep every pending Continue Trace button reachable after a branch reload.
		tree.find(".trace-continue-btn").each((_, button) => {
			$(button).closest(".delivery-trace-node").parents(".trace-branch").show();
		});
		if (focus_node?.trace_node_id) {
			const target = tree.find(`[data-trace-node-id="${focus_node.trace_node_id}"]`);
			target.parents(".trace-branch").show();
			target.parent().children(".trace-branch").show();
			target.parents(".trace-children").prev(".delivery-trace-node").find(".trace-toggle").text("−");
			setTimeout(() => target[0]?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
		}
		$(wrapper).find(".trace-print-btn").prop("disabled", false);
	}

	function print_trace() {
		set_all_branches(true);
		setTimeout(() => {
			const trace = $(wrapper).find(".delivery-trace-tree").clone();
			trace.find(".trace-toggle, .trace-continue-btn").remove();
			trace.find(".delivery-trace-node").css("margin-left", "0");
			const print_window = window.open("", "_blank");
			if (!print_window) {
				frappe.msgprint(__("Please allow pop-ups to print the trace."));
				return;
			}
			const delivery_note_name = delivery_note.get_value() || __("Delivery Batch Traceability");
			print_window.document.write(`<!doctype html><html><head><title>${frappe.utils.escape_html(delivery_note_name)}</title><style>
				@page { size: A4 portrait; margin: 12mm; }
				* { box-sizing: border-box; }
				body { margin: 0; font-family: Arial, sans-serif; color: #172033; font-size: 10px; }
				h1 { margin: 0 0 4px; font-size: 18px; text-align: center; }
				.print-subtitle { margin: 0 0 16px; text-align: center; color: #64748b; }
				.delivery-trace-tree { width: 100%; max-width: 180mm; margin: 0 auto; }
				/* Print is intentionally flat: every numbered trace entry is centred
				   in one vertical column, rather than being progressively indented. */
				.trace-children, .trace-branch { margin: 0 !important; padding: 0 !important; border: 0 !important; display: block !important; }
				.delivery-trace-node { width: 100% !important; min-width: 0 !important; margin: 5px 0 !important; padding: 7px 9px; border: 1px solid #cbd5e1; border-left: 4px solid var(--branch-color, #64748b); border-radius: 4px; break-inside: avoid; page-break-inside: avoid; }
				.trace-kind { display: inline-block; min-width: 110px; color: #64748b; font-size: 8px; font-weight: bold; text-transform: uppercase; }
				.trace-title { font-weight: bold; } .trace-title a { color: #172033; text-decoration: none; }
				.trace-subtitle { margin: 4px 0 0; padding-left: 0; color: #475569; font-size: 9px; }
				.trace-step, .trace-amount, .trace-rate { display: inline-block; margin-right: 5px; font-size: 8px; }
				.trace-amount, .trace-rate { margin-left: 5px; padding: 1px 4px; border-radius: 5px; background: #f1f5f9; }
				.trace-batch-link { color: #2563eb; font-weight: bold; }
			</style></head><body><h1>Delivery Batch Traceability</h1><div class="print-subtitle">Delivery Note: ${frappe.utils.escape_html(delivery_note_name)}</div>${trace.prop("outerHTML")}<script>window.onload=function(){window.print();};<\/script></body></html>`);
			print_window.document.close();
		}, 100);
	}

	function set_all_branches(expand) {
		const tree = $(wrapper).find(".delivery-trace-tree");
		tree.find(".trace-branch").toggle(expand);
		tree.find(".trace-toggle").text(expand ? "−" : "+");
		if (!expand) tree.find(".trace-children-level-0, .trace-children-level-1, .trace-children-level-2").show();
	}

	function render_node(node, depth, branch_color = 0, parent_kind = null, sibling_index = 0, sibling_count = 1) {
		const has_children = node.children?.length;
		const kind = node.note ? "note" : node.title.startsWith("Delivery Note") ? "delivery" : node.title.startsWith("Item:") ? "item" : node.title.startsWith("Batch:") || node.title.startsWith("Serial:") ? "batch" : node.title.startsWith("In Qty Stock Entry") ? "transaction" : "consumed";
		if (kind === "consumed" && parent_kind === "transaction" && sibling_count > 1) branch_color = sibling_index;
		const row = $("<div class='delivery-trace-node'>").addClass(`trace-${kind}`).css({ "margin-left": `${depth * 20}px`, "--branch-color": branch_palette[branch_color % branch_palette.length] });
		if (!node.trace_node_id) node.trace_node_id = `trace-node-${frappe.utils.get_random(8)}`;
		row.attr("data-trace-node-id", node.trace_node_id);
		const toggle = has_children ? $("<button class='btn btn-xs trace-toggle'>−</button>") : $("<span class='trace-spacer'>");
		const friendly = friendly_title(node, kind, depth);
		const text = node.doctype && node.name
			? $("<a>").attr("href", frappe.utils.get_form_link(node.doctype, node.name)).text(friendly.value)
			: $("<span>").text(friendly.value);
		row.append(toggle, $("<span class='trace-step'>").text(depth + 1), $("<span class='trace-kind'>").text(friendly.label), $("<span class='trace-title'>").append(text));
		if (node.amount !== null && node.amount !== undefined) {
			row.find(".trace-title").append($("<span class='trace-amount'>").text(format_currency(node.amount, node.currency)));
		}
		if (node.rate !== null && node.rate !== undefined) {
			row.find(".trace-title").append($("<span class='trace-rate'>").text(`${__("Rate")}: ${format_currency(node.rate, node.currency)}`));
		}
		if (node.subtitle) row.append(render_subtitle(node));
		if (node.continue_args) {
			const continue_button = $("<button class='btn btn-xs btn-primary trace-continue-btn'>").text(__("Continue trace"));
			continue_button.on("click", () => continue_trace(node, continue_button));
			row.append(continue_button);
		}
		const container = $("<div class='trace-children'>").append(row);
		if (has_children) {
			const children = $(`<div class='trace-branch trace-children-level-${depth}'>`);
			node.children.forEach((child, index) => children.append(render_node(child, depth + 1, branch_color, kind, index, node.children.length)));
			container.append(children);
			toggle.on("click", () => { children.toggle(); toggle.text(children.is(":visible") ? "−" : "+"); });
		}
		return container;
	}

	function continue_trace(node, button) {
		button.prop("disabled", true).text(__("Loading…"));
		frappe.call({
			method: "united_chemie.united_chemie.page.delivery_batch_trace.delivery_batch_trace.get_branch_trace",
			args: node.continue_args,
			freeze: true,
			freeze_message: __("Loading next trace segment…"),
			callback(r) {
				node.title = __("Continued trace segment");
				node.continue_args = null;
				node.children = r.message?.children || [];
				render(current_root, node);
			},
		});
	}

	const branch_palette = ["#2563eb", "#db2777", "#059669", "#7c3aed", "#d97706", "#0891b2", "#dc2626", "#4f46e5"];

	function render_subtitle(node) {
		const subtitle = $("<div class='trace-subtitle'>");
		if (!node.batch_no) return subtitle.text(node.subtitle);
		const remaining = node.subtitle.replace(`Batch: ${node.batch_no}`, "").replace(/^\s*\|\s*/, "");
		subtitle.append(document.createTextNode(`${__("Batch")}: `));
		subtitle.append($("<a class='trace-batch-link'>").attr("href", frappe.utils.get_form_link("Batch", node.batch_no)).text(node.batch_no));
		if (remaining) subtitle.append(document.createTextNode(` | ${remaining}`));
		return subtitle;
	}

	function friendly_title(node, kind, depth) {
		const value = node.title.includes(":") ? node.title.split(":").slice(1).join(":").trim() : node.title;
		const labels = {
			delivery: __("Delivery Note"),
			item: __("Delivered Item"),
			batch: __("Delivered Batch"),
			transaction: depth > 3 ? __("Earlier Stock Entry") : __("Previous Stock Entry"),
			consumed: __("Input Batch Used"),
			note: __("Trace Note"),
		};
		return { label: labels[kind], value };
	}

	frappe.dom.set_style(`
		.delivery-trace-tree { max-width: 1120px; margin-top: 10px; overflow-x: auto; }
		.trace-guide { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; max-width: 1120px; margin-top: 20px; padding: 10px 12px; border-radius: 6px; background: var(--subtle-fg); font-size: 12px; }
		.trace-guide span { padding-left: 8px; border-left: 1px solid var(--border-color); }
		.trace-toolbar { margin: 18px 0 8px; display: flex; gap: 8px; }
		.trace-filter-card { max-width: 620px; margin-top: 12px; }
		.trace-filter-card .card-body { display: flex; align-items: end; gap: 14px; padding: 16px; }
		.trace-delivery-note { flex: 1; }
		.trace-run-btn { margin-bottom: 5px; white-space: nowrap; }
		.trace-print-btn { margin-bottom: 5px; white-space: nowrap; }
		.delivery-trace-node { min-width: 700px; position: relative; border: 1px solid var(--border-color); border-left: 5px solid var(--branch-color, #7c8aa5); padding: 10px 14px; margin: 7px 0; background: var(--card-bg); border-radius: 7px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
		.trace-delivery { border-left-color: #2563eb; background: #eff6ff; }
		.trace-item { border-left-color: var(--branch-color); }
		.trace-batch { border-left-color: var(--branch-color); }
		.trace-transaction { border-left-color: var(--branch-color); background: #fffbeb; }
		.trace-consumed { border-left-color: var(--branch-color); background: color-mix(in srgb, var(--branch-color) 7%, white); }
		.trace-note { border-left-color: #9ca3af; background: #f9fafb; color: var(--text-muted); font-style: italic; }
		.trace-toggle { margin-right: 9px; width: 24px; height: 24px; border: 0; border-radius: 50%; background: var(--control-bg); font-size: 17px; line-height: 18px; }
		.trace-spacer { display: inline-block; width: 34px; }
		.trace-step { display: inline-flex; justify-content: center; align-items: center; width: 22px; height: 22px; margin-right: 7px; border-radius: 50%; background: var(--control-bg); color: var(--text-muted); font-size: 11px; font-weight: 700; }
		.trace-kind { display: inline-block; min-width: 135px; color: var(--text-muted); font-size: 10px; font-weight: 700; letter-spacing: .4px; }
		.trace-title a, .trace-title { font-weight: 600; color: var(--text-color); }
		.trace-amount { display: inline-block; margin-left: 9px; padding: 2px 7px; border-radius: 10px; background: var(--control-bg); color: var(--text-muted); font-size: 11px; font-weight: 700; }
		.trace-rate { display: inline-block; margin-left: 7px; padding: 2px 7px; border-radius: 10px; background: #ecfdf5; color: #047857; font-size: 11px; font-weight: 700; }
		.trace-subtitle { margin: 6px 0 0 34px; font-size: 12px; color: var(--text-muted); }
		.trace-batch-link { font-weight: 700; color: var(--branch-color, var(--primary)); text-decoration: underline; }
		.trace-continue-btn { margin: 8px 0 0 34px; }
		@media print {
			@page { margin: 12mm; }
			.page-head, .traceability-help, .trace-filter-card, .trace-guide, .trace-toolbar, .trace-toggle { display: none !important; }
			.layout-main-section { width: 100% !important; max-width: none !important; margin: 0 auto !important; padding: 0 !important; }
			.delivery-trace-tree { width: 92% !important; max-width: 100% !important; margin: 0 auto !important; overflow: visible !important; }
			.delivery-trace-node { break-inside: avoid; box-shadow: none; }
		}
		.traceability-help { padding: 12px 0; }
	`, "delivery-batch-trace-style");
};