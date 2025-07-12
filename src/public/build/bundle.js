
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
    	child_ctx[26] = list[i];
    	return child_ctx;
    }

    // (238:10) {:else}
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
    		source: "(238:10) {:else}",
    		ctx
    	});

    	return block;
    }

    // (236:46) 
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
    		source: "(236:46) ",
    		ctx
    	});

    	return block;
    }

    // (234:10) {#if priceDirection === 'up'}
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
    		source: "(234:10) {#if priceDirection === 'up'}",
    		ctx
    	});

    	return block;
    }

    // (258:6) {#if largestTrade}
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
    			attr_dev(div0, "class", "stat-label svelte-1ubwts6");
    			add_location(div0, file, 259, 8, 7221);
    			attr_dev(div1, "class", "stat-value svelte-1ubwts6");
    			add_location(div1, file, 260, 8, 7273);
    			attr_dev(span0, "class", "trade-side svelte-1ubwts6");
    			add_location(span0, file, 262, 10, 7384);
    			attr_dev(span1, "class", "trade-price");
    			add_location(span1, file, 263, 10, 7460);
    			attr_dev(span2, "class", "trade-time");
    			add_location(span2, file, 264, 10, 7537);
    			attr_dev(div2, "class", "stat-details svelte-1ubwts6");
    			add_location(div2, file, 261, 8, 7347);
    			attr_dev(div3, "class", div3_class_value = "stat-card largest-trade-card " + /*largestTrade*/ ctx[6].side + " svelte-1ubwts6");
    			add_location(div3, file, 258, 6, 7150);
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
    			if (dirty & /*largestTrade*/ 64 && t2_value !== (t2_value = formatSize(/*largestTrade*/ ctx[6].size) + "")) set_data_dev(t2, t2_value);
    			if (dirty & /*largestTrade*/ 64 && t5_value !== (t5_value = /*largestTrade*/ ctx[6].side.toUpperCase() + "")) set_data_dev(t5, t5_value);
    			if (dirty & /*largestTrade*/ 64 && t7_value !== (t7_value = formatPrice(/*largestTrade*/ ctx[6].price) + "")) set_data_dev(t7, t7_value);
    			if (dirty & /*largestTrade*/ 64 && t9_value !== (t9_value = formatTime(/*largestTrade*/ ctx[6].timestamp) + "")) set_data_dev(t9, t9_value);

    			if (dirty & /*largestTrade*/ 64 && div3_class_value !== (div3_class_value = "stat-card largest-trade-card " + /*largestTrade*/ ctx[6].side + " svelte-1ubwts6")) {
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
    		source: "(258:6) {#if largestTrade}",
    		ctx
    	});

    	return block;
    }

    // (274:8) {#each trades.slice(0, 10) as trade}
    function create_each_block(ctx) {
    	let div;
    	let span0;
    	let t0_value = /*trade*/ ctx[26].side.toUpperCase() + "";
    	let t0;
    	let t1;
    	let span1;
    	let t2_value = formatSize(/*trade*/ ctx[26].size) + "";
    	let t2;
    	let t3;
    	let t4;
    	let span2;
    	let t5_value = formatPrice(/*trade*/ ctx[26].price) + "";
    	let t5;
    	let t6;
    	let span3;
    	let t7_value = formatTime(/*trade*/ ctx[26].timestamp) + "";
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
    			attr_dev(span0, "class", "trade-side svelte-1ubwts6");
    			add_location(span0, file, 275, 12, 7861);
    			attr_dev(span1, "class", "trade-size");
    			add_location(span1, file, 276, 12, 7932);
    			attr_dev(span2, "class", "trade-price");
    			add_location(span2, file, 277, 12, 8005);
    			attr_dev(span3, "class", "trade-time");
    			add_location(span3, file, 278, 12, 8077);
    			attr_dev(div, "class", div_class_value = "trade-item " + /*trade*/ ctx[26].side + " svelte-1ubwts6");
    			add_location(div, file, 274, 10, 7811);
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
    			if (dirty & /*trades*/ 4 && t0_value !== (t0_value = /*trade*/ ctx[26].side.toUpperCase() + "")) set_data_dev(t0, t0_value);
    			if (dirty & /*trades*/ 4 && t2_value !== (t2_value = formatSize(/*trade*/ ctx[26].size) + "")) set_data_dev(t2, t2_value);
    			if (dirty & /*trades*/ 4 && t5_value !== (t5_value = formatPrice(/*trade*/ ctx[26].price) + "")) set_data_dev(t5, t5_value);
    			if (dirty & /*trades*/ 4 && t7_value !== (t7_value = formatTime(/*trade*/ ctx[26].timestamp) + "")) set_data_dev(t7, t7_value);

    			if (dirty & /*trades*/ 4 && div_class_value !== (div_class_value = "trade-item " + /*trade*/ ctx[26].side + " svelte-1ubwts6")) {
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
    		source: "(274:8) {#each trades.slice(0, 10) as trade}",
    		ctx
    	});

    	return block;
    }

    function create_fragment(ctx) {
    	let main;
    	let div23;
    	let header;
    	let h1;
    	let t1;
    	let div0;
    	let span;
    	let span_class_value;
    	let t2;
    	let t3_value = (/*isConnected*/ ctx[0] ? 'Connected' : 'Disconnected') + "";
    	let t3;
    	let t4;
    	let div1;
    	let button;
    	let t5_value = (/*audioEnabled*/ ctx[9] ? '🔊 Audio On' : '🔇 Audio Off') + "";
    	let t5;
    	let button_class_value;
    	let t6;
    	let div6;
    	let div5;
    	let div2;
    	let t8;
    	let div3;
    	let t9_value = formatPrice(/*currentPrice*/ ctx[1]) + "";
    	let t9;
    	let t10;
    	let div4;
    	let div5_class_value;
    	let t11;
    	let div16;
    	let div9;
    	let div7;
    	let t13;
    	let div8;
    	let t14_value = /*tradesPerSecond*/ ctx[5].toFixed(2) + "";
    	let t14;
    	let t15;
    	let div12;
    	let div10;
    	let t17;
    	let div11;
    	let t18;
    	let t19;
    	let div15;
    	let div13;
    	let t21;
    	let div14;
    	let t22_value = formatSize(/*avgTradeSize*/ ctx[4]) + "";
    	let t22;
    	let t23;
    	let t24;
    	let t25;
    	let div18;
    	let h2;
    	let t27;
    	let div17;
    	let t28;
    	let div22;
    	let div20;
    	let div19;
    	let t29;
    	let div21;
    	let div21_class_value;
    	let mounted;
    	let dispose;

    	function select_block_type(ctx, dirty) {
    		if (/*priceDirection*/ ctx[7] === 'up') return create_if_block_1;
    		if (/*priceDirection*/ ctx[7] === 'down') return create_if_block_2;
    		return create_else_block;
    	}

    	let current_block_type = select_block_type(ctx);
    	let if_block0 = current_block_type(ctx);
    	let if_block1 = /*largestTrade*/ ctx[6] && create_if_block(ctx);
    	let each_value = /*trades*/ ctx[2].slice(0, 10);
    	validate_each_argument(each_value);
    	let each_blocks = [];

    	for (let i = 0; i < each_value.length; i += 1) {
    		each_blocks[i] = create_each_block(get_each_context(ctx, each_value, i));
    	}

    	const block = {
    		c: function create() {
    			main = element("main");
    			div23 = element("div");
    			header = element("header");
    			h1 = element("h1");
    			h1.textContent = "🎵 BTC Live Tape Audio Visualizer";
    			t1 = space();
    			div0 = element("div");
    			span = element("span");
    			t2 = space();
    			t3 = text(t3_value);
    			t4 = space();
    			div1 = element("div");
    			button = element("button");
    			t5 = text(t5_value);
    			t6 = space();
    			div6 = element("div");
    			div5 = element("div");
    			div2 = element("div");
    			div2.textContent = "BTC/USD";
    			t8 = space();
    			div3 = element("div");
    			t9 = text(t9_value);
    			t10 = space();
    			div4 = element("div");
    			if_block0.c();
    			t11 = space();
    			div16 = element("div");
    			div9 = element("div");
    			div7 = element("div");
    			div7.textContent = "Trades/Second";
    			t13 = space();
    			div8 = element("div");
    			t14 = text(t14_value);
    			t15 = space();
    			div12 = element("div");
    			div10 = element("div");
    			div10.textContent = "Total Trades";
    			t17 = space();
    			div11 = element("div");
    			t18 = text(/*tradeCount*/ ctx[3]);
    			t19 = space();
    			div15 = element("div");
    			div13 = element("div");
    			div13.textContent = "Avg Trade Size";
    			t21 = space();
    			div14 = element("div");
    			t22 = text(t22_value);
    			t23 = text(" BTC");
    			t24 = space();
    			if (if_block1) if_block1.c();
    			t25 = space();
    			div18 = element("div");
    			h2 = element("h2");
    			h2.textContent = "Recent Trades";
    			t27 = space();
    			div17 = element("div");

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				each_blocks[i].c();
    			}

    			t28 = space();
    			div22 = element("div");
    			div20 = element("div");
    			div19 = element("div");
    			t29 = space();
    			div21 = element("div");
    			attr_dev(h1, "class", "svelte-1ubwts6");
    			add_location(h1, file, 215, 6, 5699);
    			attr_dev(span, "class", span_class_value = "status-indicator " + (/*isConnected*/ ctx[0] ? 'connected' : 'disconnected') + " svelte-1ubwts6");
    			add_location(span, file, 217, 8, 5788);
    			attr_dev(div0, "class", "connection-status svelte-1ubwts6");
    			add_location(div0, file, 216, 6, 5748);
    			attr_dev(header, "class", "svelte-1ubwts6");
    			add_location(header, file, 214, 4, 5684);
    			attr_dev(button, "class", button_class_value = "audio-toggle " + (/*audioEnabled*/ ctx[9] ? 'enabled' : 'disabled') + " svelte-1ubwts6");
    			add_location(button, file, 223, 6, 5990);
    			attr_dev(div1, "class", "controls svelte-1ubwts6");
    			add_location(div1, file, 222, 4, 5961);
    			attr_dev(div2, "class", "price-label svelte-1ubwts6");
    			add_location(div2, file, 230, 8, 6258);
    			attr_dev(div3, "class", "price-value svelte-1ubwts6");
    			add_location(div3, file, 231, 8, 6305);
    			attr_dev(div4, "class", "price-change svelte-1ubwts6");
    			add_location(div4, file, 232, 8, 6372);
    			attr_dev(div5, "class", div5_class_value = "current-price " + /*priceDirection*/ ctx[7] + " svelte-1ubwts6");
    			add_location(div5, file, 229, 6, 6205);
    			attr_dev(div6, "class", "price-section svelte-1ubwts6");
    			add_location(div6, file, 228, 4, 6171);
    			attr_dev(div7, "class", "stat-label svelte-1ubwts6");
    			add_location(div7, file, 246, 8, 6685);
    			attr_dev(div8, "class", "stat-value svelte-1ubwts6");
    			add_location(div8, file, 247, 8, 6737);
    			attr_dev(div9, "class", "stat-card svelte-1ubwts6");
    			add_location(div9, file, 245, 6, 6653);
    			attr_dev(div10, "class", "stat-label svelte-1ubwts6");
    			add_location(div10, file, 250, 8, 6847);
    			attr_dev(div11, "class", "stat-value svelte-1ubwts6");
    			add_location(div11, file, 251, 8, 6898);
    			attr_dev(div12, "class", "stat-card svelte-1ubwts6");
    			add_location(div12, file, 249, 6, 6815);
    			attr_dev(div13, "class", "stat-label svelte-1ubwts6");
    			add_location(div13, file, 254, 8, 6992);
    			attr_dev(div14, "class", "stat-value svelte-1ubwts6");
    			add_location(div14, file, 255, 8, 7045);
    			attr_dev(div15, "class", "stat-card svelte-1ubwts6");
    			add_location(div15, file, 253, 6, 6960);
    			attr_dev(div16, "class", "stats-grid svelte-1ubwts6");
    			add_location(div16, file, 244, 4, 6622);
    			attr_dev(h2, "class", "svelte-1ubwts6");
    			add_location(h2, file, 271, 6, 7701);
    			attr_dev(div17, "class", "trades-list svelte-1ubwts6");
    			add_location(div17, file, 272, 6, 7730);
    			attr_dev(div18, "class", "trades-section svelte-1ubwts6");
    			add_location(div18, file, 270, 4, 7666);
    			attr_dev(div19, "class", "volume-fill svelte-1ubwts6");
    			set_style(div19, "width", /*volumeIntensity*/ ctx[8] * 100 + "%");
    			add_location(div19, file, 286, 8, 8269);
    			attr_dev(div20, "class", "volume-bar svelte-1ubwts6");
    			add_location(div20, file, 285, 6, 8236);
    			attr_dev(div21, "class", div21_class_value = "pulse-indicator " + (/*audioEnabled*/ ctx[9] ? 'active' : '') + " svelte-1ubwts6");
    			add_location(div21, file, 288, 6, 8360);
    			attr_dev(div22, "class", "visualizer svelte-1ubwts6");
    			add_location(div22, file, 284, 4, 8205);
    			attr_dev(div23, "class", "container svelte-1ubwts6");
    			add_location(div23, file, 213, 2, 5656);
    			add_location(main, file, 212, 0, 5647);
    		},
    		l: function claim(nodes) {
    			throw new Error("options.hydrate only works if the component was compiled with the `hydratable: true` option");
    		},
    		m: function mount(target, anchor) {
    			insert_dev(target, main, anchor);
    			append_dev(main, div23);
    			append_dev(div23, header);
    			append_dev(header, h1);
    			append_dev(header, t1);
    			append_dev(header, div0);
    			append_dev(div0, span);
    			append_dev(div0, t2);
    			append_dev(div0, t3);
    			append_dev(div23, t4);
    			append_dev(div23, div1);
    			append_dev(div1, button);
    			append_dev(button, t5);
    			append_dev(div23, t6);
    			append_dev(div23, div6);
    			append_dev(div6, div5);
    			append_dev(div5, div2);
    			append_dev(div5, t8);
    			append_dev(div5, div3);
    			append_dev(div3, t9);
    			append_dev(div5, t10);
    			append_dev(div5, div4);
    			if_block0.m(div4, null);
    			append_dev(div23, t11);
    			append_dev(div23, div16);
    			append_dev(div16, div9);
    			append_dev(div9, div7);
    			append_dev(div9, t13);
    			append_dev(div9, div8);
    			append_dev(div8, t14);
    			append_dev(div16, t15);
    			append_dev(div16, div12);
    			append_dev(div12, div10);
    			append_dev(div12, t17);
    			append_dev(div12, div11);
    			append_dev(div11, t18);
    			append_dev(div16, t19);
    			append_dev(div16, div15);
    			append_dev(div15, div13);
    			append_dev(div15, t21);
    			append_dev(div15, div14);
    			append_dev(div14, t22);
    			append_dev(div14, t23);
    			append_dev(div16, t24);
    			if (if_block1) if_block1.m(div16, null);
    			append_dev(div23, t25);
    			append_dev(div23, div18);
    			append_dev(div18, h2);
    			append_dev(div18, t27);
    			append_dev(div18, div17);

    			for (let i = 0; i < each_blocks.length; i += 1) {
    				if (each_blocks[i]) {
    					each_blocks[i].m(div17, null);
    				}
    			}

    			append_dev(div23, t28);
    			append_dev(div23, div22);
    			append_dev(div22, div20);
    			append_dev(div20, div19);
    			append_dev(div22, t29);
    			append_dev(div22, div21);

    			if (!mounted) {
    				dispose = listen_dev(button, "click", /*toggleAudio*/ ctx[10], false, false, false, false);
    				mounted = true;
    			}
    		},
    		p: function update(ctx, [dirty]) {
    			if (dirty & /*isConnected*/ 1 && span_class_value !== (span_class_value = "status-indicator " + (/*isConnected*/ ctx[0] ? 'connected' : 'disconnected') + " svelte-1ubwts6")) {
    				attr_dev(span, "class", span_class_value);
    			}

    			if (dirty & /*isConnected*/ 1 && t3_value !== (t3_value = (/*isConnected*/ ctx[0] ? 'Connected' : 'Disconnected') + "")) set_data_dev(t3, t3_value);
    			if (dirty & /*audioEnabled*/ 512 && t5_value !== (t5_value = (/*audioEnabled*/ ctx[9] ? '🔊 Audio On' : '🔇 Audio Off') + "")) set_data_dev(t5, t5_value);

    			if (dirty & /*audioEnabled*/ 512 && button_class_value !== (button_class_value = "audio-toggle " + (/*audioEnabled*/ ctx[9] ? 'enabled' : 'disabled') + " svelte-1ubwts6")) {
    				attr_dev(button, "class", button_class_value);
    			}

    			if (dirty & /*currentPrice*/ 2 && t9_value !== (t9_value = formatPrice(/*currentPrice*/ ctx[1]) + "")) set_data_dev(t9, t9_value);

    			if (current_block_type !== (current_block_type = select_block_type(ctx))) {
    				if_block0.d(1);
    				if_block0 = current_block_type(ctx);

    				if (if_block0) {
    					if_block0.c();
    					if_block0.m(div4, null);
    				}
    			}

    			if (dirty & /*priceDirection*/ 128 && div5_class_value !== (div5_class_value = "current-price " + /*priceDirection*/ ctx[7] + " svelte-1ubwts6")) {
    				attr_dev(div5, "class", div5_class_value);
    			}

    			if (dirty & /*tradesPerSecond*/ 32 && t14_value !== (t14_value = /*tradesPerSecond*/ ctx[5].toFixed(2) + "")) set_data_dev(t14, t14_value);
    			if (dirty & /*tradeCount*/ 8) set_data_dev(t18, /*tradeCount*/ ctx[3]);
    			if (dirty & /*avgTradeSize*/ 16 && t22_value !== (t22_value = formatSize(/*avgTradeSize*/ ctx[4]) + "")) set_data_dev(t22, t22_value);

    			if (/*largestTrade*/ ctx[6]) {
    				if (if_block1) {
    					if_block1.p(ctx, dirty);
    				} else {
    					if_block1 = create_if_block(ctx);
    					if_block1.c();
    					if_block1.m(div16, null);
    				}
    			} else if (if_block1) {
    				if_block1.d(1);
    				if_block1 = null;
    			}

    			if (dirty & /*trades, formatTime, formatPrice, formatSize*/ 4) {
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
    						each_blocks[i].m(div17, null);
    					}
    				}

    				for (; i < each_blocks.length; i += 1) {
    					each_blocks[i].d(1);
    				}

    				each_blocks.length = each_value.length;
    			}

    			if (dirty & /*volumeIntensity*/ 256) {
    				set_style(div19, "width", /*volumeIntensity*/ ctx[8] * 100 + "%");
    			}

    			if (dirty & /*audioEnabled*/ 512 && div21_class_value !== (div21_class_value = "pulse-indicator " + (/*audioEnabled*/ ctx[9] ? 'active' : '') + " svelte-1ubwts6")) {
    				attr_dev(div21, "class", div21_class_value);
    			}
    		},
    		i: noop,
    		o: noop,
    		d: function destroy(detaching) {
    			if (detaching) detach_dev(main);
    			if_block0.d();
    			if (if_block1) if_block1.d();
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

    function formatTime(timestamp) {
    	return new Date(timestamp).toLocaleTimeString();
    }

    function instance($$self, $$props, $$invalidate) {
    	let { $$slots: slots = {}, $$scope } = $$props;
    	validate_slots('App', slots, []);
    	let ws;
    	let isConnected = false;

    	// Audio context and nodes
    	let audioContext;

    	let oscillator;
    	let gainNode;
    	let analyser;
    	let dataArray;
    	let isAudioInitialized = false;

    	// Trade data
    	let currentPrice = 0;

    	let lastPrice = 0;
    	let trades = [];
    	let tradeCount = 0;
    	let totalVolume = 0;
    	let avgTradeSize = 0;
    	let tradesPerSecond = 0;
    	let largestTrade = null;

    	// UI state
    	let priceDirection = 'neutral'; // 'up', 'down', 'neutral'

    	let volumeIntensity = 0;
    	let audioEnabled = false;

    	// Rolling window for TPS calculation
    	let tradeTimestamps = [];

    	let clickSound = null;

    	onMount(() => {
    		connectWebSocket();

    		// Preload the click sound
    		clickSound = new Audio('/geiger_click.wav');

    		clickSound.load();
    		initializeAudio();
    	});

    	onDestroy(() => {
    		if (ws) {
    			ws.close();
    		}

    		if (audioContext) {
    			audioContext.close();
    		}
    	});

    	function connectWebSocket() {
    		try {
    			ws = new WebSocket('ws://localhost:8000/ws');

    			ws.onopen = () => {
    				$$invalidate(0, isConnected = true);
    				console.log('Connected to WebSocket');
    			};

    			ws.onmessage = event => {
    				const message = JSON.parse(event.data);

    				if (message.type === 'trade') {
    					processTrade(message.data);
    				}
    			};

    			ws.onclose = () => {
    				$$invalidate(0, isConnected = false);
    				console.log('WebSocket connection closed');

    				// Reconnect after 3 seconds
    				setTimeout(connectWebSocket, 3000);
    			};

    			ws.onerror = error => {
    				console.error('WebSocket error:', error);
    			};
    		} catch(error) {
    			console.error('Failed to connect to WebSocket:', error);
    		}
    	}

    	function initializeAudio() {
    		try {
    			audioContext = new (window.AudioContext || window.webkitAudioContext)();

    			// Create oscillator
    			oscillator = audioContext.createOscillator();

    			gainNode = audioContext.createGain();
    			analyser = audioContext.createAnalyser();

    			// Configure nodes
    			oscillator.type = 'sine';

    			oscillator.frequency.setValueAtTime(220, audioContext.currentTime);
    			gainNode.gain.setValueAtTime(0, audioContext.currentTime);
    			analyser.fftSize = 256;
    			dataArray = new Uint8Array(analyser.frequencyBinCount);

    			// Connect nodes
    			oscillator.connect(gainNode);

    			gainNode.connect(analyser);
    			analyser.connect(audioContext.destination);

    			// Start oscillator
    			oscillator.start();

    			isAudioInitialized = true;
    			console.log('Audio initialized');
    		} catch(error) {
    			console.error('Failed to initialize audio:', error);
    		}
    	}

    	function processTrade(trade) {
    		const now = Date.now();

    		// Update price data
    		lastPrice = currentPrice;

    		$$invalidate(1, currentPrice = trade.price);

    		// Determine price direction
    		if (currentPrice > lastPrice) {
    			$$invalidate(7, priceDirection = 'up');
    		} else if (currentPrice < lastPrice) {
    			$$invalidate(7, priceDirection = 'down');
    		} else {
    			$$invalidate(7, priceDirection = 'neutral');
    		}

    		// Add to trades array (keep last 100 trades)
    		$$invalidate(2, trades = [trade, ...trades.slice(0, 99)]); // Svelte reactivity fix

    		// Update statistics
    		$$invalidate(3, tradeCount++, tradeCount);

    		totalVolume += trade.size;
    		$$invalidate(4, avgTradeSize = totalVolume / tradeCount);

    		// Calculate trades per second
    		tradeTimestamps.unshift(now);

    		tradeTimestamps = tradeTimestamps.filter(ts => now - ts <= TPS_WINDOW * 1000);
    		$$invalidate(5, tradesPerSecond = tradeTimestamps.length / TPS_WINDOW);

    		// Update volume intensity (0-1 scale)
    		$$invalidate(8, volumeIntensity = Math.min(trade.size / 10, 1)); // Normalize to 10 BTC max

    		// Update audio
    		if (audioEnabled && isAudioInitialized) {
    			updateAudio(trade);
    		}

    		// Play the click sound if audio is enabled
    		if (audioEnabled && clickSound) {
    			clickSound.currentTime = 0;
    			clickSound.play();
    		}

    		// Track largest trade
    		if (!largestTrade || trade.size > largestTrade.size) {
    			$$invalidate(6, largestTrade = { ...trade });
    			$$invalidate(6, largestTrade = { ...largestTrade }); // Svelte reactivity fix
    		}
    	}

    	function updateAudio(trade) {
    		if (!audioContext || !oscillator || !gainNode) return;
    		const now = audioContext.currentTime;

    		// Map trade size to frequency (larger trades = lower frequency)
    		const frequency = Math.max(100, 500 - trade.size * 20);

    		// Map volume intensity to gain (0-0.3 to avoid ear damage)
    		const gain = volumeIntensity * 0.3;

    		// Different tones for buy/sell
    		const baseFreq = trade.side === 'buy' ? frequency : frequency * 0.8;

    		// Set frequency and gain
    		oscillator.frequency.setValueAtTime(baseFreq, now);

    		gainNode.gain.setValueAtTime(gain, now);

    		// Create a brief tone (attack and decay)
    		gainNode.gain.exponentialRampToValueAtTime(gain, now + 0.01);

    		gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
    	}

    	function toggleAudio() {
    		$$invalidate(9, audioEnabled = !audioEnabled);

    		if (!audioEnabled && gainNode) {
    			gainNode.gain.setValueAtTime(0, audioContext.currentTime);
    		}
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
    		audioContext,
    		oscillator,
    		gainNode,
    		analyser,
    		dataArray,
    		isAudioInitialized,
    		currentPrice,
    		lastPrice,
    		trades,
    		tradeCount,
    		totalVolume,
    		avgTradeSize,
    		tradesPerSecond,
    		largestTrade,
    		priceDirection,
    		volumeIntensity,
    		audioEnabled,
    		tradeTimestamps,
    		TPS_WINDOW,
    		clickSound,
    		connectWebSocket,
    		initializeAudio,
    		processTrade,
    		updateAudio,
    		toggleAudio,
    		formatPrice,
    		formatSize,
    		formatTime
    	});

    	$$self.$inject_state = $$props => {
    		if ('ws' in $$props) ws = $$props.ws;
    		if ('isConnected' in $$props) $$invalidate(0, isConnected = $$props.isConnected);
    		if ('audioContext' in $$props) audioContext = $$props.audioContext;
    		if ('oscillator' in $$props) oscillator = $$props.oscillator;
    		if ('gainNode' in $$props) gainNode = $$props.gainNode;
    		if ('analyser' in $$props) analyser = $$props.analyser;
    		if ('dataArray' in $$props) dataArray = $$props.dataArray;
    		if ('isAudioInitialized' in $$props) isAudioInitialized = $$props.isAudioInitialized;
    		if ('currentPrice' in $$props) $$invalidate(1, currentPrice = $$props.currentPrice);
    		if ('lastPrice' in $$props) lastPrice = $$props.lastPrice;
    		if ('trades' in $$props) $$invalidate(2, trades = $$props.trades);
    		if ('tradeCount' in $$props) $$invalidate(3, tradeCount = $$props.tradeCount);
    		if ('totalVolume' in $$props) totalVolume = $$props.totalVolume;
    		if ('avgTradeSize' in $$props) $$invalidate(4, avgTradeSize = $$props.avgTradeSize);
    		if ('tradesPerSecond' in $$props) $$invalidate(5, tradesPerSecond = $$props.tradesPerSecond);
    		if ('largestTrade' in $$props) $$invalidate(6, largestTrade = $$props.largestTrade);
    		if ('priceDirection' in $$props) $$invalidate(7, priceDirection = $$props.priceDirection);
    		if ('volumeIntensity' in $$props) $$invalidate(8, volumeIntensity = $$props.volumeIntensity);
    		if ('audioEnabled' in $$props) $$invalidate(9, audioEnabled = $$props.audioEnabled);
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
    		priceDirection,
    		volumeIntensity,
    		audioEnabled,
    		toggleAudio
    	];
    }

    class App extends SvelteComponentDev {
    	constructor(options) {
    		super(options);
    		init(this, options, instance, create_fragment, safe_not_equal, {});

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
