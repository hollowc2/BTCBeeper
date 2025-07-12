
(function(l, r) { if (!l || l.getElementById('livereloadscript')) return; r = l.createElement('script'); r.async = 1; r.src = '//' + (self.location.host || 'localhost').split(':')[0] + ':35729/livereload.js?snipver=1'; r.id = 'livereloadscript'; l.getElementsByTagName('head')[0].appendChild(r) })(self.document);
var app = (function () {
    'use strict';

    function noop() { }
    function add_location(element, file, line, column, char) {
        element.__svelte_meta = {
            loc: { file, line, column, char }
        };
    }
    function run(fn) {
        return fn();
    }
    function blank_object() {
        return Object.create(null);
    }
    function run_all(fns) {
        fns.forEach(run);
    }
    function is_function(thing) {
        return typeof thing === 'function';
    }
    function safe_not_equal(a, b) {
        return a != a ? b == b : a !== b || ((a && typeof a === 'object') || typeof a === 'function');
    }
    function is_empty(obj) {
        return Object.keys(obj).length === 0;
    }

    const globals = (typeof window !== 'undefined'
        ? window
        : typeof globalThis !== 'undefined'
            ? globalThis
            : global);
    function append(target, node) {
        target.appendChild(node);
    }
    function insert(target, node, anchor) {
        target.insertBefore(node, anchor || null);
    }
    function detach(node) {
        if (node.parentNode) {
            node.parentNode.removeChild(node);
        }
    }
    function destroy_each(iterations, detaching) {
        for (let i = 0; i < iterations.length; i += 1) {
            if (iterations[i])
                iterations[i].d(detaching);
        }
    }
    function element(name) {
        return document.createElement(name);
    }
    function text(data) {
        return document.createTextNode(data);
    }
    function space() {
        return text(' ');
    }
    function listen(node, event, handler, options) {
        node.addEventListener(event, handler, options);
        return () => node.removeEventListener(event, handler, options);
    }
    function attr(node, attribute, value) {
        if (value == null)
            node.removeAttribute(attribute);
        else if (node.getAttribute(attribute) !== value)
            node.setAttribute(attribute, value);
    }
    function children(element) {
        return Array.from(element.childNodes);
    }
    function set_style(node, key, value, important) {
        if (value == null) {
            node.style.removeProperty(key);
        }
        else {
            node.style.setProperty(key, value, important ? 'important' : '');
        }
    }
    function custom_event(type, detail, { bubbles = false, cancelable = false } = {}) {
        const e = document.createEvent('CustomEvent');
        e.initCustomEvent(type, bubbles, cancelable, detail);
        return e;
    }

    let current_component;
    function set_current_component(component) {
        current_component = component;
    }
    function get_current_component() {
        if (!current_component)
            throw new Error('Function called outside component initialization');
        return current_component;
    }
    /**
     * The `onMount` function schedules a callback to run as soon as the component has been mounted to the DOM.
     * It must be called during the component's initialisation (but doesn't need to live *inside* the component;
     * it can be called from an external module).
     *
     * `onMount` does not run inside a [server-side component](/docs#run-time-server-side-component-api).
     *
     * https://svelte.dev/docs#run-time-svelte-onmount
     */
    function onMount(fn) {
        get_current_component().$$.on_mount.push(fn);
    }
    /**
     * Schedules a callback to run immediately before the component is unmounted.
     *
     * Out of `onMount`, `beforeUpdate`, `afterUpdate` and `onDestroy`, this is the
     * only one that runs inside a server-side component.
     *
     * https://svelte.dev/docs#run-time-svelte-ondestroy
     */
    function onDestroy(fn) {
        get_current_component().$$.on_destroy.push(fn);
    }

    const dirty_components = [];
    const binding_callbacks = [];
    let render_callbacks = [];
    const flush_callbacks = [];
    const resolved_promise = /* @__PURE__ */ Promise.resolve();
    let update_scheduled = false;
    function schedule_update() {
        if (!update_scheduled) {
            update_scheduled = true;
            resolved_promise.then(flush);
        }
    }
    function add_render_callback(fn) {
        render_callbacks.push(fn);
    }
    // flush() calls callbacks in this order:
    // 1. All beforeUpdate callbacks, in order: parents before children
    // 2. All bind:this callbacks, in reverse order: children before parents.
    // 3. All afterUpdate callbacks, in order: parents before children. EXCEPT
    //    for afterUpdates called during the initial onMount, which are called in
    //    reverse order: children before parents.
    // Since callbacks might update component values, which could trigger another
    // call to flush(), the following steps guard against this:
    // 1. During beforeUpdate, any updated components will be added to the
    //    dirty_components array and will cause a reentrant call to flush(). Because
    //    the flush index is kept outside the function, the reentrant call will pick
    //    up where the earlier call left off and go through all dirty components. The
    //    current_component value is saved and restored so that the reentrant call will
    //    not interfere with the "parent" flush() call.
    // 2. bind:this callbacks cannot trigger new flush() calls.
    // 3. During afterUpdate, any updated components will NOT have their afterUpdate
    //    callback called a second time; the seen_callbacks set, outside the flush()
    //    function, guarantees this behavior.
    const seen_callbacks = new Set();
    let flushidx = 0; // Do *not* move this inside the flush() function
    function flush() {
        // Do not reenter flush while dirty components are updated, as this can
        // result in an infinite loop. Instead, let the inner flush handle it.
        // Reentrancy is ok afterwards for bindings etc.
        if (flushidx !== 0) {
            return;
        }
        const saved_component = current_component;
        do {
            // first, call beforeUpdate functions
            // and update components
            try {
                while (flushidx < dirty_components.length) {
                    const component = dirty_components[flushidx];
                    flushidx++;
                    set_current_component(component);
                    update(component.$$);
                }
            }
            catch (e) {
                // reset dirty state to not end up in a deadlocked state and then rethrow
                dirty_components.length = 0;
                flushidx = 0;
                throw e;
            }
            set_current_component(null);
            dirty_components.length = 0;
            flushidx = 0;
            while (binding_callbacks.length)
                binding_callbacks.pop()();
            // then, once components are updated, call
            // afterUpdate functions. This may cause
            // subsequent updates...
            for (let i = 0; i < render_callbacks.length; i += 1) {
                const callback = render_callbacks[i];
                if (!seen_callbacks.has(callback)) {
                    // ...so guard against infinite loops
                    seen_callbacks.add(callback);
                    callback();
                }
            }
            render_callbacks.length = 0;
        } while (dirty_components.length);
        while (flush_callbacks.length) {
            flush_callbacks.pop()();
        }
        update_scheduled = false;
        seen_callbacks.clear();
        set_current_component(saved_component);
    }
    function update($$) {
        if ($$.fragment !== null) {
            $$.update();
            run_all($$.before_update);
            const dirty = $$.dirty;
            $$.dirty = [-1];
            $$.fragment && $$.fragment.p($$.ctx, dirty);
            $$.after_update.forEach(add_render_callback);
        }
    }
    /**
     * Useful for example to execute remaining `afterUpdate` callbacks before executing `destroy`.
     */
    function flush_render_callbacks(fns) {
        const filtered = [];
        const targets = [];
        render_callbacks.forEach((c) => fns.indexOf(c) === -1 ? filtered.push(c) : targets.push(c));
        targets.forEach((c) => c());
        render_callbacks = filtered;
    }
    const outroing = new Set();
    function transition_in(block, local) {
        if (block && block.i) {
            outroing.delete(block);
            block.i(local);
        }
    }
    function mount_component(component, target, anchor, customElement) {
        const { fragment, after_update } = component.$$;
        fragment && fragment.m(target, anchor);
        if (!customElement) {
            // onMount happens before the initial afterUpdate
            add_render_callback(() => {
                const new_on_destroy = component.$$.on_mount.map(run).filter(is_function);
                // if the component was destroyed immediately
                // it will update the `$$.on_destroy` reference to `null`.
                // the destructured on_destroy may still reference to the old array
                if (component.$$.on_destroy) {
                    component.$$.on_destroy.push(...new_on_destroy);
                }
                else {
                    // Edge case - component was destroyed immediately,
                    // most likely as a result of a binding initialising
                    run_all(new_on_destroy);
                }
                component.$$.on_mount = [];
            });
        }
        after_update.forEach(add_render_callback);
    }
    function destroy_component(component, detaching) {
        const $$ = component.$$;
        if ($$.fragment !== null) {
            flush_render_callbacks($$.after_update);
            run_all($$.on_destroy);
            $$.fragment && $$.fragment.d(detaching);
            // TODO null out other refs, including component.$$ (but need to
            // preserve final state?)
            $$.on_destroy = $$.fragment = null;
            $$.ctx = [];
        }
    }
    function make_dirty(component, i) {
        if (component.$$.dirty[0] === -1) {
            dirty_components.push(component);
            schedule_update();
            component.$$.dirty.fill(0);
        }
        component.$$.dirty[(i / 31) | 0] |= (1 << (i % 31));
    }
    function init(component, options, instance, create_fragment, not_equal, props, append_styles, dirty = [-1]) {
        const parent_component = current_component;
        set_current_component(component);
        const $$ = component.$$ = {
            fragment: null,
            ctx: [],
            // state
            props,
            update: noop,
            not_equal,
            bound: blank_object(),
            // lifecycle
            on_mount: [],
            on_destroy: [],
            on_disconnect: [],
            before_update: [],
            after_update: [],
            context: new Map(options.context || (parent_component ? parent_component.$$.context : [])),
            // everything else
            callbacks: blank_object(),
            dirty,
            skip_bound: false,
            root: options.target || parent_component.$$.root
        };
        append_styles && append_styles($$.root);
        let ready = false;
        $$.ctx = instance
            ? instance(component, options.props || {}, (i, ret, ...rest) => {
                const value = rest.length ? rest[0] : ret;
                if ($$.ctx && not_equal($$.ctx[i], $$.ctx[i] = value)) {
                    if (!$$.skip_bound && $$.bound[i])
                        $$.bound[i](value);
                    if (ready)
                        make_dirty(component, i);
                }
                return ret;
            })
            : [];
        $$.update();
        ready = true;
        run_all($$.before_update);
        // `false` as a special case of no DOM component
        $$.fragment = create_fragment ? create_fragment($$.ctx) : false;
        if (options.target) {
            if (options.hydrate) {
                const nodes = children(options.target);
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment && $$.fragment.l(nodes);
                nodes.forEach(detach);
            }
            else {
                // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
                $$.fragment && $$.fragment.c();
            }
            if (options.intro)
                transition_in(component.$$.fragment);
            mount_component(component, options.target, options.anchor, options.customElement);
            flush();
        }
        set_current_component(parent_component);
    }
    /**
     * Base class for Svelte components. Used when dev=false.
     */
    class SvelteComponent {
        $destroy() {
            destroy_component(this, 1);
            this.$destroy = noop;
        }
        $on(type, callback) {
            if (!is_function(callback)) {
                return noop;
            }
            const callbacks = (this.$$.callbacks[type] || (this.$$.callbacks[type] = []));
            callbacks.push(callback);
            return () => {
                const index = callbacks.indexOf(callback);
                if (index !== -1)
                    callbacks.splice(index, 1);
            };
        }
        $set($$props) {
            if (this.$$set && !is_empty($$props)) {
                this.$$.skip_bound = true;
                this.$$set($$props);
                this.$$.skip_bound = false;
            }
        }
    }

    function dispatch_dev(type, detail) {
        document.dispatchEvent(custom_event(type, Object.assign({ version: '3.59.2' }, detail), { bubbles: true }));
    }
    function append_dev(target, node) {
        dispatch_dev('SvelteDOMInsert', { target, node });
        append(target, node);
    }
    function insert_dev(target, node, anchor) {
        dispatch_dev('SvelteDOMInsert', { target, node, anchor });
        insert(target, node, anchor);
    }
    function detach_dev(node) {
        dispatch_dev('SvelteDOMRemove', { node });
        detach(node);
    }
    function listen_dev(node, event, handler, options, has_prevent_default, has_stop_propagation, has_stop_immediate_propagation) {
        const modifiers = options === true ? ['capture'] : options ? Array.from(Object.keys(options)) : [];
        if (has_prevent_default)
            modifiers.push('preventDefault');
        if (has_stop_propagation)
            modifiers.push('stopPropagation');
        if (has_stop_immediate_propagation)
            modifiers.push('stopImmediatePropagation');
        dispatch_dev('SvelteDOMAddEventListener', { node, event, handler, modifiers });
        const dispose = listen(node, event, handler, options);
        return () => {
            dispatch_dev('SvelteDOMRemoveEventListener', { node, event, handler, modifiers });
            dispose();
        };
    }
    function attr_dev(node, attribute, value) {
        attr(node, attribute, value);
        if (value == null)
            dispatch_dev('SvelteDOMRemoveAttribute', { node, attribute });
        else
            dispatch_dev('SvelteDOMSetAttribute', { node, attribute, value });
    }
    function set_data_dev(text, data) {
        data = '' + data;
        if (text.data === data)
            return;
        dispatch_dev('SvelteDOMSetData', { node: text, data });
        text.data = data;
    }
    function validate_each_argument(arg) {
        if (typeof arg !== 'string' && !(arg && typeof arg === 'object' && 'length' in arg)) {
            let msg = '{#each} only iterates over array-like objects.';
            if (typeof Symbol === 'function' && arg && Symbol.iterator in arg) {
                msg += ' You can use a spread to convert this iterable into an array.';
            }
            throw new Error(msg);
        }
    }
    function validate_slots(name, slot, keys) {
        for (const slot_key of Object.keys(slot)) {
            if (!~keys.indexOf(slot_key)) {
                console.warn(`<${name}> received an unexpected slot "${slot_key}".`);
            }
        }
    }
    /**
     * Base class for Svelte components with some minor dev-enhancements. Used when dev=true.
     */
    class SvelteComponentDev extends SvelteComponent {
        constructor(options) {
            if (!options || (!options.target && !options.$$inline)) {
                throw new Error("'target' is a required option");
            }
            super();
        }
        $destroy() {
            super.$destroy();
            this.$destroy = () => {
                console.warn('Component was already destroyed'); // eslint-disable-line no-console
            };
        }
        $capture_state() { }
        $inject_state() { }
    }

    /* App.svelte generated by Svelte v3.59.2 */

    const { console: console_1 } = globals;
    const file = "App.svelte";

    function get_each_context(ctx, list, i) {
    	const child_ctx = ctx.slice();
    	child_ctx[29] = list[i];
    	return child_ctx;
    }

    function get_each_context_1(ctx, list, i) {
    	const child_ctx = ctx.slice();
    	child_ctx[32] = list[i][0];
    	child_ctx[33] = list[i][1];
    	return child_ctx;
    }

    function get_each_context_2(ctx, list, i) {
    	const child_ctx = ctx.slice();
    	child_ctx[32] = list[i][0];
    	child_ctx[33] = list[i][1];
    	return child_ctx;
    }

    // (271:10) {:else}
    function create_else_block_1(ctx) {
    	let t;

    	const block = {
    		c: function create() {
    			t = text("Disconnected");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},
    		p: noop,
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(t);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_else_block_1.name,
    		type: "else",
    		source: "(271:10) {:else}",
    		ctx
    	});

    	return block;
    }

    // (269:10) {#if isConnected}
    function create_if_block_4(ctx) {
    	let t0;
    	let t1_value = /*getConnectionStatus*/ ctx[14]() + "";
    	let t1;
    	let t2;

    	const block = {
    		c: function create() {
    			t0 = text("Connected (");
    			t1 = text(t1_value);
    			t2 = text(")");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, t0, anchor);
    			insert_dev(target, t1, anchor);
    			insert_dev(target, t2, anchor);
    		},
    		p: noop,
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(t0);
    			if (detaching) detach_dev(t1);
    			if (detaching) detach_dev(t2);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block_4.name,
    		type: "if",
    		source: "(269:10) {#if isConnected}",
    		ctx
    	});

    	return block;
    }

    // (275:8) {#if lastHeartbeat}
    function create_if_block_3(ctx) {
    	let span;
    	let t0;
    	let t1_value = formatTime(/*lastHeartbeat*/ ctx[9]) + "";
    	let t1;

    	const block = {
    		c: function create() {
    			span = element("span");
    			t0 = text("Last heartbeat: ");
    			t1 = text(t1_value);
    			attr_dev(span, "class", "heartbeat-time svelte-94kqpu");
    			add_location(span, file, 275, 10, 7333);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, span, anchor);
    			append_dev(span, t0);
    			append_dev(span, t1);
    		},
    		p: function update(ctx, dirty) {
    			if (dirty[0] & /*lastHeartbeat*/ 512 && t1_value !== (t1_value = formatTime(/*lastHeartbeat*/ ctx[9]) + "")) set_data_dev(t1, t1_value);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(span);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block_3.name,
    		type: "if",
    		source: "(275:8) {#if lastHeartbeat}",
    		ctx
    	});

    	return block;
    }

    // (298:10) {:else}
    function create_else_block(ctx) {
    	let t;

    	const block = {
    		c: function create() {
    			t = text("➡️ FLAT");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(t);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_else_block.name,
    		type: "else",
    		source: "(298:10) {:else}",
    		ctx
    	});

    	return block;
    }

    // (296:46) 
    function create_if_block_2(ctx) {
    	let t;

    	const block = {
    		c: function create() {
    			t = text("↘️ DOWN");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(t);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block_2.name,
    		type: "if",
    		source: "(296:46) ",
    		ctx
    	});

    	return block;
    }

    // (294:10) {#if priceDirection === 'up'}
    function create_if_block_1(ctx) {
    	let t;

    	const block = {
    		c: function create() {
    			t = text("↗️ UP");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, t, anchor);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(t);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block_1.name,
    		type: "if",
    		source: "(294:10) {#if priceDirection === 'up'}",
    		ctx
    	});

    	return block;
    }

    // (331:6) {#if largestTrade}
    function create_if_block(ctx) {
    	let div3;
    	let div0;
    	let t1;
    	let div1;
    	let t2_value = formatSize(/*largestTrade*/ ctx[6].size) + "";
    	let t2;
    	let t3;
    	let t4;
    	let div2;
    	let span0;
    	let t5_value = /*largestTrade*/ ctx[6].side.toUpperCase() + "";
    	let t5;
    	let t6;
    	let span1;
    	let t7_value = formatPrice(/*largestTrade*/ ctx[6].price) + "";
    	let t7;
    	let t8;
    	let span2;
    	let t9_value = formatTime(/*largestTrade*/ ctx[6].timestamp) + "";
    	let t9;
    	let div3_class_value;

    	const block = {
    		c: function create() {
    			div3 = element("div");
    			div0 = element("div");
    			div0.textContent = "Largest Trade";
    			t1 = space();
    			div1 = element("div");
    			t2 = text(t2_value);
    			t3 = text(" BTC");
    			t4 = space();
    			div2 = element("div");
    			span0 = element("span");
    			t5 = text(t5_value);
    			t6 = space();
    			span1 = element("span");
    			t7 = text(t7_value);
    			t8 = space();
    			span2 = element("span");
    			t9 = text(t9_value);
    			attr_dev(div0, "class", "stat-label svelte-94kqpu");
    			add_location(div0, file, 332, 8, 9273);
    			attr_dev(div1, "class", "stat-value svelte-94kqpu");
    			add_location(div1, file, 333, 8, 9325);
    			attr_dev(span0, "class", "trade-side svelte-94kqpu");
    			add_location(span0, file, 335, 10, 9436);
    			attr_dev(span1, "class", "trade-price");
    			add_location(span1, file, 336, 10, 9512);
    			attr_dev(span2, "class", "trade-time");
    			add_location(span2, file, 337, 10, 9589);
    			attr_dev(div2, "class", "stat-details svelte-94kqpu");
    			add_location(div2, file, 334, 8, 9399);
    			attr_dev(div3, "class", div3_class_value = "stat-card largest-trade-card " + /*largestTrade*/ ctx[6].side + " svelte-94kqpu");
    			add_location(div3, file, 331, 6, 9202);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div3, anchor);
    			append_dev(div3, div0);
    			append_dev(div3, t1);
    			append_dev(div3, div1);
    			append_dev(div1, t2);
    			append_dev(div1, t3);
    			append_dev(div3, t4);
    			append_dev(div3, div2);
    			append_dev(div2, span0);
    			append_dev(span0, t5);
    			append_dev(div2, t6);
    			append_dev(div2, span1);
    			append_dev(span1, t7);
    			append_dev(div2, t8);
    			append_dev(div2, span2);
    			append_dev(span2, t9);
    		},
    		p: function update(ctx, dirty) {
    			if (dirty[0] & /*largestTrade*/ 64 && t2_value !== (t2_value = formatSize(/*largestTrade*/ ctx[6].size) + "")) set_data_dev(t2, t2_value);
    			if (dirty[0] & /*largestTrade*/ 64 && t5_value !== (t5_value = /*largestTrade*/ ctx[6].side.toUpperCase() + "")) set_data_dev(t5, t5_value);
    			if (dirty[0] & /*largestTrade*/ 64 && t7_value !== (t7_value = formatPrice(/*largestTrade*/ ctx[6].price) + "")) set_data_dev(t7, t7_value);
    			if (dirty[0] & /*largestTrade*/ 64 && t9_value !== (t9_value = formatTime(/*largestTrade*/ ctx[6].timestamp) + "")) set_data_dev(t9, t9_value);

    			if (dirty[0] & /*largestTrade*/ 64 && div3_class_value !== (div3_class_value = "stat-card largest-trade-card " + /*largestTrade*/ ctx[6].side + " svelte-94kqpu")) {
    				attr_dev(div3, "class", div3_class_value);
    			}
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div3);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_if_block.name,
    		type: "if",
    		source: "(331:6) {#if largestTrade}",
    		ctx
    	});

    	return block;
    }

    // (374:12) {#each orderBook.bids as [price, size]}
    function create_each_block_2(ctx) {
    	let div;
    	let span0;
    	let t0_value = formatPrice(parseFloat(/*price*/ ctx[32])) + "";
    	let t0;
    	let t1;
    	let span1;
    	let t2_value = formatSize(parseFloat(/*size*/ ctx[33])) + "";
    	let t2;
    	let t3;

    	const block = {
    		c: function create() {
    			div = element("div");
    			span0 = element("span");
    			t0 = text(t0_value);
    			t1 = space();
    			span1 = element("span");
    			t2 = text(t2_value);
    			t3 = space();
    			attr_dev(span0, "class", "order-price");
    			add_location(span0, file, 375, 16, 10965);
    			attr_dev(span1, "class", "order-size");
    			add_location(span1, file, 376, 16, 11047);
    			attr_dev(div, "class", "order-row bid svelte-94kqpu");
    			add_location(div, file, 374, 14, 10921);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, span0);
    			append_dev(span0, t0);
    			append_dev(div, t1);
    			append_dev(div, span1);
    			append_dev(span1, t2);
    			append_dev(div, t3);
    		},
    		p: function update(ctx, dirty) {
    			if (dirty[0] & /*orderBook*/ 256 && t0_value !== (t0_value = formatPrice(parseFloat(/*price*/ ctx[32])) + "")) set_data_dev(t0, t0_value);
    			if (dirty[0] & /*orderBook*/ 256 && t2_value !== (t2_value = formatSize(parseFloat(/*size*/ ctx[33])) + "")) set_data_dev(t2, t2_value);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_each_block_2.name,
    		type: "each",
    		source: "(374:12) {#each orderBook.bids as [price, size]}",
    		ctx
    	});

    	return block;
    }

    // (386:12) {#each orderBook.asks as [price, size]}
    function create_each_block_1(ctx) {
    	let div;
    	let span0;
    	let t0_value = formatPrice(parseFloat(/*price*/ ctx[32])) + "";
    	let t0;
    	let t1;
    	let span1;
    	let t2_value = formatSize(parseFloat(/*size*/ ctx[33])) + "";
    	let t2;
    	let t3;

    	const block = {
    		c: function create() {
    			div = element("div");
    			span0 = element("span");
    			t0 = text(t0_value);
    			t1 = space();
    			span1 = element("span");
    			t2 = text(t2_value);
    			t3 = space();
    			attr_dev(span0, "class", "order-price");
    			add_location(span0, file, 387, 16, 11404);
    			attr_dev(span1, "class", "order-size");
    			add_location(span1, file, 388, 16, 11486);
    			attr_dev(div, "class", "order-row ask svelte-94kqpu");
    			add_location(div, file, 386, 14, 11360);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, span0);
    			append_dev(span0, t0);
    			append_dev(div, t1);
    			append_dev(div, span1);
    			append_dev(span1, t2);
    			append_dev(div, t3);
    		},
    		p: function update(ctx, dirty) {
    			if (dirty[0] & /*orderBook*/ 256 && t0_value !== (t0_value = formatPrice(parseFloat(/*price*/ ctx[32])) + "")) set_data_dev(t0, t0_value);
    			if (dirty[0] & /*orderBook*/ 256 && t2_value !== (t2_value = formatSize(parseFloat(/*size*/ ctx[33])) + "")) set_data_dev(t2, t2_value);
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_each_block_1.name,
    		type: "each",
    		source: "(386:12) {#each orderBook.asks as [price, size]}",
    		ctx
    	});

    	return block;
    }

    // (400:8) {#each trades.slice(0, 10) as trade}
    function create_each_block(ctx) {
    	let div;
    	let span0;
    	let t0_value = /*trade*/ ctx[29].side.toUpperCase() + "";
    	let t0;
    	let t1;
    	let span1;
    	let t2_value = formatSize(/*trade*/ ctx[29].size) + "";
    	let t2;
    	let t3;
    	let t4;
    	let span2;
    	let t5_value = formatPrice(/*trade*/ ctx[29].price) + "";
    	let t5;
    	let t6;
    	let span3;
    	let t7_value = formatTime(/*trade*/ ctx[29].timestamp) + "";
    	let t7;
    	let t8;
    	let div_class_value;

    	const block = {
    		c: function create() {
    			div = element("div");
    			span0 = element("span");
    			t0 = text(t0_value);
    			t1 = space();
    			span1 = element("span");
    			t2 = text(t2_value);
    			t3 = text(" BTC");
    			t4 = space();
    			span2 = element("span");
    			t5 = text(t5_value);
    			t6 = space();
    			span3 = element("span");
    			t7 = text(t7_value);
    			t8 = space();
    			attr_dev(span0, "class", "trade-side svelte-94kqpu");
    			add_location(span0, file, 401, 12, 11850);
    			attr_dev(span1, "class", "trade-size");
    			add_location(span1, file, 402, 12, 11921);
    			attr_dev(span2, "class", "trade-price");
    			add_location(span2, file, 403, 12, 11994);
    			attr_dev(span3, "class", "trade-time");
    			add_location(span3, file, 404, 12, 12066);
    			attr_dev(div, "class", div_class_value = "trade-item " + /*trade*/ ctx[29].side + " svelte-94kqpu");
    			add_location(div, file, 400, 10, 11800);
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, div, anchor);
    			append_dev(div, span0);
    			append_dev(span0, t0);
    			append_dev(div, t1);
    			append_dev(div, span1);
    			append_dev(span1, t2);
    			append_dev(span1, t3);
    			append_dev(div, t4);
    			append_dev(div, span2);
    			append_dev(span2, t5);
    			append_dev(div, t6);
    			append_dev(div, span3);
    			append_dev(span3, t7);
    			append_dev(div, t8);
    		},
    		p: function update(ctx, dirty) {
    			if (dirty[0] & /*trades*/ 4 && t0_value !== (t0_value = /*trade*/ ctx[29].side.toUpperCase() + "")) set_data_dev(t0, t0_value);
    			if (dirty[0] & /*trades*/ 4 && t2_value !== (t2_value = formatSize(/*trade*/ ctx[29].size) + "")) set_data_dev(t2, t2_value);
    			if (dirty[0] & /*trades*/ 4 && t5_value !== (t5_value = formatPrice(/*trade*/ ctx[29].price) + "")) set_data_dev(t5, t5_value);
    			if (dirty[0] & /*trades*/ 4 && t7_value !== (t7_value = formatTime(/*trade*/ ctx[29].timestamp) + "")) set_data_dev(t7, t7_value);

    			if (dirty[0] & /*trades*/ 4 && div_class_value !== (div_class_value = "trade-item " + /*trade*/ ctx[29].side + " svelte-94kqpu")) {
    				attr_dev(div, "class", div_class_value);
    			}
    		},
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(div);
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_each_block.name,
    		type: "each",
    		source: "(400:8) {#each trades.slice(0, 10) as trade}",
    		ctx
    	});

    	return block;
    }

    function create_fragment(ctx) {
    	let main;
    	let div55;
    	let header;
    	let h1;
    	let t1;
    	let h20;
    	let t3;
    	let div0;
    	let span;
    	let t4;
    	let t5;
    	let div1;
    	let button;

    	let t6_value = (/*audioEnabled*/ ctx[12]
    	? '🔊 Audio On'
    	: '🔇 Audio Off') + "";

    	let t6;
    	let button_class_value;
    	let t7;
    	let div6;
    	let div5;
    	let div2;
    	let t9;
    	let div3;
    	let t10_value = formatPrice(/*currentPrice*/ ctx[1]) + "";
    	let t10;
    	let t11;
    	let div4;
    	let div5_class_value;
    	let t12;
    	let div25;
    	let div9;
    	let div7;
    	let t14;
    	let div8;
    	let t15_value = /*tradesPerSecond*/ ctx[5].toFixed(2) + "";
    	let t15;
    	let t16;
    	let div12;
    	let div10;
    	let t18;
    	let div11;
    	let t19;
    	let t20;
    	let div15;
    	let div13;
    	let t22;
    	let div14;
    	let t23_value = formatSize(/*avgTradeSize*/ ctx[4]) + "";
    	let t23;
    	let t24;
    	let t25;
    	let div18;
    	let div16;
    	let t27;
    	let div17;
    	let t28_value = formatVolume(/*tickerData*/ ctx[7].volume24h) + "";
    	let t28;
    	let t29;
    	let t30;
    	let div21;
    	let div19;
    	let t32;
    	let div20;
    	let t33_value = formatPrice(/*tickerData*/ ctx[7].high24h) + "";
    	let t33;
    	let t34;
    	let div24;
    	let div22;
    	let t36;
    	let div23;
    	let t37_value = formatPrice(/*tickerData*/ ctx[7].low24h) + "";
    	let t37;
    	let t38;
    	let t39;
    	let div47;
    	let h21;
    	let t41;
    	let div41;
    	let div28;
    	let div26;
    	let t43;
    	let div27;
    	let t44_value = formatPrice(/*tickerData*/ ctx[7].spread) + "";
    	let t44;
    	let t45;
    	let div31;
    	let div29;
    	let t47;
    	let div30;
    	let t48_value = formatPrice(/*tickerData*/ ctx[7].bestBid) + "";
    	let t48;
    	let t49;
    	let div34;
    	let div32;
    	let t51;
    	let div33;
    	let t52_value = formatPrice(/*tickerData*/ ctx[7].bestAsk) + "";
    	let t52;
    	let t53;
    	let div37;
    	let div35;
    	let t55;
    	let div36;
    	let t56_value = formatSize(/*orderBook*/ ctx[8].bidDepth) + "";
    	let t56;
    	let t57;
    	let t58;
    	let div40;
    	let div38;
    	let t60;
    	let div39;
    	let t61_value = formatSize(/*orderBook*/ ctx[8].askDepth) + "";
    	let t61;
    	let t62;
    	let t63;
    	let div46;
    	let div43;
    	let h30;
    	let t65;
    	let div42;
    	let t66;
    	let div45;
    	let h31;
    	let t68;
    	let div44;
    	let t69;
    	let div49;
    	let h22;
    	let t71;
    	let div48;
    	let t72;
    	let div54;
    	let div52;
    	let div50;
    	let t73;
    	let div51;
    	let t75;
    	let div53;
    	let div53_class_value;
    	let mounted;
    	let dispose;

    	function select_block_type(ctx, dirty) {
    		if (/*isConnected*/ ctx[0]) return create_if_block_4;
    		return create_else_block_1;
    	}

    	let current_block_type = select_block_type(ctx);
    	let if_block0 = current_block_type(ctx);
    	let if_block1 = /*lastHeartbeat*/ ctx[9] && create_if_block_3(ctx);

    	function select_block_type_1(ctx, dirty) {
    		if (/*priceDirection*/ ctx[10] === 'up') return create_if_block_1;
    		if (/*priceDirection*/ ctx[10] === 'down') return create_if_block_2;
    		return create_else_block;
    	}

    	let current_block_type_1 = select_block_type_1(ctx);
    	let if_block2 = current_block_type_1(ctx);
    	let if_block3 = /*largestTrade*/ ctx[6] && create_if_block(ctx);
    	let each_value_2 = /*orderBook*/ ctx[8].bids;
    	validate_each_argument(each_value_2);
    	let each_blocks_2 = [];

    	for (let i = 0; i < each_value_2.length; i += 1) {
    		each_blocks_2[i] = create_each_block_2(get_each_context_2(ctx, each_value_2, i));
    	}

    	let each_value_1 = /*orderBook*/ ctx[8].asks;
    	validate_each_argument(each_value_1);
    	let each_blocks_1 = [];

    	for (let i = 0; i < each_value_1.length; i += 1) {
    		each_blocks_1[i] = create_each_block_1(get_each_context_1(ctx, each_value_1, i));
    	}

    	let each_value = /*trades*/ ctx[2].slice(0, 10);
    	validate_each_argument(each_value);
    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block(get_each_context(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			main = element("main");
    			div55 = element("div");
    			header = element("header");
    			h1 = element("h1");
    			h1.textContent = "🎵 BTC Beeper 🎵";
    			t1 = space();
    			h20 = element("h2");
    			h20.textContent = "Audio Visualizer";
    			t3 = space();
    			div0 = element("div");
    			span = element("span");
    			if_block0.c();
    			t4 = space();
    			if (if_block1) if_block1.c();
    			t5 = space();
    			div1 = element("div");
    			button = element("button");
    			t6 = text(t6_value);
    			t7 = space();
    			div6 = element("div");
    			div5 = element("div");
    			div2 = element("div");
    			div2.textContent = "BTC/USD";
    			t9 = space();
    			div3 = element("div");
    			t10 = text(t10_value);
    			t11 = space();
    			div4 = element("div");
    			if_block2.c();
    			t12 = space();
    			div25 = element("div");
    			div9 = element("div");
    			div7 = element("div");
    			div7.textContent = "Trades/Second";
    			t14 = space();
    			div8 = element("div");
    			t15 = text(t15_value);
    			t16 = space();
    			div12 = element("div");
    			div10 = element("div");
    			div10.textContent = "Total Trades";
    			t18 = space();
    			div11 = element("div");
    			t19 = text(/*tradeCount*/ ctx[3]);
    			t20 = space();
    			div15 = element("div");
    			div13 = element("div");
    			div13.textContent = "Avg Trade Size";
    			t22 = space();
    			div14 = element("div");
    			t23 = text(t23_value);
    			t24 = text(" BTC");
    			t25 = space();
    			div18 = element("div");
    			div16 = element("div");
    			div16.textContent = "24h Volume";
    			t27 = space();
    			div17 = element("div");
    			t28 = text(t28_value);
    			t29 = text(" BTC");
    			t30 = space();
    			div21 = element("div");
    			div19 = element("div");
    			div19.textContent = "24h High";
    			t32 = space();
    			div20 = element("div");
    			t33 = text(t33_value);
    			t34 = space();
    			div24 = element("div");
    			div22 = element("div");
    			div22.textContent = "24h Low";
    			t36 = space();
    			div23 = element("div");
    			t37 = text(t37_value);
    			t38 = space();
    			if (if_block3) if_block3.c();
    			t39 = space();
    			div47 = element("div");
    			h21 = element("h2");
    			h21.textContent = "Order Book";
    			t41 = space();
    			div41 = element("div");
    			div28 = element("div");
    			div26 = element("div");
    			div26.textContent = "Spread";
    			t43 = space();
    			div27 = element("div");
    			t44 = text(t44_value);
    			t45 = space();
    			div31 = element("div");
    			div29 = element("div");
    			div29.textContent = "Best Bid";
    			t47 = space();
    			div30 = element("div");
    			t48 = text(t48_value);
    			t49 = space();
    			div34 = element("div");
    			div32 = element("div");
    			div32.textContent = "Best Ask";
    			t51 = space();
    			div33 = element("div");
    			t52 = text(t52_value);
    			t53 = space();
    			div37 = element("div");
    			div35 = element("div");
    			div35.textContent = "Bid Depth";
    			t55 = space();
    			div36 = element("div");
    			t56 = text(t56_value);
    			t57 = text(" BTC");
    			t58 = space();
    			div40 = element("div");
    			div38 = element("div");
    			div38.textContent = "Ask Depth";
    			t60 = space();
    			div39 = element("div");
    			t61 = text(t61_value);
    			t62 = text(" BTC");
    			t63 = space();
    			div46 = element("div");
    			div43 = element("div");
    			h30 = element("h3");
    			h30.textContent = "Bids";
    			t65 = space();
    			div42 = element("div");

    			for (let i = 0; i < each_blocks_2.length; i += 1) {
    				each_blocks_2[i].c();
    			}

    			t66 = space();
    			div45 = element("div");
    			h31 = element("h3");
    			h31.textContent = "Asks";
    			t68 = space();
    			div44 = element("div");

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				each_blocks_1[i].c();
    			}

    			t69 = space();
    			div49 = element("div");
    			h22 = element("h2");
    			h22.textContent = "Recent Trades";
    			t71 = space();
    			div48 = element("div");

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t72 = space();
    			div54 = element("div");
    			div52 = element("div");
    			div50 = element("div");
    			t73 = space();
    			div51 = element("div");
    			div51.textContent = "Volume Intensity";
    			t75 = space();
    			div53 = element("div");
    			attr_dev(h1, "class", "svelte-94kqpu");
    			add_location(h1, file, 263, 6, 7004);
    			add_location(h20, file, 264, 6, 7037);
    			attr_dev(span, "class", "status-text");
    			add_location(span, file, 267, 8, 7117);
    			attr_dev(div0, "class", "connection-status svelte-94kqpu");
    			add_location(div0, file, 265, 6, 7069);
    			attr_dev(header, "class", "svelte-94kqpu");
    			add_location(header, file, 262, 4, 6989);
    			attr_dev(button, "class", button_class_value = "audio-toggle " + (/*audioEnabled*/ ctx[12] ? 'enabled' : 'disabled') + " svelte-94kqpu");
    			add_location(button, file, 283, 6, 7516);
    			attr_dev(div1, "class", "controls svelte-94kqpu");
    			add_location(div1, file, 282, 4, 7487);
    			attr_dev(div2, "class", "price-label svelte-94kqpu");
    			add_location(div2, file, 290, 8, 7784);
    			attr_dev(div3, "class", "price-value svelte-94kqpu");
    			add_location(div3, file, 291, 8, 7831);
    			attr_dev(div4, "class", "price-change svelte-94kqpu");
    			add_location(div4, file, 292, 8, 7898);
    			attr_dev(div5, "class", div5_class_value = "current-price " + /*priceDirection*/ ctx[10] + " svelte-94kqpu");
    			add_location(div5, file, 289, 6, 7731);
    			attr_dev(div6, "class", "price-section svelte-94kqpu");
    			add_location(div6, file, 288, 4, 7697);
    			attr_dev(div7, "class", "stat-label svelte-94kqpu");
    			add_location(div7, file, 307, 8, 8244);
    			attr_dev(div8, "class", "stat-value svelte-94kqpu");
    			add_location(div8, file, 308, 8, 8296);
    			attr_dev(div9, "class", "stat-card svelte-94kqpu");
    			add_location(div9, file, 306, 6, 8212);
    			attr_dev(div10, "class", "stat-label svelte-94kqpu");
    			add_location(div10, file, 311, 8, 8406);
    			attr_dev(div11, "class", "stat-value svelte-94kqpu");
    			add_location(div11, file, 312, 8, 8457);
    			attr_dev(div12, "class", "stat-card svelte-94kqpu");
    			add_location(div12, file, 310, 6, 8374);
    			attr_dev(div13, "class", "stat-label svelte-94kqpu");
    			add_location(div13, file, 315, 8, 8551);
    			attr_dev(div14, "class", "stat-value svelte-94kqpu");
    			add_location(div14, file, 316, 8, 8604);
    			attr_dev(div15, "class", "stat-card svelte-94kqpu");
    			add_location(div15, file, 314, 6, 8519);
    			attr_dev(div16, "class", "stat-label svelte-94kqpu");
    			add_location(div16, file, 319, 8, 8716);
    			attr_dev(div17, "class", "stat-value svelte-94kqpu");
    			add_location(div17, file, 320, 8, 8765);
    			attr_dev(div18, "class", "stat-card svelte-94kqpu");
    			add_location(div18, file, 318, 6, 8684);
    			attr_dev(div19, "class", "stat-label svelte-94kqpu");
    			add_location(div19, file, 323, 8, 8887);
    			attr_dev(div20, "class", "stat-value svelte-94kqpu");
    			add_location(div20, file, 324, 8, 8934);
    			attr_dev(div21, "class", "stat-card svelte-94kqpu");
    			add_location(div21, file, 322, 6, 8855);
    			attr_dev(div22, "class", "stat-label svelte-94kqpu");
    			add_location(div22, file, 327, 8, 9049);
    			attr_dev(div23, "class", "stat-value svelte-94kqpu");
    			add_location(div23, file, 328, 8, 9095);
    			attr_dev(div24, "class", "stat-card svelte-94kqpu");
    			add_location(div24, file, 326, 6, 9017);
    			attr_dev(div25, "class", "stats-grid svelte-94kqpu");
    			add_location(div25, file, 305, 4, 8181);
    			attr_dev(h21, "class", "svelte-94kqpu");
    			add_location(h21, file, 345, 6, 9784);
    			attr_dev(div26, "class", "stat-label svelte-94kqpu");
    			add_location(div26, file, 348, 10, 9882);
    			attr_dev(div27, "class", "stat-value svelte-94kqpu");
    			add_location(div27, file, 349, 10, 9929);
    			attr_dev(div28, "class", "stat-card svelte-94kqpu");
    			add_location(div28, file, 347, 8, 9848);
    			attr_dev(div29, "class", "stat-label svelte-94kqpu");
    			add_location(div29, file, 352, 10, 10049);
    			attr_dev(div30, "class", "stat-value svelte-94kqpu");
    			add_location(div30, file, 353, 10, 10098);
    			attr_dev(div31, "class", "stat-card svelte-94kqpu");
    			add_location(div31, file, 351, 8, 10015);
    			attr_dev(div32, "class", "stat-label svelte-94kqpu");
    			add_location(div32, file, 356, 10, 10219);
    			attr_dev(div33, "class", "stat-value svelte-94kqpu");
    			add_location(div33, file, 357, 10, 10268);
    			attr_dev(div34, "class", "stat-card svelte-94kqpu");
    			add_location(div34, file, 355, 8, 10185);
    			attr_dev(div35, "class", "stat-label svelte-94kqpu");
    			add_location(div35, file, 360, 10, 10389);
    			attr_dev(div36, "class", "stat-value svelte-94kqpu");
    			add_location(div36, file, 361, 10, 10439);
    			attr_dev(div37, "class", "stat-card svelte-94kqpu");
    			add_location(div37, file, 359, 8, 10355);
    			attr_dev(div38, "class", "stat-label svelte-94kqpu");
    			add_location(div38, file, 364, 10, 10563);
    			attr_dev(div39, "class", "stat-value svelte-94kqpu");
    			add_location(div39, file, 365, 10, 10613);
    			attr_dev(div40, "class", "stat-card svelte-94kqpu");
    			add_location(div40, file, 363, 8, 10529);
    			attr_dev(div41, "class", "orderbook-stats svelte-94kqpu");
    			add_location(div41, file, 346, 6, 9810);
    			attr_dev(h30, "class", "svelte-94kqpu");
    			add_location(h30, file, 371, 10, 10800);
    			attr_dev(div42, "class", "orderbook-orders svelte-94kqpu");
    			add_location(div42, file, 372, 10, 10824);
    			attr_dev(div43, "class", "orderbook-side svelte-94kqpu");
    			add_location(div43, file, 370, 8, 10761);
    			attr_dev(h31, "class", "svelte-94kqpu");
    			add_location(h31, file, 383, 10, 11239);
    			attr_dev(div44, "class", "orderbook-orders svelte-94kqpu");
    			add_location(div44, file, 384, 10, 11263);
    			attr_dev(div45, "class", "orderbook-side svelte-94kqpu");
    			add_location(div45, file, 382, 8, 11200);
    			attr_dev(div46, "class", "orderbook-display svelte-94kqpu");
    			add_location(div46, file, 369, 6, 10721);
    			attr_dev(div47, "class", "orderbook-section svelte-94kqpu");
    			add_location(div47, file, 344, 4, 9746);
    			attr_dev(h22, "class", "svelte-94kqpu");
    			add_location(h22, file, 397, 6, 11690);
    			attr_dev(div48, "class", "trades-list svelte-94kqpu");
    			add_location(div48, file, 398, 6, 11719);
    			attr_dev(div49, "class", "trades-section svelte-94kqpu");
    			add_location(div49, file, 396, 4, 11655);
    			attr_dev(div50, "class", "volume-fill svelte-94kqpu");
    			set_style(div50, "width", /*volumeIntensity*/ ctx[11] * 100 + "%");
    			add_location(div50, file, 412, 8, 12258);
    			attr_dev(div51, "class", "volume-label svelte-94kqpu");
    			add_location(div51, file, 413, 8, 12338);
    			attr_dev(div52, "class", "volume-bar svelte-94kqpu");
    			add_location(div52, file, 411, 6, 12225);
    			attr_dev(div53, "class", div53_class_value = "pulse-indicator " + (/*audioEnabled*/ ctx[12] ? 'active' : '') + " svelte-94kqpu");
    			add_location(div53, file, 415, 6, 12406);
    			attr_dev(div54, "class", "visualizer svelte-94kqpu");
    			add_location(div54, file, 410, 4, 12194);
    			attr_dev(div55, "class", "container svelte-94kqpu");
    			add_location(div55, file, 261, 2, 6961);
    			add_location(main, file, 260, 0, 6952);
    		},
    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, main, anchor);
    			append_dev(main, div55);
    			append_dev(div55, header);
    			append_dev(header, h1);
    			append_dev(header, t1);
    			append_dev(header, h20);
    			append_dev(header, t3);
    			append_dev(header, div0);
    			append_dev(div0, span);
    			if_block0.m(span, null);
    			append_dev(div0, t4);
    			if (if_block1) if_block1.m(div0, null);
    			append_dev(div55, t5);
    			append_dev(div55, div1);
    			append_dev(div1, button);
    			append_dev(button, t6);
    			append_dev(div55, t7);
    			append_dev(div55, div6);
    			append_dev(div6, div5);
    			append_dev(div5, div2);
    			append_dev(div5, t9);
    			append_dev(div5, div3);
    			append_dev(div3, t10);
    			append_dev(div5, t11);
    			append_dev(div5, div4);
    			if_block2.m(div4, null);
    			append_dev(div55, t12);
    			append_dev(div55, div25);
    			append_dev(div25, div9);
    			append_dev(div9, div7);
    			append_dev(div9, t14);
    			append_dev(div9, div8);
    			append_dev(div8, t15);
    			append_dev(div25, t16);
    			append_dev(div25, div12);
    			append_dev(div12, div10);
    			append_dev(div12, t18);
    			append_dev(div12, div11);
    			append_dev(div11, t19);
    			append_dev(div25, t20);
    			append_dev(div25, div15);
    			append_dev(div15, div13);
    			append_dev(div15, t22);
    			append_dev(div15, div14);
    			append_dev(div14, t23);
    			append_dev(div14, t24);
    			append_dev(div25, t25);
    			append_dev(div25, div18);
    			append_dev(div18, div16);
    			append_dev(div18, t27);
    			append_dev(div18, div17);
    			append_dev(div17, t28);
    			append_dev(div17, t29);
    			append_dev(div25, t30);
    			append_dev(div25, div21);
    			append_dev(div21, div19);
    			append_dev(div21, t32);
    			append_dev(div21, div20);
    			append_dev(div20, t33);
    			append_dev(div25, t34);
    			append_dev(div25, div24);
    			append_dev(div24, div22);
    			append_dev(div24, t36);
    			append_dev(div24, div23);
    			append_dev(div23, t37);
    			append_dev(div25, t38);
    			if (if_block3) if_block3.m(div25, null);
    			append_dev(div55, t39);
    			append_dev(div55, div47);
    			append_dev(div47, h21);
    			append_dev(div47, t41);
    			append_dev(div47, div41);
    			append_dev(div41, div28);
    			append_dev(div28, div26);
    			append_dev(div28, t43);
    			append_dev(div28, div27);
    			append_dev(div27, t44);
    			append_dev(div41, t45);
    			append_dev(div41, div31);
    			append_dev(div31, div29);
    			append_dev(div31, t47);
    			append_dev(div31, div30);
    			append_dev(div30, t48);
    			append_dev(div41, t49);
    			append_dev(div41, div34);
    			append_dev(div34, div32);
    			append_dev(div34, t51);
    			append_dev(div34, div33);
    			append_dev(div33, t52);
    			append_dev(div41, t53);
    			append_dev(div41, div37);
    			append_dev(div37, div35);
    			append_dev(div37, t55);
    			append_dev(div37, div36);
    			append_dev(div36, t56);
    			append_dev(div36, t57);
    			append_dev(div41, t58);
    			append_dev(div41, div40);
    			append_dev(div40, div38);
    			append_dev(div40, t60);
    			append_dev(div40, div39);
    			append_dev(div39, t61);
    			append_dev(div39, t62);
    			append_dev(div47, t63);
    			append_dev(div47, div46);
    			append_dev(div46, div43);
    			append_dev(div43, h30);
    			append_dev(div43, t65);
    			append_dev(div43, div42);

    			for (let i = 0; i < each_blocks_2.length; i += 1) {
    				if (each_blocks_2[i]) {
    					each_blocks_2[i].m(div42, null);
    				}
    			}

    			append_dev(div46, t66);
    			append_dev(div46, div45);
    			append_dev(div45, h31);
    			append_dev(div45, t68);
    			append_dev(div45, div44);

    			for (let i = 0; i < each_blocks_1.length; i += 1) {
    				if (each_blocks_1[i]) {
    					each_blocks_1[i].m(div44, null);
    				}
    			}

    			append_dev(div55, t69);
    			append_dev(div55, div49);
    			append_dev(div49, h22);
    			append_dev(div49, t71);
    			append_dev(div49, div48);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				if (each_blocks[i]) {
    					each_blocks[i].m(div48, null);
    				}
    			}

    			append_dev(div55, t72);
    			append_dev(div55, div54);
    			append_dev(div54, div52);
    			append_dev(div52, div50);
    			append_dev(div52, t73);
    			append_dev(div52, div51);
    			append_dev(div54, t75);
    			append_dev(div54, div53);

    			if (!mounted) {
    				dispose = listen_dev(button, "click", /*toggleAudio*/ ctx[13], false, false, false, false);
    				mounted = true;
    			}
    		},
    		p: function update(ctx, dirty) {
    			if (current_block_type === (current_block_type = select_block_type(ctx)) && if_block0) {
    				if_block0.p(ctx, dirty);
    			} else {
    				if_block0.d(1);
    				if_block0 = current_block_type(ctx);

    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(span, null);
    				}
    			}

    			if (/*lastHeartbeat*/ ctx[9]) {
    				if (if_block1) {
    					if_block1.p(ctx, dirty);
    				} else {
    					if_block1 = create_if_block_3(ctx);
    					if_block1.c();
    					if_block1.m(div0, null);
    				}
    			} else if (if_block1) {
    				if_block1.d(1);
    				if_block1 = null;
    			}

    			if (dirty[0] & /*audioEnabled*/ 4096 && t6_value !== (t6_value = (/*audioEnabled*/ ctx[12]
    			? '🔊 Audio On'
    			: '🔇 Audio Off') + "")) set_data_dev(t6, t6_value);

    			if (dirty[0] & /*audioEnabled*/ 4096 && button_class_value !== (button_class_value = "audio-toggle " + (/*audioEnabled*/ ctx[12] ? 'enabled' : 'disabled') + " svelte-94kqpu")) {
    				attr_dev(button, "class", button_class_value);
    			}

    			if (dirty[0] & /*currentPrice*/ 2 && t10_value !== (t10_value = formatPrice(/*currentPrice*/ ctx[1]) + "")) set_data_dev(t10, t10_value);

    			if (current_block_type_1 !== (current_block_type_1 = select_block_type_1(ctx))) {
    				if_block2.d(1);
    				if_block2 = current_block_type_1(ctx);

    				if (if_block2) {
    					if_block2.c();
    					if_block2.m(div4, null);
    				}
    			}

    			if (dirty[0] & /*priceDirection*/ 1024 && div5_class_value !== (div5_class_value = "current-price " + /*priceDirection*/ ctx[10] + " svelte-94kqpu")) {
    				attr_dev(div5, "class", div5_class_value);
    			}

    			if (dirty[0] & /*tradesPerSecond*/ 32 && t15_value !== (t15_value = /*tradesPerSecond*/ ctx[5].toFixed(2) + "")) set_data_dev(t15, t15_value);
    			if (dirty[0] & /*tradeCount*/ 8) set_data_dev(t19, /*tradeCount*/ ctx[3]);
    			if (dirty[0] & /*avgTradeSize*/ 16 && t23_value !== (t23_value = formatSize(/*avgTradeSize*/ ctx[4]) + "")) set_data_dev(t23, t23_value);
    			if (dirty[0] & /*tickerData*/ 128 && t28_value !== (t28_value = formatVolume(/*tickerData*/ ctx[7].volume24h) + "")) set_data_dev(t28, t28_value);
    			if (dirty[0] & /*tickerData*/ 128 && t33_value !== (t33_value = formatPrice(/*tickerData*/ ctx[7].high24h) + "")) set_data_dev(t33, t33_value);
    			if (dirty[0] & /*tickerData*/ 128 && t37_value !== (t37_value = formatPrice(/*tickerData*/ ctx[7].low24h) + "")) set_data_dev(t37, t37_value);

    			if (/*largestTrade*/ ctx[6]) {
    				if (if_block3) {
    					if_block3.p(ctx, dirty);
    				} else {
    					if_block3 = create_if_block(ctx);
    					if_block3.c();
    					if_block3.m(div25, null);
    				}
    			} else if (if_block3) {
    				if_block3.d(1);
    				if_block3 = null;
    			}

    			if (dirty[0] & /*tickerData*/ 128 && t44_value !== (t44_value = formatPrice(/*tickerData*/ ctx[7].spread) + "")) set_data_dev(t44, t44_value);
    			if (dirty[0] & /*tickerData*/ 128 && t48_value !== (t48_value = formatPrice(/*tickerData*/ ctx[7].bestBid) + "")) set_data_dev(t48, t48_value);
    			if (dirty[0] & /*tickerData*/ 128 && t52_value !== (t52_value = formatPrice(/*tickerData*/ ctx[7].bestAsk) + "")) set_data_dev(t52, t52_value);
    			if (dirty[0] & /*orderBook*/ 256 && t56_value !== (t56_value = formatSize(/*orderBook*/ ctx[8].bidDepth) + "")) set_data_dev(t56, t56_value);
    			if (dirty[0] & /*orderBook*/ 256 && t61_value !== (t61_value = formatSize(/*orderBook*/ ctx[8].askDepth) + "")) set_data_dev(t61, t61_value);

    			if (dirty[0] & /*orderBook*/ 256) {
    				each_value_2 = /*orderBook*/ ctx[8].bids;
    				validate_each_argument(each_value_2);
    				let i;

    				for (i = 0; i < each_value_2.length; i += 1) {
    					const child_ctx = get_each_context_2(ctx, each_value_2, i);

    					if (each_blocks_2[i]) {
    						each_blocks_2[i].p(child_ctx, dirty);
    					} else {
    						each_blocks_2[i] = create_each_block_2(child_ctx);
    						each_blocks_2[i].c();
    						each_blocks_2[i].m(div42, null);
    					}
    				}

    				for (; i < each_blocks_2.length; i += 1) {
    					each_blocks_2[i].d(1);
    				}

    				each_blocks_2.length = each_value_2.length;
    			}

    			if (dirty[0] & /*orderBook*/ 256) {
    				each_value_1 = /*orderBook*/ ctx[8].asks;
    				validate_each_argument(each_value_1);
    				let i;

    				for (i = 0; i < each_value_1.length; i += 1) {
    					const child_ctx = get_each_context_1(ctx, each_value_1, i);

    					if (each_blocks_1[i]) {
    						each_blocks_1[i].p(child_ctx, dirty);
    					} else {
    						each_blocks_1[i] = create_each_block_1(child_ctx);
    						each_blocks_1[i].c();
    						each_blocks_1[i].m(div44, null);
    					}
    				}

    				for (; i < each_blocks_1.length; i += 1) {
    					each_blocks_1[i].d(1);
    				}

    				each_blocks_1.length = each_value_1.length;
    			}

    			if (dirty[0] & /*trades*/ 4) {
    				each_value = /*trades*/ ctx[2].slice(0, 10);
    				validate_each_argument(each_value);
    				let i;

    				for (i = 0; i < each_value.length; i += 1) {
    					const child_ctx = get_each_context(ctx, each_value, i);

    					if (each_blocks[i]) {
    						each_blocks[i].p(child_ctx, dirty);
    					} else {
    						each_blocks[i] = create_each_block(child_ctx);
    						each_blocks[i].c();
    						each_blocks[i].m(div48, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}

    				each_blocks.length = each_value.length;
    			}

    			if (dirty[0] & /*volumeIntensity*/ 2048) {
    				set_style(div50, "width", /*volumeIntensity*/ ctx[11] * 100 + "%");
    			}

    			if (dirty[0] & /*audioEnabled*/ 4096 && div53_class_value !== (div53_class_value = "pulse-indicator " + (/*audioEnabled*/ ctx[12] ? 'active' : '') + " svelte-94kqpu")) {
    				attr_dev(div53, "class", div53_class_value);
    			}
    		},
    		i: noop,
    		o: noop,
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(main);
    			if_block0.d();
    			if (if_block1) if_block1.d();
    			if_block2.d();
    			if (if_block3) if_block3.d();
    			destroy_each(each_blocks_2, detaching);
    			destroy_each(each_blocks_1, detaching);
    			destroy_each(each_blocks, detaching);
    			mounted = false;
    			dispose();
    		}
    	};

    	dispatch_dev("SvelteRegisterBlock", {
    		block,
    		id: create_fragment.name,
    		type: "component",
    		source: "",
    		ctx
    	});

    	return block;
    }

    const TPS_WINDOW = 10; // seconds

    function processStatus(status) {
    	console.log('Status update:', status);
    }

    function formatPrice(price) {
    	return new Intl.NumberFormat('en-US',
    	{
    			style: 'currency',
    			currency: 'USD',
    			minimumFractionDigits: 2,
    			maximumFractionDigits: 2
    		}).format(price);
    }

    function formatSize(size) {
    	return size.toFixed(6);
    }

    function formatVolume(volume) {
    	if (volume >= 1000000) {
    		return (volume / 1000000).toFixed(2) + 'M';
    	} else if (volume >= 1000) {
    		return (volume / 1000).toFixed(2) + 'K';
    	}

    	return volume.toFixed(2);
    }

    function formatTime(timestamp) {
    	return new Date(timestamp).toLocaleTimeString();
    }

    function instance($$self, $$props, $$invalidate) {
    	let { $$slots: slots = {}, $$scope } = $$props;
    	validate_slots('App', slots, []);
    	let ws;
    	let isConnected = false;

    	// Trade data
    	let currentPrice = 0;

    	let lastPrice = 0;
    	let trades = [];
    	let tradeCount = 0;
    	let totalVolume = 0;
    	let avgTradeSize = 0;
    	let tradesPerSecond = 0;
    	let largestTrade = null;

    	// New ticker data
    	let tickerData = {
    		bestBid: 0,
    		bestAsk: 0,
    		volume24h: 0,
    		low24h: 0,
    		high24h: 0,
    		spread: 0
    	};

    	// Order book data
    	let orderBook = {
    		bids: [],
    		asks: [],
    		spread: 0,
    		bidDepth: 0,
    		askDepth: 0
    	};

    	// Connection health
    	let lastHeartbeat = null;

    	let connectionHealth = 'unknown';

    	// UI state
    	let priceDirection = 'neutral'; // 'up', 'down', 'neutral'

    	let volumeIntensity = 0;
    	let audioEnabled = false;
    	let activeChannels = ['matches', 'ticker', 'level2', 'heartbeat'];

    	// Rolling window for TPS calculation
    	let tradeTimestamps = [];

    	let clickSound = null;

    	onMount(() => {
    		connectWebSocket();

    		// Preload the click sound
    		clickSound = new Audio('/geiger_click.wav');

    		clickSound.load();
    	});

    	onDestroy(() => {
    		if (ws) {
    			ws.close();
    		}
    	});

    	function connectWebSocket() {
    		try {
    			// Connect with channel filtering for multi-channel support
    			const channelParam = activeChannels.join(',');

    			ws = new WebSocket(`ws://localhost:8000/ws?channels=${channelParam}`);

    			ws.onopen = () => {
    				$$invalidate(0, isConnected = true);
    				connectionHealth = 'healthy';
    				console.log('Connected to WebSocket with channels:', activeChannels);
    			};

    			ws.onmessage = event => {
    				const message = JSON.parse(event.data);

    				// Only process BTC data
    				if (message.product_id && message.product_id !== 'BTC-USD') {
    					return;
    				}

    				switch (message.type) {
    					case 'btc_trade':
    						processTrade(message.data);
    						break;
    					case 'btc_ticker':
    						processTicker(message.data);
    						break;
    					case 'btc_orderbook_snapshot':
    						processOrderBookSnapshot(message.data);
    						break;
    					case 'btc_orderbook_update':
    						processOrderBookUpdate(message.data);
    						break;
    					case 'btc_heartbeat':
    						processHeartbeat(message.data);
    						break;
    					case 'btc_status':
    						processStatus(message.data);
    						break;
    					case 'filter_channels':
    						console.log('Channel filter applied:', message.channels);
    						break;
    				}
    			};

    			ws.onclose = () => {
    				$$invalidate(0, isConnected = false);
    				connectionHealth = 'disconnected';
    				console.log('WebSocket connection closed');

    				// Reconnect after 3 seconds
    				setTimeout(connectWebSocket, 3000);
    			};

    			ws.onerror = error => {
    				console.error('WebSocket error:', error);
    				connectionHealth = 'error';
    			};
    		} catch(error) {
    			console.error('Failed to connect to WebSocket:', error);
    			connectionHealth = 'error';
    		}
    	}

    	function processTrade(trade) {
    		const now = Date.now();

    		// Update price data
    		lastPrice = currentPrice;

    		$$invalidate(1, currentPrice = trade.price);

    		// Determine price direction
    		if (currentPrice > lastPrice) {
    			$$invalidate(10, priceDirection = 'up');
    		} else if (currentPrice < lastPrice) {
    			$$invalidate(10, priceDirection = 'down');
    		} else {
    			$$invalidate(10, priceDirection = 'neutral');
    		}

    		// Add to trades array (keep last 100 trades)
    		$$invalidate(2, trades = [trade, ...trades.slice(0, 99)]);

    		// Update statistics
    		$$invalidate(3, tradeCount++, tradeCount);

    		totalVolume += trade.size;
    		$$invalidate(4, avgTradeSize = totalVolume / tradeCount);

    		// Calculate trades per second
    		tradeTimestamps.unshift(now);

    		tradeTimestamps = tradeTimestamps.filter(ts => now - ts <= TPS_WINDOW * 1000);
    		$$invalidate(5, tradesPerSecond = tradeTimestamps.length / TPS_WINDOW);

    		// Update volume intensity (0-1 scale)
    		$$invalidate(11, volumeIntensity = Math.min(trade.size / 10, 1)); // Normalize to 10 BTC max

    		// Play the click sound if audio is enabled
    		if (audioEnabled && clickSound) {
    			clickSound.currentTime = 0;
    			clickSound.play();
    		}

    		// Track largest trade
    		if (!largestTrade || trade.size > largestTrade.size) {
    			$$invalidate(6, largestTrade = { ...trade });
    		}
    	}

    	function processTicker(ticker) {
    		$$invalidate(7, tickerData = {
    			bestBid: ticker.best_bid,
    			bestAsk: ticker.best_ask,
    			volume24h: ticker.volume_24h,
    			low24h: ticker.low_24h,
    			high24h: ticker.high_24h,
    			spread: ticker.best_ask - ticker.best_bid
    		});

    		// Update current price from ticker if no recent trades
    		if (!currentPrice || Math.abs(currentPrice - ticker.price) > 0.01) {
    			$$invalidate(1, currentPrice = ticker.price);
    		}
    	}

    	function processOrderBookSnapshot(snapshot) {
    		$$invalidate(8, orderBook.bids = snapshot.bids.slice(0, 10), orderBook);
    		$$invalidate(8, orderBook.asks = snapshot.asks.slice(0, 10), orderBook);
    		updateOrderBookStats();
    	}

    	function processOrderBookUpdate(update) {
    		// This is a simplified update - in production you'd want to maintain the full order book
    		// For now, we'll just track the stats from the backend
    		updateOrderBookStats();
    	}

    	function updateOrderBookStats() {
    		if (orderBook.bids.length > 0 && orderBook.asks.length > 0) {
    			const topBid = parseFloat(orderBook.bids[0][0]);
    			const topAsk = parseFloat(orderBook.asks[0][0]);
    			$$invalidate(8, orderBook.spread = topAsk - topBid, orderBook);

    			// Calculate depth (total volume in top 10 levels)
    			$$invalidate(8, orderBook.bidDepth = orderBook.bids.reduce((sum, [price, size]) => sum + parseFloat(size), 0), orderBook);

    			$$invalidate(8, orderBook.askDepth = orderBook.asks.reduce((sum, [price, size]) => sum + parseFloat(size), 0), orderBook);
    		}
    	}

    	function processHeartbeat(heartbeat) {
    		$$invalidate(9, lastHeartbeat = new Date(heartbeat.timestamp));
    		connectionHealth = 'healthy';
    	}

    	function toggleAudio() {
    		$$invalidate(12, audioEnabled = !audioEnabled);
    	}

    	function getConnectionStatus() {
    		if (!isConnected) return 'disconnected';

    		if (lastHeartbeat && Date.now() - lastHeartbeat.getTime() > 30000) {
    			return 'stale';
    		}

    		return connectionHealth;
    	}

    	const writable_props = [];

    	Object.keys($$props).forEach(key => {
    		if (!~writable_props.indexOf(key) && key.slice(0, 2) !== '$$' && key !== 'slot') console_1.warn(`<App> was created with unknown prop '${key}'`);
    	});

    	$$self.$capture_state = () => ({
    		onMount,
    		onDestroy,
    		ws,
    		isConnected,
    		currentPrice,
    		lastPrice,
    		trades,
    		tradeCount,
    		totalVolume,
    		avgTradeSize,
    		tradesPerSecond,
    		largestTrade,
    		tickerData,
    		orderBook,
    		lastHeartbeat,
    		connectionHealth,
    		priceDirection,
    		volumeIntensity,
    		audioEnabled,
    		activeChannels,
    		tradeTimestamps,
    		TPS_WINDOW,
    		clickSound,
    		connectWebSocket,
    		processTrade,
    		processTicker,
    		processOrderBookSnapshot,
    		processOrderBookUpdate,
    		updateOrderBookStats,
    		processHeartbeat,
    		processStatus,
    		toggleAudio,
    		formatPrice,
    		formatSize,
    		formatVolume,
    		formatTime,
    		getConnectionStatus
    	});

    	$$self.$inject_state = $$props => {
    		if ('ws' in $$props) ws = $$props.ws;
    		if ('isConnected' in $$props) $$invalidate(0, isConnected = $$props.isConnected);
    		if ('currentPrice' in $$props) $$invalidate(1, currentPrice = $$props.currentPrice);
    		if ('lastPrice' in $$props) lastPrice = $$props.lastPrice;
    		if ('trades' in $$props) $$invalidate(2, trades = $$props.trades);
    		if ('tradeCount' in $$props) $$invalidate(3, tradeCount = $$props.tradeCount);
    		if ('totalVolume' in $$props) totalVolume = $$props.totalVolume;
    		if ('avgTradeSize' in $$props) $$invalidate(4, avgTradeSize = $$props.avgTradeSize);
    		if ('tradesPerSecond' in $$props) $$invalidate(5, tradesPerSecond = $$props.tradesPerSecond);
    		if ('largestTrade' in $$props) $$invalidate(6, largestTrade = $$props.largestTrade);
    		if ('tickerData' in $$props) $$invalidate(7, tickerData = $$props.tickerData);
    		if ('orderBook' in $$props) $$invalidate(8, orderBook = $$props.orderBook);
    		if ('lastHeartbeat' in $$props) $$invalidate(9, lastHeartbeat = $$props.lastHeartbeat);
    		if ('connectionHealth' in $$props) connectionHealth = $$props.connectionHealth;
    		if ('priceDirection' in $$props) $$invalidate(10, priceDirection = $$props.priceDirection);
    		if ('volumeIntensity' in $$props) $$invalidate(11, volumeIntensity = $$props.volumeIntensity);
    		if ('audioEnabled' in $$props) $$invalidate(12, audioEnabled = $$props.audioEnabled);
    		if ('activeChannels' in $$props) activeChannels = $$props.activeChannels;
    		if ('tradeTimestamps' in $$props) tradeTimestamps = $$props.tradeTimestamps;
    		if ('clickSound' in $$props) clickSound = $$props.clickSound;
    	};

    	if ($$props && "$$inject" in $$props) {
    		$$self.$inject_state($$props.$$inject);
    	}

    	return [
    		isConnected,
    		currentPrice,
    		trades,
    		tradeCount,
    		avgTradeSize,
    		tradesPerSecond,
    		largestTrade,
    		tickerData,
    		orderBook,
    		lastHeartbeat,
    		priceDirection,
    		volumeIntensity,
    		audioEnabled,
    		toggleAudio,
    		getConnectionStatus
    	];
    }

    class App extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance, create_fragment, safe_not_equal, {}, null, [-1, -1]);

    		dispatch_dev("SvelteRegisterComponent", {
    			component: this,
    			tagName: "App",
    			options,
    			id: create_fragment.name
    		});
    	}
    }

    const app = new App({
    	target: document.body,
    	props: {}
    });

    return app;

})();
//# sourceMappingURL=bundle.js.map
